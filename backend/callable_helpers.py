"""
Firebase Callable Functions — wire protocol helpers.

The Firebase JS SDK's httpsCallable() wraps requests in this envelope:

  Request body:  { "data": { ...your args... } }
  Success body:  { "result": { ...your return value... } }
  Error body:    { "error": { "status": "UNAUTHENTICATED" | "INVALID_ARGUMENT" | ...,
                              "message": "..." } }

All functions receive a Flask/functions-framework Request object and must return
a (body_dict, status_code) tuple.

Auth: the Firebase JS SDK sends the Firebase ID token in the Authorization header
as  "Bearer <id_token>".  We verify it here with the Firebase Admin SDK.
"""

from __future__ import annotations

import logging
from typing import Any

import flask
from firebase_admin import auth

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------


def parse_callable_request(request: flask.Request) -> dict[str, Any]:
    """
    Parse the Callable request envelope and return the inner `data` dict.
    Raises ValueError with a descriptive message on malformed input.
    """
    body = request.get_json(silent=True)
    if body is None:
        raise ValueError("Request body is not valid JSON.")
    if "data" not in body:
        raise ValueError("Missing 'data' key in request body.")
    data = body["data"]
    if not isinstance(data, dict):
        raise ValueError("'data' must be a JSON object.")
    return data


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def verify_firebase_token(request: flask.Request) -> dict[str, Any]:
    """
    Extract and verify the Firebase ID token from the Authorization header.

    Returns the decoded token claims dict (includes 'uid', 'email', etc.).
    Raises PermissionError if the token is missing, malformed, or invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise PermissionError("Missing or malformed Authorization header.")

    id_token = auth_header.removeprefix("Bearer ").strip()
    if not id_token:
        raise PermissionError("Empty ID token in Authorization header.")

    try:
        decoded = auth.verify_id_token(id_token)
    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", exc)
        raise PermissionError("Invalid or expired Firebase ID token.") from exc

    return decoded


# ---------------------------------------------------------------------------
# Response formatting
# ---------------------------------------------------------------------------


def callable_response(result: Any) -> tuple[dict, int]:
    """Wrap a successful result in the Callable response envelope."""
    return {"result": result}, 200


def callable_error(status: str, message: str, http_code: int = 500) -> tuple[dict, int]:
    """
    Wrap an error in the Callable error envelope.

    `status` should be a Firebase Functions error code string, e.g.:
      "UNAUTHENTICATED", "INVALID_ARGUMENT", "NOT_FOUND", "INTERNAL"
    """
    return {"error": {"status": status, "message": message}}, http_code
