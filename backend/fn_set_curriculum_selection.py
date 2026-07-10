"""Cloud Function entry point: set_curriculum_selection."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import firebase_admin
import flask
import functions_framework
from firebase_admin import credentials
from google.cloud.firestore import Client as FirestoreClient

import log_setup  # noqa: F401
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
from constants import RATE_LIMIT_SET_CURRICULUM_SELECTION, RATE_LIMIT_WINDOW_SECONDS
from services.curriculum_selection import set_curriculum_selection

logger = logging.getLogger(__name__)


def _init_firebase() -> None:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred = credentials.Certificate(cred_path) if cred_path else credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"projectId": os.getenv("GOOGLE_CLOUD_PROJECT")})


@lru_cache(maxsize=1)
def _get_db() -> FirestoreClient:
    return FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))


@functions_framework.http
def set_curriculum_selection_fn(request: flask.Request) -> tuple:
    """HTTP Cloud Function entry point for explicit curriculum selection changes."""
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
        curriculum_chapter_id = data["curriculumChapterId"]
        chapter_id = data["chapterId"]
        if not isinstance(curriculum_chapter_id, str) or not curriculum_chapter_id.strip():
            raise ValueError("curriculumChapterId must be a non-empty string.")
        if not isinstance(chapter_id, str) or not chapter_id.strip():
            raise ValueError("chapterId must be a non-empty string.")
    except (ValueError, KeyError) as exc:
        return callable_error("INVALID_ARGUMENT", str(exc), 400)

    db = _get_db()

    try:
        ensure_active_user(db, uid)
    except PermissionError as exc:
        return callable_error("PERMISSION_DENIED", str(exc), 403)

    try:
        check_rate_limit(
            db,
            uid,
            "set_curriculum_selection",
            limit=RATE_LIMIT_SET_CURRICULUM_SELECTION,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )
    except RateLimitExceeded as exc:
        return callable_error("RESOURCE_EXHAUSTED", str(exc), 429)

    try:
        result = set_curriculum_selection(
            uid=uid,
            curriculum_chapter_id=curriculum_chapter_id,
            chapter_id=chapter_id,
        )
    except PermissionError as exc:
        return callable_error("PERMISSION_DENIED", str(exc), 403)
    except ValueError as exc:
        return callable_error("INVALID_ARGUMENT", str(exc), 400)
    except Exception as exc:
        logger.exception("Error setting curriculum selection for user '%s': %s", uid, exc)
        return callable_error("INTERNAL", "Failed to update curriculum selection.", 500)

    return callable_response(
        {
            "curriculumChapterId": result["curriculum_chapter_id"],
            "chapterId": result["chapter_id"],
        }
    )
