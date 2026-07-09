"""
Integration tests for fn_complete_practice.py — the Cloud Function entry point.

Strategy: mock Firebase token verification and services.practice_progress.complete_practice
so we exercise only the routing/auth/rate-limit logic of the Cloud Function.
"""

from unittest.mock import patch

import fn_complete_practice
from callable_helpers import RateLimitExceeded
from tests.conftest import make_flask_request

CALLER_UID = "user-123"
PRACTICE_SET_ID = "ps_p1_c1_airport_01"

SUCCESS_RESULT = {"practice_set_id": PRACTICE_SET_ID, "xp_gained": 175}


def test_complete_practice_fn_happy_path():
    req = make_flask_request(body={"data": {"practiceSetId": PRACTICE_SET_ID}})

    with (
        patch("fn_complete_practice.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_practice._get_db"),
        patch("fn_complete_practice._init_firebase"),
        patch("fn_complete_practice.ensure_active_user"),
        patch("fn_complete_practice.check_rate_limit"),
        patch("fn_complete_practice.complete_practice", return_value=SUCCESS_RESULT),
    ):
        body, status, _headers = fn_complete_practice.complete_practice_fn(req)

    assert status == 200
    assert body["result"] == {"practiceSetId": PRACTICE_SET_ID, "xpGained": 175}


def test_complete_practice_fn_unauthenticated():
    req = make_flask_request(auth_header="")

    with (
        patch("fn_complete_practice.verify_firebase_token", side_effect=PermissionError("No token")),
        patch("fn_complete_practice._init_firebase"),
    ):
        body, status, _headers = fn_complete_practice.complete_practice_fn(req)

    assert status == 401
    assert body["error"]["status"] == "UNAUTHENTICATED"


def test_complete_practice_fn_missing_practice_set_id():
    req = make_flask_request(body={"data": {}})

    with (
        patch("fn_complete_practice.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_practice._init_firebase"),
    ):
        body, status, _headers = fn_complete_practice.complete_practice_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_complete_practice_fn_inactive_user_rejected():
    req = make_flask_request(body={"data": {"practiceSetId": PRACTICE_SET_ID}})

    with (
        patch("fn_complete_practice.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_practice._get_db"),
        patch("fn_complete_practice._init_firebase"),
        patch("fn_complete_practice.ensure_active_user", side_effect=PermissionError("not active")),
    ):
        body, status, _headers = fn_complete_practice.complete_practice_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


def test_complete_practice_fn_rate_limited():
    req = make_flask_request(body={"data": {"practiceSetId": PRACTICE_SET_ID}})

    with (
        patch("fn_complete_practice.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_practice._get_db"),
        patch("fn_complete_practice._init_firebase"),
        patch("fn_complete_practice.ensure_active_user"),
        patch("fn_complete_practice.check_rate_limit", side_effect=RateLimitExceeded("too many calls")),
    ):
        body, status, _headers = fn_complete_practice.complete_practice_fn(req)

    assert status == 429
    assert body["error"]["status"] == "RESOURCE_EXHAUSTED"


def test_complete_practice_fn_not_found():
    req = make_flask_request(body={"data": {"practiceSetId": PRACTICE_SET_ID}})

    with (
        patch("fn_complete_practice.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_practice._get_db"),
        patch("fn_complete_practice._init_firebase"),
        patch("fn_complete_practice.ensure_active_user"),
        patch("fn_complete_practice.check_rate_limit"),
        patch("fn_complete_practice.complete_practice", side_effect=ValueError("Practice set not found")),
    ):
        body, status, _headers = fn_complete_practice.complete_practice_fn(req)

    assert status == 404
    assert body["error"]["status"] == "NOT_FOUND"


def test_complete_practice_fn_unexpected_error_returns_500():
    req = make_flask_request(body={"data": {"practiceSetId": PRACTICE_SET_ID}})

    with (
        patch("fn_complete_practice.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_practice._get_db"),
        patch("fn_complete_practice._init_firebase"),
        patch("fn_complete_practice.ensure_active_user"),
        patch("fn_complete_practice.check_rate_limit"),
        patch("fn_complete_practice.complete_practice", side_effect=RuntimeError("boom")),
    ):
        body, status, _headers = fn_complete_practice.complete_practice_fn(req)

    assert status == 500
    assert body["error"]["status"] == "INTERNAL"
