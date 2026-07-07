"""
Cloud Function entry point: complete_chapter

Deployed as a 2nd-gen Cloud Function (HTTP trigger, --allow-unauthenticated).
Auth is enforced in code via Firebase ID token verification.

Firebase Callable wire protocol:
  Request:  POST /
            Authorization: Bearer <firebase-id-token>
            Content-Type: application/json
            Body: { "data": { "chapterId": "<Firestore chapter document ID>" } }

  Success:  { "result": { "chapterId": str,
                           "xpGained": int,
                           "progressSummary": str,
                           "completedChapterIds": [str, ...] } }
  Error:    { "error": { "status": "...", "message": "..." } }

The function:
  1. Verifies the caller's Firebase ID token (extracts uid).
  2. Verifies the caller's account is "active" and within their rate limit.
  3. Runs the progress service: verifies the student attempted at least one
     graded exercise (BE-06, when the chapter has any), generates a progress
     summary via Gemini, and atomically updates the user document in
     Firestore (completedChapterIds, lastActive, lastProgressSummary, xp).
  4. Returns the progress data to the caller.

Note: grammar book entries are no longer generated here. Each chapter document
contains a pre-generated grammarSummary field (written by the content-cli pipeline).
The frontend assembles the grammar book at runtime from completed chapter summaries.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import firebase_admin
import flask
import functions_framework
from firebase_admin import credentials
from google.cloud.firestore import Client as FirestoreClient

import log_setup  # noqa: F401 — configures root logger for Cloud Logging
from callable_helpers import (
    PreconditionFailedError,
    RateLimitExceeded,
    callable_error,
    callable_response,
    check_rate_limit,
    cors_preflight,
    ensure_active_user,
    parse_callable_request,
    verify_firebase_token,
)
from constants import RATE_LIMIT_COMPLETE_CHAPTER, RATE_LIMIT_WINDOW_SECONDS
from services.progress import complete_chapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Firebase Admin SDK — initialised once per cold start.
# ---------------------------------------------------------------------------


def _init_firebase() -> None:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred = credentials.Certificate(cred_path) if cred_path else credentials.ApplicationDefault()
    firebase_admin.initialize_app(
        cred,
        {"projectId": os.getenv("GOOGLE_CLOUD_PROJECT")},
    )


# IMP-BE-03: construct the Firestore client once and reuse it across
# invocations within the same process, instead of on every single request.
@lru_cache(maxsize=1)
def _get_db() -> FirestoreClient:
    return FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))


# ---------------------------------------------------------------------------
# Cloud Function entry point
# ---------------------------------------------------------------------------


@functions_framework.http
def complete_chapter_fn(request: flask.Request) -> tuple:
    """HTTP Cloud Function entry point for chapter completion."""
    # Handle CORS preflight before any auth/logic.
    if request.method == "OPTIONS":
        return cors_preflight()

    _init_firebase()

    # 1. Verify caller identity
    try:
        decoded_token = verify_firebase_token(request)
    except PermissionError as exc:
        return callable_error("UNAUTHENTICATED", str(exc), 401)

    uid: str = decoded_token["uid"]

    # 2. Parse request data
    try:
        data = parse_callable_request(request)
        chapter_id: str = data["chapterId"]
        if not chapter_id:
            raise ValueError("chapterId must not be empty.")
    except (ValueError, KeyError) as exc:
        return callable_error("INVALID_ARGUMENT", str(exc), 400)

    db = _get_db()

    # 3. Active-user gate (BE-05) — must run before any billable work.
    try:
        ensure_active_user(db, uid)
    except PermissionError as exc:
        return callable_error("PERMISSION_DENIED", str(exc), 403)

    # 4. Per-user rate limit (IMP-BE-07)
    try:
        check_rate_limit(
            db,
            uid,
            "complete_chapter",
            limit=RATE_LIMIT_COMPLETE_CHAPTER,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )
    except RateLimitExceeded as exc:
        return callable_error("RESOURCE_EXHAUSTED", str(exc), 429)

    # 5. Run the progress workflow (~10s — one Gemini call for the progress summary)
    try:
        result = complete_chapter(uid=uid, chapter_id=chapter_id)
    except PreconditionFailedError as exc:
        return callable_error("FAILED_PRECONDITION", str(exc), 400)
    except ValueError as exc:
        return callable_error("NOT_FOUND", str(exc), 404)
    except Exception as exc:
        logger.exception("Error completing chapter '%s' for user '%s': %s", chapter_id, uid, exc)
        return callable_error("INTERNAL", "Failed to process chapter completion.", 500)

    # 6. Return result — use camelCase keys to match the Firebase Callable convention
    return callable_response(
        {
            "chapterId": result["chapter_id"],
            "xpGained": result["xp_gained"],
            "progressSummary": result["progress_summary"],
            "completedChapterIds": result["completed_chapter_ids"],
        }
    )
