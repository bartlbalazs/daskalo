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
from datetime import UTC, datetime
from typing import Any

import flask
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from google.cloud import firestore as gc_firestore
from google.cloud.firestore import Client as FirestoreClient

from models.firestore import UserStatus

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
    except (FirebaseError, ValueError) as exc:
        # FirebaseError covers every exception firebase_admin.auth itself defines
        # for this call (InvalidIdTokenError, ExpiredIdTokenError, RevokedIdTokenError,
        # CertificateFetchError, UserDisabledError, ...) — i.e. "this token is bad" or
        # "we couldn't fetch the certs to check it", both legitimately 401s.
        # ValueError covers verify_id_token's own guard for a malformed id_token string.
        # Anything else is a genuinely unexpected bug and is left to propagate so the
        # caller's own handler surfaces it as a 500, per BE-17 — we don't want to
        # silently relabel unrelated failures as "invalid token".
        logger.warning("Firebase ID token verification failed: %s", exc)
        raise PermissionError("Invalid or expired Firebase ID token.") from exc

    return decoded


# ---------------------------------------------------------------------------
# Active-user gate (BE-05 / IMP-BE-06)
# ---------------------------------------------------------------------------


def ensure_active_user(db: FirestoreClient, uid: str) -> None:
    """
    Raise PermissionError unless ``users/{uid}.status == "active"``.

    Must be called after ``verify_firebase_token()`` succeeds and before any
    billable work (Gemini/STT/TTS/GCS). The Admin SDK bypasses Firestore
    security rules, so a `pending` (unapproved) user with a valid Firebase ID
    token could otherwise still trigger paid backend work — this check is the
    only thing standing in the way.
    """
    user_snap = db.collection("users").document(uid).get()
    if not user_snap.exists:
        raise PermissionError(f"User '{uid}' does not have an account.")

    status = (user_snap.to_dict() or {}).get("status")
    if status != UserStatus.active.value:
        raise PermissionError(f"User '{uid}' is not active (status={status!r}).")


# ---------------------------------------------------------------------------
# Precondition failures (BE-06)
# ---------------------------------------------------------------------------


class PreconditionFailedError(Exception):
    """
    Raised by service-layer functions when a required precondition isn't met
    (e.g. no exercise attempted yet). Callers should map this to a 400
    FAILED_PRECONDITION Callable error.
    """


# ---------------------------------------------------------------------------
# Rate limiting (IMP-BE-07)
# ---------------------------------------------------------------------------


class RateLimitExceeded(Exception):
    """Raised by check_rate_limit() when a caller exceeds their per-user, per-function quota."""


def check_rate_limit(db: FirestoreClient, uid: str, fn_name: str, limit: int, window_seconds: int) -> None:
    """
    Enforce a per-user, per-function sliding-window rate limit.

    Defense-in-depth *underneath* the existing per-project API Gateway quota
    (which is shared across every user — see BUGS.md#BE-15). Backed by a
    Firestore counter document at ``rate_limits/{uid}_{fn_name}``:
    ``{count, windowStart}``. This is a simple fixed window (resets once
    ``window_seconds`` have elapsed since ``windowStart``), not a true sliding
    log, which is sufficient for a coarse per-user throttle.

    The read-check-increment is performed inside a Firestore transaction so
    concurrent calls from the same user can't both slip through under the limit.

    Raises RateLimitExceeded if the caller has already made ``limit`` calls
    within the current window.
    """
    doc_ref = db.collection("rate_limits").document(f"{uid}_{fn_name}")
    transaction = db.transaction()

    @gc_firestore.transactional
    def _check_and_increment(transaction: gc_firestore.Transaction) -> None:
        snap = doc_ref.get(transaction=transaction)
        now = datetime.now(UTC)

        if snap.exists:
            existing = snap.to_dict() or {}
            window_start = existing.get("windowStart")
            count = existing.get("count", 0)
            window_active = window_start is not None and (now - window_start).total_seconds() < window_seconds
            if window_active:
                if count >= limit:
                    raise RateLimitExceeded(
                        f"Rate limit exceeded for '{fn_name}': max {limit} calls "
                        f"per {window_seconds}s. Please slow down and try again shortly."
                    )
                transaction.update(doc_ref, {"count": count + 1})
                return

        # No existing doc, or the previous window has expired — start a fresh one.
        transaction.set(doc_ref, {"count": 1, "windowStart": now})

    _check_and_increment(transaction)


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
