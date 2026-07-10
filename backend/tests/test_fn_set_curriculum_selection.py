"""Tests for fn_set_curriculum_selection.py."""

from unittest.mock import patch

import fn_set_curriculum_selection
from callable_helpers import RateLimitExceeded
from tests.conftest import make_flask_request

CALLER_UID = "user-123"
CURRICULUM_CHAPTER_ID = "b1_c1"
CHAPTER_ID = "b1_c1_airport"


def test_set_curriculum_selection_fn_happy_path():
    req = make_flask_request(body={"data": {"curriculumChapterId": CURRICULUM_CHAPTER_ID, "chapterId": CHAPTER_ID}})

    with (
        patch("fn_set_curriculum_selection.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_set_curriculum_selection._get_db"),
        patch("fn_set_curriculum_selection._init_firebase"),
        patch("fn_set_curriculum_selection.ensure_active_user"),
        patch("fn_set_curriculum_selection.check_rate_limit"),
        patch(
            "fn_set_curriculum_selection.set_curriculum_selection",
            return_value={"curriculum_chapter_id": CURRICULUM_CHAPTER_ID, "chapter_id": CHAPTER_ID},
        ) as service,
    ):
        body, status, _headers = fn_set_curriculum_selection.set_curriculum_selection_fn(req)

    assert status == 200
    assert body["result"] == {"curriculumChapterId": CURRICULUM_CHAPTER_ID, "chapterId": CHAPTER_ID}
    service.assert_called_once_with(uid=CALLER_UID, curriculum_chapter_id=CURRICULUM_CHAPTER_ID, chapter_id=CHAPTER_ID)


def test_set_curriculum_selection_fn_rejects_non_string_ids():
    req = make_flask_request(body={"data": {"curriculumChapterId": CURRICULUM_CHAPTER_ID, "chapterId": None}})

    with (
        patch("fn_set_curriculum_selection.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_set_curriculum_selection._init_firebase"),
    ):
        body, status, _headers = fn_set_curriculum_selection.set_curriculum_selection_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_set_curriculum_selection_fn_inactive_user_rejected():
    req = make_flask_request(body={"data": {"curriculumChapterId": CURRICULUM_CHAPTER_ID, "chapterId": CHAPTER_ID}})

    with (
        patch("fn_set_curriculum_selection.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_set_curriculum_selection._get_db"),
        patch("fn_set_curriculum_selection._init_firebase"),
        patch("fn_set_curriculum_selection.ensure_active_user", side_effect=PermissionError("not active")),
    ):
        body, status, _headers = fn_set_curriculum_selection.set_curriculum_selection_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


def test_set_curriculum_selection_fn_rate_limited():
    req = make_flask_request(body={"data": {"curriculumChapterId": CURRICULUM_CHAPTER_ID, "chapterId": CHAPTER_ID}})

    with (
        patch("fn_set_curriculum_selection.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_set_curriculum_selection._get_db"),
        patch("fn_set_curriculum_selection._init_firebase"),
        patch("fn_set_curriculum_selection.ensure_active_user"),
        patch("fn_set_curriculum_selection.check_rate_limit", side_effect=RateLimitExceeded("too many calls")),
    ):
        body, status, _headers = fn_set_curriculum_selection.set_curriculum_selection_fn(req)

    assert status == 429
    assert body["error"]["status"] == "RESOURCE_EXHAUSTED"


def test_set_curriculum_selection_fn_hidden_unselected_rejected():
    req = make_flask_request(body={"data": {"curriculumChapterId": CURRICULUM_CHAPTER_ID, "chapterId": CHAPTER_ID}})

    with (
        patch("fn_set_curriculum_selection.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_set_curriculum_selection._get_db"),
        patch("fn_set_curriculum_selection._init_firebase"),
        patch("fn_set_curriculum_selection.ensure_active_user"),
        patch("fn_set_curriculum_selection.check_rate_limit"),
        patch("fn_set_curriculum_selection.set_curriculum_selection", side_effect=PermissionError("not selectable")),
    ):
        body, status, _headers = fn_set_curriculum_selection.set_curriculum_selection_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"
