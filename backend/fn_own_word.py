"""
Cloud Function entry point: add_own_word

Deployed as a 2nd-gen Cloud Function (HTTP trigger, --no-allow-unauthenticated).
Auth is enforced in code via Firebase ID token verification.

Firebase Callable wire protocol:
  Request:  POST /
            Authorization: Bearer <firebase-id-token>
            Content-Type: application/json
            Body: { "data": { "text": "<Greek word>", "chapterId": "...", "bookId": "..." } }

  Success:  { "result": { "greek": "...", "english": "...", "audioUrl": "...",
                           "chapterId": "...", "bookId": "...", "createdAt": "..." } }
  Error:    { "error": { "status": "...", "message": "..." } }

The function:
  1. Verifies the caller's Firebase ID token.
  2. Validates input (non-empty, ≤ 50 chars, chapterId and bookId present).
  3. Verifies the caller's account is "active" and within their rate limit.
  4. Calls the own_word service to normalise, generate TTS, upload to GCS, and save to Firestore.
     Real deduplication happens there via the deterministic Firestore document ID + set()
     (see BE-13 note in services/own_word.py) — this function no longer runs its own
     (ineffective) pre-check.
  5. Returns the word card data to the caller.
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
from constants import RATE_LIMIT_ADD_OWN_WORD, RATE_LIMIT_WINDOW_SECONDS
from services.own_word import _MAX_INPUT_CHARS, create_own_word

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
def add_own_word_fn(request: flask.Request) -> tuple:
    """HTTP Cloud Function entry point for adding a student's own vocabulary word."""
    if request.method == "OPTIONS":
        return cors_preflight()

    _init_firebase()

    # 1. Verify caller identity
    try:
        decoded_token = verify_firebase_token(request)
    except PermissionError as exc:
        return callable_error("UNAUTHENTICATED", str(exc), 401)

    caller_uid: str = decoded_token["uid"]

    # 2. Parse and validate request data
    try:
        data = parse_callable_request(request)
        text: str = (data.get("text") or "").strip()
        chapter_id: str = (data.get("chapterId") or "").strip()
        book_id: str = (data.get("bookId") or "").strip()

        if not text:
            raise ValueError("'text' must not be empty.")
        if len(text) > _MAX_INPUT_CHARS:
            raise ValueError(f"Input exceeds maximum allowed length of {_MAX_INPUT_CHARS} characters.")
        if not chapter_id:
            raise ValueError("'chapterId' must not be empty.")
        if not book_id:
            raise ValueError("'bookId' must not be empty.")
    except (ValueError, KeyError) as exc:
        return callable_error("INVALID_ARGUMENT", str(exc), 400)

    db = _get_db()

    # 3. Active-user gate (BE-05) — must run before any billable work.
    try:
        ensure_active_user(db, caller_uid)
    except PermissionError as exc:
        return callable_error("PERMISSION_DENIED", str(exc), 403)

    # 4. Per-user rate limit (IMP-BE-07)
    try:
        check_rate_limit(
            db,
            caller_uid,
            "add_own_word",
            limit=RATE_LIMIT_ADD_OWN_WORD,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )
    except RateLimitExceeded as exc:
        return callable_error("RESOURCE_EXHAUSTED", str(exc), 429)

    # 5. Create the word card. (BE-12: PUBLIC_ASSETS_BUCKET is guarded and any
    # failure to resolve it is raised *inside* this try/except, so it produces
    # a proper Callable error response instead of a raw, unhandled KeyError.)
    try:
        assets_bucket = os.environ.get("PUBLIC_ASSETS_BUCKET")
        if not assets_bucket:
            raise RuntimeError("PUBLIC_ASSETS_BUCKET environment variable is not configured.")
        result = create_own_word(
            raw_input=text,
            user_id=caller_uid,
            chapter_id=chapter_id,
            book_id=book_id,
            assets_bucket=assets_bucket,
        )
    except ValueError as exc:
        logger.warning("Own-word creation failed for user '%s': %s", caller_uid, exc)
        return callable_error("INVALID_ARGUMENT", str(exc), 400)
    except RuntimeError as exc:
        logger.error("Own-word creation misconfigured for user '%s': %s", caller_uid, exc)
        return callable_error("INTERNAL", "Server is misconfigured. Please contact support.", 500)
    except Exception as exc:
        logger.exception("Own-word creation failed for user '%s': %s", caller_uid, exc)
        return callable_error("INTERNAL", "Failed to create word card. Please try again.", 500)

    # 6. Return the word card
    return callable_response(result)
