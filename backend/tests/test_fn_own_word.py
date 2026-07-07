"""
Integration tests for fn_own_word.py — the Cloud Function entry point.

Strategy: mock Firebase token verification and services.own_word.create_own_word
so we exercise only the routing/auth/rate-limit/validation logic of the Cloud
Function. There is deliberately no "duplicate check" test here — BE-13 removed
that (ineffective) pre-check; see services/own_word.py for the dedup story.
"""

from unittest.mock import patch

import fn_own_word
from callable_helpers import RateLimitExceeded
from tests.conftest import make_flask_request

CALLER_UID = "user-123"

SUCCESS_RESULT = {
    "greek": "ο δάσκαλος",
    "english": "the teacher",
    "audioUrl": "gs://bucket/users/user-123/own_words/chapter__ο_δάσκαλος.mp3",
    "chapterId": "chapter-xyz",
    "bookId": "b1",
    "docId": "chapter-xyz__ο_δάσκαλος",
    "alreadyExisted": False,
    "createdAt": "2026-01-01T00:00:00+00:00",
}


def _valid_body():
    return {"data": {"text": "δασκαλος", "chapterId": "chapter-xyz", "bookId": "b1"}}


def test_add_own_word_fn_happy_path():
    req = make_flask_request(body=_valid_body())

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._get_db"),
        patch("fn_own_word._init_firebase"),
        patch("fn_own_word.ensure_active_user"),
        patch("fn_own_word.check_rate_limit"),
        patch("fn_own_word.create_own_word", return_value=SUCCESS_RESULT),
        patch.dict("os.environ", {"PUBLIC_ASSETS_BUCKET": "demo-daskalo-assets"}),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 200
    assert body["result"] == SUCCESS_RESULT


def test_add_own_word_fn_unauthenticated():
    req = make_flask_request(auth_header="")

    with (
        patch("fn_own_word.verify_firebase_token", side_effect=PermissionError("No token")),
        patch("fn_own_word._init_firebase"),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 401
    assert body["error"]["status"] == "UNAUTHENTICATED"


def test_add_own_word_fn_missing_text():
    req = make_flask_request(body={"data": {"chapterId": "chapter-xyz", "bookId": "b1"}})

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._init_firebase"),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_add_own_word_fn_text_too_long():
    req = make_flask_request(body={"data": {"text": "α" * 51, "chapterId": "chapter-xyz", "bookId": "b1"}})

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._init_firebase"),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_add_own_word_fn_missing_chapter_id():
    req = make_flask_request(body={"data": {"text": "δασκαλος", "bookId": "b1"}})

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._init_firebase"),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_add_own_word_fn_missing_book_id():
    req = make_flask_request(body={"data": {"text": "δασκαλος", "chapterId": "chapter-xyz"}})

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._init_firebase"),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


# ---------------------------------------------------------------------------
# BE-05: active-user gate
# ---------------------------------------------------------------------------


def test_add_own_word_fn_inactive_user_rejected():
    req = make_flask_request(body=_valid_body())

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._get_db"),
        patch("fn_own_word._init_firebase"),
        patch("fn_own_word.ensure_active_user", side_effect=PermissionError("not active")),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# IMP-BE-07: rate limiting
# ---------------------------------------------------------------------------


def test_add_own_word_fn_rate_limited():
    req = make_flask_request(body=_valid_body())

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._get_db"),
        patch("fn_own_word._init_firebase"),
        patch("fn_own_word.ensure_active_user"),
        patch("fn_own_word.check_rate_limit", side_effect=RateLimitExceeded("too many calls")),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 429
    assert body["error"]["status"] == "RESOURCE_EXHAUSTED"


# ---------------------------------------------------------------------------
# BE-12: missing PUBLIC_ASSETS_BUCKET must produce a Callable error, not a raw 500
# ---------------------------------------------------------------------------


def test_add_own_word_fn_missing_assets_bucket_env_var():
    req = make_flask_request(body=_valid_body())

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._get_db"),
        patch("fn_own_word._init_firebase"),
        patch("fn_own_word.ensure_active_user"),
        patch("fn_own_word.check_rate_limit"),
        patch.dict("os.environ", {}, clear=False),
    ):
        # Ensure the var really is absent for this test, regardless of the ambient environment.
        import os as _os

        _os.environ.pop("PUBLIC_ASSETS_BUCKET", None)
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 500
    assert body["error"]["status"] == "INTERNAL"
    # And it must be a well-formed Callable envelope (not a raw framework 500).
    assert "message" in body["error"]


# ---------------------------------------------------------------------------
# Own-word creation failures
# ---------------------------------------------------------------------------


def test_add_own_word_fn_creation_value_error():
    req = make_flask_request(body=_valid_body())

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._get_db"),
        patch("fn_own_word._init_firebase"),
        patch("fn_own_word.ensure_active_user"),
        patch("fn_own_word.check_rate_limit"),
        patch("fn_own_word.create_own_word", side_effect=ValueError("not Greek")),
        patch.dict("os.environ", {"PUBLIC_ASSETS_BUCKET": "demo-daskalo-assets"}),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


def test_add_own_word_fn_creation_unexpected_error():
    req = make_flask_request(body=_valid_body())

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._get_db"),
        patch("fn_own_word._init_firebase"),
        patch("fn_own_word.ensure_active_user"),
        patch("fn_own_word.check_rate_limit"),
        patch("fn_own_word.create_own_word", side_effect=RuntimeError("boom")),
        patch.dict("os.environ", {"PUBLIC_ASSETS_BUCKET": "demo-daskalo-assets"}),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 500
    assert body["error"]["status"] == "INTERNAL"


def test_add_own_word_fn_gemini_failure_is_not_mislabeled_as_misconfigured():
    """Regression test: a Gemini call exhausting its retries (GeminiCallFailed,
    surfaced from services/gemini_utils.py through create_own_word) must NOT be
    mistaken for the unrelated "PUBLIC_ASSETS_BUCKET missing" RuntimeError case —
    each needs its own distinct exception type so the two failure causes are
    never confused (see services/gemini_utils.py's GeminiCallFailed docstring)."""
    from services.gemini_utils import GeminiCallFailed

    req = make_flask_request(body=_valid_body())

    with (
        patch("fn_own_word.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_own_word._get_db"),
        patch("fn_own_word._init_firebase"),
        patch("fn_own_word.ensure_active_user"),
        patch("fn_own_word.check_rate_limit"),
        patch("fn_own_word.create_own_word", side_effect=GeminiCallFailed("Gemini call failed after retries.")),
        patch.dict("os.environ", {"PUBLIC_ASSETS_BUCKET": "demo-daskalo-assets"}),
    ):
        body, status, _headers = fn_own_word.add_own_word_fn(req)

    assert status == 500
    assert body["error"]["status"] == "INTERNAL"
    # Must get the generic "try again" message, NOT the "misconfigured" one.
    assert "try again" in body["error"]["message"].lower()
    assert "misconfigured" not in body["error"]["message"].lower()
