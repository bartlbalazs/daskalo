"""
Integration tests for fn_complete_chapter.py — the Cloud Function entry point.

Strategy: mock Firebase token verification and services.progress.complete_chapter
so we exercise only the routing/auth/rate-limit logic of the Cloud Function.
"""

from unittest.mock import patch

import fn_complete_chapter
from callable_helpers import PreconditionFailedError, RateLimitExceeded
from tests.conftest import make_flask_request

CALLER_UID = "user-123"
CHAPTER_ID = "chapter-xyz"

SUCCESS_RESULT = {
    "chapter_id": CHAPTER_ID,
    "xp_gained": 150,
    "progress_summary": "Great work today.",
    "completed_chapter_ids": [CHAPTER_ID],
}


def test_complete_chapter_fn_happy_path():
    req = make_flask_request(body={"data": {"chapterId": CHAPTER_ID}})

    with (
        patch("fn_complete_chapter.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_chapter._get_db"),
        patch("fn_complete_chapter._init_firebase"),
        patch("fn_complete_chapter.ensure_active_user"),
        patch("fn_complete_chapter.check_rate_limit"),
        patch("fn_complete_chapter.complete_chapter", return_value=SUCCESS_RESULT),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 200
    assert body["result"] == {
        "chapterId": CHAPTER_ID,
        "xpGained": 150,
        "progressSummary": "Great work today.",
        "completedChapterIds": [CHAPTER_ID],
    }


def test_complete_chapter_fn_unauthenticated():
    req = make_flask_request(auth_header="")

    with (
        patch("fn_complete_chapter.verify_firebase_token", side_effect=PermissionError("No token")),
        patch("fn_complete_chapter._init_firebase"),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 401
    assert body["error"]["status"] == "UNAUTHENTICATED"


def test_complete_chapter_fn_missing_chapter_id():
    req = make_flask_request(body={"data": {}})

    with (
        patch("fn_complete_chapter.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_chapter._init_firebase"),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_complete_chapter_fn_inactive_user_rejected():
    req = make_flask_request(body={"data": {"chapterId": CHAPTER_ID}})

    with (
        patch("fn_complete_chapter.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_chapter._get_db"),
        patch("fn_complete_chapter._init_firebase"),
        patch("fn_complete_chapter.ensure_active_user", side_effect=PermissionError("not active")),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


def test_complete_chapter_fn_rate_limited():
    req = make_flask_request(body={"data": {"chapterId": CHAPTER_ID}})

    with (
        patch("fn_complete_chapter.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_chapter._get_db"),
        patch("fn_complete_chapter._init_firebase"),
        patch("fn_complete_chapter.ensure_active_user"),
        patch("fn_complete_chapter.check_rate_limit", side_effect=RateLimitExceeded("too many calls")),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 429
    assert body["error"]["status"] == "RESOURCE_EXHAUSTED"


def test_complete_chapter_fn_chapter_not_found():
    req = make_flask_request(body={"data": {"chapterId": CHAPTER_ID}})

    with (
        patch("fn_complete_chapter.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_chapter._get_db"),
        patch("fn_complete_chapter._init_firebase"),
        patch("fn_complete_chapter.ensure_active_user"),
        patch("fn_complete_chapter.check_rate_limit"),
        patch("fn_complete_chapter.complete_chapter", side_effect=ValueError("Chapter not found")),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 404
    assert body["error"]["status"] == "NOT_FOUND"


def test_complete_chapter_fn_no_attempt_precondition_failed():
    """BE-06: no completed exercise attempt yet -> 400 FAILED_PRECONDITION."""
    req = make_flask_request(body={"data": {"chapterId": CHAPTER_ID}})

    with (
        patch("fn_complete_chapter.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_chapter._get_db"),
        patch("fn_complete_chapter._init_firebase"),
        patch("fn_complete_chapter.ensure_active_user"),
        patch("fn_complete_chapter.check_rate_limit"),
        patch(
            "fn_complete_chapter.complete_chapter",
            side_effect=PreconditionFailedError("No completed exercise attempt found."),
        ),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 400
    assert body["error"]["status"] == "FAILED_PRECONDITION"


def test_complete_chapter_fn_unexpected_error_returns_500():
    req = make_flask_request(body={"data": {"chapterId": CHAPTER_ID}})

    with (
        patch("fn_complete_chapter.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_complete_chapter._get_db"),
        patch("fn_complete_chapter._init_firebase"),
        patch("fn_complete_chapter.ensure_active_user"),
        patch("fn_complete_chapter.check_rate_limit"),
        patch("fn_complete_chapter.complete_chapter", side_effect=RuntimeError("boom")),
    ):
        body, status, _headers = fn_complete_chapter.complete_chapter_fn(req)

    assert status == 500
    assert body["error"]["status"] == "INTERNAL"
