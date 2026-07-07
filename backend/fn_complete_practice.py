"""
Cloud Function entry point: complete_practice

Deployed as a 2nd-gen Cloud Function (HTTP trigger, --allow-unauthenticated).
Auth is enforced in code via Firebase ID token verification.

Firebase Callable wire protocol:
  Request:  POST /
            Authorization: Bearer <firebase-id-token>
            Content-Type: application/json
            Body: { "data": { "practiceSetId": "<Firestore practice_sets document ID>" } }

  Success:  { "result": { "practiceSetId": str, "xpGained": int } }
  Error:    { "error": { "status": "...", "message": "..." } }

The function:
  1. Verifies the caller's Firebase ID token (extracts uid).
  2. Verifies the caller's account is "active" and within their rate limit.
  3. Checks if the practice set is already completed (idempotent — returns 200 if so).
  4. Awards PRACTICE_XP and adds the practiceSetId to completedPracticeSetIds.
  5. Returns { practiceSetId, xpGained }.
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
    RateLimitExceeded,
    callable_error,
    callable_response,
    check_rate_limit,
    cors_preflight,
    ensure_active_user,
    parse_callable_request,
    verify_firebase_token,
)
from constants import RATE_LIMIT_COMPLETE_PRACTICE, RATE_LIMIT_WINDOW_SECONDS
from services.practice_progress import complete_practice

logger = logging.getLogger(__name__)


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


@functions_framework.http
def complete_practice_fn(request: flask.Request) -> tuple:
    """HTTP Cloud Function entry point for practice set completion."""
    if request.method == "OPTIONS":
        return cors_preflight()

    _init_firebase()

    try:
        decoded_token = verify_firebase_token(request)
    except PermissionError as exc:
        return callable_error("UNAUTHENTICATED", str(exc), 401)

    uid: str = decoded_token["uid"]

    try:
        data = parse_callable_request(request)
        practice_set_id: str = data["practiceSetId"]
        if not practice_set_id:
            raise ValueError("practiceSetId must not be empty.")
    except (ValueError, KeyError) as exc:
        return callable_error("INVALID_ARGUMENT", str(exc), 400)

    db = _get_db()

    # Active-user gate (BE-05) — must run before any billable/state-changing work.
    try:
        ensure_active_user(db, uid)
    except PermissionError as exc:
        return callable_error("PERMISSION_DENIED", str(exc), 403)

    # Per-user rate limit (IMP-BE-07)
    try:
        check_rate_limit(
            db,
            uid,
            "complete_practice",
            limit=RATE_LIMIT_COMPLETE_PRACTICE,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )
    except RateLimitExceeded as exc:
        return callable_error("RESOURCE_EXHAUSTED", str(exc), 429)

    try:
        result = complete_practice(uid=uid, practice_set_id=practice_set_id)
    except ValueError as exc:
        return callable_error("NOT_FOUND", str(exc), 404)
    except Exception as exc:
        logger.exception("Error completing practice '%s' for user '%s': %s", practice_set_id, uid, exc)
        return callable_error("INTERNAL", "Failed to process practice set completion.", 500)

    return callable_response(
        {
            "practiceSetId": result["practice_set_id"],
            "xpGained": result["xp_gained"],
        }
    )
