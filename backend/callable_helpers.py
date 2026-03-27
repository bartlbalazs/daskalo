"""
Firebase Callable Functions — wire protocol helpers.

The Firebase JS SDK's httpsCallable() wraps requests in this envelope:

  Request body:  { "data": { ...your args... } }
  Success body:  { "result": { ...your return value... } }
  Error body:    { "error": { "status": "UNAUTHENTICATED" | "INVALID_ARGUMENT" | ...,
                              "message": "..." } }

All functions receive a Flask/functions-framework Request object and must return
a (body_dict, status_code) tuple.

Auth: in production the Firebase ID token is sent in ``data.idToken`` inside
the request body, because the API Gateway replaces the ``Authorization`` header
with its own service-account JWT when proxying to Cloud Run.  In local dev
(no gateway) the token is still read from the ``Authorization: Bearer`` header
as a fallback.
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

    The ``idToken`` field is stripped from the returned dict — it is an
    auth-transport concern and should not leak into business logic.

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
    # Strip the auth token — it is consumed by verify_firebase_token(), not by
    # the business logic that receives this dict.
    data.pop("idToken", None)
    return data


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def verify_firebase_token(request: flask.Request) -> dict[str, Any]:
    """
    Extract and verify the Firebase ID token.

    Token source priority:
      1. Request body ``data.idToken`` — used in production where the API
         Gateway replaces the ``Authorization`` header with its own
         service-account JWT before proxying to Cloud Run.
      2. ``Authorization: Bearer <token>`` header — used in local dev where
         requests reach the function directly without a gateway.

    Returns the decoded token claims dict (includes 'uid', 'email', etc.).
    Raises PermissionError if the token is missing, malformed, or invalid.
    """
    # 1. Try the request body first (production path via API Gateway).
    id_token: str | None = None
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, dict):
            id_token = data.get("idToken") or None

    # 2. Fall back to the Authorization header (local dev / direct calls).
    if not id_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            id_token = auth_header.removeprefix("Bearer ").strip() or None

    if not id_token:
        raise PermissionError("Firebase ID token not found in request body (data.idToken) or Authorization header.")

    try:
        decoded = auth.verify_id_token(id_token)
    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", exc)
        raise PermissionError("Invalid or expired Firebase ID token.") from exc

    return decoded


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Allowed origins could be locked down to the Firebase Hosting domain in
# future, but "*" is fine for a public learning app that uses token-based auth
# (no cookies) and sends credentials in the request body, not the header.
_CORS_HEADERS: dict[str, str] = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "3600",
}


def cors_preflight() -> tuple[str, int, dict[str, str]]:
    """Return an empty 204 response with CORS headers for OPTIONS preflight."""
    return ("", 204, _CORS_HEADERS)


# ---------------------------------------------------------------------------
# Response formatting
# ---------------------------------------------------------------------------


def callable_response(result: Any) -> tuple[dict, int, dict[str, str]]:
    """Wrap a successful result in the Callable response envelope."""
    return {"result": result}, 200, _CORS_HEADERS


def callable_error(status: str, message: str, http_code: int = 500) -> tuple[dict, int, dict[str, str]]:
    """
    Wrap an error in the Callable error envelope.

    `status` should be a Firebase Functions error code string, e.g.:
      "UNAUTHENTICATED", "INVALID_ARGUMENT", "NOT_FOUND", "INTERNAL"
    """
    return {"error": {"status": status, "message": message}}, http_code, _CORS_HEADERS
