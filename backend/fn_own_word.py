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
  3. Checks for an existing own-word document (skip silently if duplicate).
  4. Calls the own_word service to normalise, generate TTS, upload to GCS, and save to Firestore.
  5. Returns the word card data to the caller.
"""

from __future__ import annotations

import logging
import os

import firebase_admin
import flask
import functions_framework
from firebase_admin import credentials
from google.cloud.firestore import Client as FirestoreClient

import log_setup  # noqa: F401 — configures root logger for Cloud Logging
from callable_helpers import (
    callable_error,
    callable_response,
    cors_preflight,
    parse_callable_request,
    verify_firebase_token,
)
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

    # 3. Check for duplicate — skip silently if already exists
    try:
        db = FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))
        # We use the raw text as a preliminary check key; the service will use the
        # normalised Greek for the actual document ID. We do a best-effort check here.
        own_words_ref = db.collection("users").document(caller_uid).collection("ownWords")
        existing_snap = own_words_ref.where("chapterId", "==", chapter_id).stream()
        existing_words = [doc.to_dict().get("greek", "").lower() for doc in existing_snap]
        if text.lower() in existing_words:
            logger.info("Duplicate own-word '%s' skipped for user '%s'", text, caller_uid)
            # Find and return the existing document
            for doc in own_words_ref.where("chapterId", "==", chapter_id).stream():
                d = doc.to_dict()
                if d.get("greek", "").lower() == text.lower():
                    return callable_response(
                        {
                            "greek": d.get("greek", ""),
                            "english": d.get("english", ""),
                            "audioUrl": d.get("audioUrl", ""),
                            "chapterId": d.get("chapterId", ""),
                            "bookId": d.get("bookId", ""),
                            "docId": doc.id,
                            "alreadyExisted": True,
                            "createdAt": d.get("createdAt", ""),
                        }
                    )
    except Exception as exc:
        logger.warning("Duplicate check failed, proceeding: %s", exc)

    # 4. Create the word card
    assets_bucket = os.environ["PUBLIC_ASSETS_BUCKET"]
    try:
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
    except Exception as exc:
        logger.exception("Own-word creation failed for user '%s': %s", caller_uid, exc)
        return callable_error("INTERNAL", "Failed to create word card. Please try again.", 500)

    # 5. Return the word card
    return callable_response(result)
