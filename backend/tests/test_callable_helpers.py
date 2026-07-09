"""
Tests for callable_helpers.py — Firebase Callable wire protocol helpers.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from firebase_admin.auth import InvalidIdTokenError

from callable_helpers import (
    PreconditionFailedError,
    RateLimitExceeded,
    callable_error,
    callable_response,
    check_rate_limit,
    ensure_active_user,
    parse_callable_request,
    verify_firebase_token,
)
from tests.conftest import FakeTransaction, make_flask_request

# ---------------------------------------------------------------------------
# parse_callable_request
# ---------------------------------------------------------------------------


def test_parse_callable_request_returns_data():
    req = make_flask_request(body={"data": {"attemptId": "abc"}})
    result = parse_callable_request(req)
    assert result == {"attemptId": "abc"}


def test_parse_callable_request_raises_on_missing_json():
    req = make_flask_request(body=None)
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_callable_request(req)


def test_parse_callable_request_raises_on_missing_data_key():
    req = make_flask_request(body={"other": "stuff"})
    with pytest.raises(ValueError, match="Missing 'data'"):
        parse_callable_request(req)


def test_parse_callable_request_raises_if_data_not_dict():
    req = make_flask_request(body={"data": "string-not-dict"})
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_callable_request(req)


# ---------------------------------------------------------------------------
# verify_firebase_token
# ---------------------------------------------------------------------------


def test_verify_firebase_token_returns_decoded_token():
    req = make_flask_request(auth_header="Bearer valid-token")
    decoded = {"uid": "user-123", "email": "test@example.com"}

    with patch("callable_helpers.auth.verify_id_token", return_value=decoded):
        result = verify_firebase_token(req)

    assert result["uid"] == "user-123"


def test_verify_firebase_token_raises_on_missing_header():
    req = make_flask_request(auth_header="")
    with pytest.raises(PermissionError, match="Firebase ID token not found"):
        verify_firebase_token(req)


def test_verify_firebase_token_raises_on_invalid_token():
    """BE-17: a FirebaseError-family exception (bad/expired token) maps to PermissionError."""
    req = make_flask_request(auth_header="Bearer bad-token")

    with patch("callable_helpers.auth.verify_id_token", side_effect=InvalidIdTokenError("bad token")):
        with pytest.raises(PermissionError, match="Invalid or expired"):
            verify_firebase_token(req)


def test_verify_firebase_token_lets_unexpected_exceptions_propagate():
    """BE-17: a genuinely unexpected exception (not FirebaseError/ValueError) must NOT
    be silently relabeled as an auth failure — it should propagate untouched so the
    endpoint's own handler can surface it as a 500."""
    req = make_flask_request(auth_header="Bearer some-token")

    class _WeirdBug(RuntimeError):
        pass

    with patch("callable_helpers.auth.verify_id_token", side_effect=_WeirdBug("totally unrelated bug")):
        with pytest.raises(_WeirdBug):
            verify_firebase_token(req)


# ---------------------------------------------------------------------------
# ensure_active_user (BE-05 / IMP-BE-06)
# ---------------------------------------------------------------------------


def _make_user_db(status: str | None, exists: bool = True) -> MagicMock:
    db = MagicMock()
    snap = MagicMock(exists=exists)
    snap.to_dict.return_value = {"status": status} if exists else None
    db.collection.return_value.document.return_value.get.return_value = snap
    return db


def test_ensure_active_user_passes_for_active_user():
    db = _make_user_db(status="active")
    ensure_active_user(db, "user-123")  # must not raise


def test_ensure_active_user_raises_for_pending_user():
    db = _make_user_db(status="pending")
    with pytest.raises(PermissionError, match="not active"):
        ensure_active_user(db, "user-123")


def test_ensure_active_user_raises_when_user_doc_missing():
    db = _make_user_db(status=None, exists=False)
    with pytest.raises(PermissionError, match="does not have an account"):
        ensure_active_user(db, "user-123")


# ---------------------------------------------------------------------------
# check_rate_limit (IMP-BE-07)
# ---------------------------------------------------------------------------


def _make_rate_limit_db(existing_doc: dict | None) -> tuple[MagicMock, MagicMock]:
    db = MagicMock()
    doc_ref = MagicMock()
    snap = MagicMock(exists=existing_doc is not None)
    snap.to_dict.return_value = existing_doc
    doc_ref.get.return_value = snap
    db.collection.return_value.document.return_value = doc_ref
    db.transaction.return_value = FakeTransaction()
    return db, doc_ref


def test_check_rate_limit_allows_first_call_and_creates_window():
    db, doc_ref = _make_rate_limit_db(existing_doc=None)

    check_rate_limit(db, "user-123", "evaluate", limit=5, window_seconds=60)

    doc_ref.set.assert_called_once()
    written = doc_ref.set.call_args.args[0]
    assert written["count"] == 1


def test_check_rate_limit_increments_within_window():
    now = datetime.now(UTC)
    db, doc_ref = _make_rate_limit_db(existing_doc={"count": 2, "windowStart": now})

    check_rate_limit(db, "user-123", "evaluate", limit=5, window_seconds=60)

    doc_ref.update.assert_called_once_with({"count": 3})


def test_check_rate_limit_raises_when_limit_reached():
    now = datetime.now(UTC)
    db, doc_ref = _make_rate_limit_db(existing_doc={"count": 5, "windowStart": now})

    with pytest.raises(RateLimitExceeded, match="Rate limit exceeded"):
        check_rate_limit(db, "user-123", "evaluate", limit=5, window_seconds=60)

    doc_ref.update.assert_not_called()
    doc_ref.set.assert_not_called()


def test_check_rate_limit_resets_after_window_expires():
    stale_start = datetime.now(UTC) - timedelta(seconds=120)
    db, doc_ref = _make_rate_limit_db(existing_doc={"count": 5, "windowStart": stale_start})

    check_rate_limit(db, "user-123", "evaluate", limit=5, window_seconds=60)

    doc_ref.set.assert_called_once()
    written = doc_ref.set.call_args.args[0]
    assert written["count"] == 1
    doc_ref.update.assert_not_called()


# ---------------------------------------------------------------------------
# PreconditionFailedError — trivial marker exception (BE-06)
# ---------------------------------------------------------------------------


def test_precondition_failed_error_is_an_exception():
    with pytest.raises(PreconditionFailedError, match="no attempt"):
        raise PreconditionFailedError("no attempt found")


# ---------------------------------------------------------------------------
# callable_response / callable_error
# ---------------------------------------------------------------------------


def test_callable_response_wraps_result():
    body, status, _headers = callable_response({"score": 85})
    assert status == 200
    assert body == {"result": {"score": 85}}


def test_callable_error_wraps_error():
    body, status, _headers = callable_error("NOT_FOUND", "Attempt not found.", 404)
    assert status == 404
    assert body["error"]["status"] == "NOT_FOUND"
    assert body["error"]["message"] == "Attempt not found."
