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
  2. Checks if the practice set is already completed (idempotent — returns 200 if so).
  3. Awards exactly 175 XP and adds the practiceSetId to completedPracticeSetIds.
  4. Returns { practiceSetId, xpGained }.
"""

from __future__ import annotations

import logging
import os

import firebase_admin
import flask
import functions_framework
from firebase_admin import credentials

import log_setup  # noqa: F401 — configures root logger for Cloud Logging
from callable_helpers import (
    callable_error,
    callable_response,
    cors_preflight,
    parse_callable_request,
    verify_firebase_token,
)
from services.practice_progress import complete_practice

logger = logging.getLogger(__name__)

PRACTICE_XP = 175


def _init_firebase() -> None:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred = credentials.Certificate(cred_path) if cred_path else credentials.ApplicationDefault()
    firebase_admin.initialize_app(
        cred,
        {"projectId": os.getenv("GOOGLE_CLOUD_PROJECT")},
    )


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
