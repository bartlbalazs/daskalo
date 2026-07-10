"""Tests for fn_mark_onboarding_seen.py."""

from unittest.mock import patch

import fn_mark_onboarding_seen
from callable_helpers import RateLimitExceeded
from tests.conftest import make_flask_request

CALLER_UID = "user-123"


def test_mark_onboarding_seen_fn_happy_path():
    req = make_flask_request(body={"data": {"key": "howItWorks"}})

    with (
        patch("fn_mark_onboarding_seen.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_mark_onboarding_seen._get_db"),
        patch("fn_mark_onboarding_seen._init_firebase"),
        patch("fn_mark_onboarding_seen.ensure_active_user"),
        patch("fn_mark_onboarding_seen.check_rate_limit"),
        patch("fn_mark_onboarding_seen.mark_onboarding_seen", return_value={"key": "howItWorks", "alreadySeen": False}) as service,
    ):
        body, status, _headers = fn_mark_onboarding_seen.mark_onboarding_seen_fn(req)

    assert status == 200
    assert body["result"] == {"key": "howItWorks", "alreadySeen": False}
    service.assert_called_once_with(uid=CALLER_UID, key="howItWorks")


def test_mark_onboarding_seen_fn_rejects_unknown_key():
    req = make_flask_request(body={"data": {"key": "tour"}})

    with (
        patch("fn_mark_onboarding_seen.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_mark_onboarding_seen._init_firebase"),
    ):
        body, status, _headers = fn_mark_onboarding_seen.mark_onboarding_seen_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_mark_onboarding_seen_fn_inactive_user_rejected():
    req = make_flask_request(body={"data": {"key": "howItWorks"}})

    with (
        patch("fn_mark_onboarding_seen.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_mark_onboarding_seen._get_db"),
        patch("fn_mark_onboarding_seen._init_firebase"),
        patch("fn_mark_onboarding_seen.ensure_active_user", side_effect=PermissionError("not active")),
    ):
        body, status, _headers = fn_mark_onboarding_seen.mark_onboarding_seen_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


def test_mark_onboarding_seen_fn_rate_limited():
    req = make_flask_request(body={"data": {"key": "howItWorks"}})

    with (
        patch("fn_mark_onboarding_seen.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_mark_onboarding_seen._get_db"),
        patch("fn_mark_onboarding_seen._init_firebase"),
        patch("fn_mark_onboarding_seen.ensure_active_user"),
        patch("fn_mark_onboarding_seen.check_rate_limit", side_effect=RateLimitExceeded("too many calls")),
    ):
        body, status, _headers = fn_mark_onboarding_seen.mark_onboarding_seen_fn(req)

    assert status == 429
    assert body["error"]["status"] == "RESOURCE_EXHAUSTED"
