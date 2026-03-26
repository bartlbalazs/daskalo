"""
Tests for callable_helpers.py — Firebase Callable wire protocol helpers.
"""

from unittest.mock import MagicMock, patch

import pytest

from callable_helpers import (
    callable_error,
    callable_response,
    parse_callable_request,
    verify_firebase_token,
)
from tests.conftest import make_flask_request


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
    with pytest.raises(PermissionError, match="Missing or malformed"):
        verify_firebase_token(req)


def test_verify_firebase_token_raises_on_invalid_token():
    req = make_flask_request(auth_header="Bearer bad-token")

    with patch("callable_helpers.auth.verify_id_token", side_effect=Exception("expired")):
        with pytest.raises(PermissionError, match="Invalid or expired"):
            verify_firebase_token(req)


# ---------------------------------------------------------------------------
# callable_response / callable_error
# ---------------------------------------------------------------------------


def test_callable_response_wraps_result():
    body, status = callable_response({"score": 85})
    assert status == 200
    assert body == {"result": {"score": 85}}


def test_callable_error_wraps_error():
    body, status = callable_error("NOT_FOUND", "Attempt not found.", 404)
    assert status == 404
    assert body["error"]["status"] == "NOT_FOUND"
    assert body["error"]["message"] == "Attempt not found."
