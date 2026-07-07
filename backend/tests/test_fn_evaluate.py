"""
Integration tests for fn_evaluate.py — the Cloud Function entry point.

Strategy: mock Firestore, Firebase token verification, and the evaluation
service so we exercise the routing logic of the Cloud Function without
hitting any real infrastructure.
"""

import base64
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import fn_evaluate
from models.firestore import AttemptStatus, ExerciseType
from tests.conftest import FakeTransaction, make_flask_request

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

CALLER_UID = "user-123"
ATTEMPT_ID = "attempt-abc"
CHAPTER_ID = "chapter-xyz"

ATTEMPT_DOC = {
    "userId": CALLER_UID,
    "chapterId": CHAPTER_ID,
    "exerciseId": "ex_0",
    "type": ExerciseType.translation_challenge.value,
    "submittedAt": datetime(2026, 1, 1, 12, 0, 0),
    "payload": {"text": "Γεια σου κόσμε"},
    "status": AttemptStatus.pending.value,
    "evaluation": None,
}

CHAPTER_DOC = {
    "exercises": [
        {"prompt": "Translate: Hello world", "data": {}},
    ]
}

EVAL_RESULT = MagicMock(score=80, feedback="Well done!", isCorrect=True)
EVAL_RESULT.model_dump.return_value = {"score": 80, "feedback": "Well done!", "isCorrect": True}


# ---------------------------------------------------------------------------
# Helper: build a fully-wired Firestore mock
# ---------------------------------------------------------------------------


def _make_db(attempt_doc: dict = ATTEMPT_DOC, chapter_doc: dict = CHAPTER_DOC):
    db = MagicMock()

    # exercise_attempts/{attemptId}
    attempt_snap = MagicMock(exists=True)
    attempt_snap.to_dict.return_value = dict(attempt_doc)
    attempt_ref = MagicMock()
    attempt_ref.get.return_value = attempt_snap

    # chapters/{chapterId}
    chapter_snap = MagicMock(exists=True)
    chapter_snap.to_dict.return_value = dict(chapter_doc)
    chapter_ref = MagicMock()
    chapter_ref.get.return_value = chapter_snap

    def _collection(name):
        col = MagicMock()
        if name == "exercise_attempts":
            col.document.return_value = attempt_ref
        elif name == "chapters":
            col.document.return_value = chapter_ref
        return col

    db.collection.side_effect = _collection
    db.transaction.side_effect = lambda: FakeTransaction()
    return db


# ---------------------------------------------------------------------------
# Happy path — text-based exercise
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_happy_path():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    db = _make_db()

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate.evaluate_attempt", return_value=EVAL_RESULT),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 200
    assert body["result"]["score"] == 80

    # The attempt must have been transitioned evaluating -> completed.
    attempt_ref = db.collection("exercise_attempts").document(ATTEMPT_ID)
    update_calls = [c.args[0] for c in attempt_ref.update.call_args_list]
    assert {"status": AttemptStatus.completed.value, "evaluation": EVAL_RESULT.model_dump.return_value} in update_calls


# ---------------------------------------------------------------------------
# Happy path — pronunciation exercise with audioBase64
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_pronunciation_happy_path():
    audio_b64 = base64.b64encode(b"fake-audio").decode()
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID, "audioBase64": audio_b64}})

    pronunciation_doc = dict(ATTEMPT_DOC)
    pronunciation_doc["type"] = ExerciseType.pronunciation_practice.value
    # BE-18: production reads exercise_data["data"]["target_text"] (snake_case).
    chapter_doc = {"exercises": [{"prompt": "", "data": {"target_text": "γεια σου"}}]}
    db = _make_db(attempt_doc=pronunciation_doc, chapter_doc=chapter_doc)

    pronunciation_result = MagicMock(score=70, feedback="Good try!", isCorrect=False)
    pronunciation_result.model_dump.return_value = {"score": 70, "feedback": "Good try!", "isCorrect": False}

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate.evaluate_pronunciation", return_value=pronunciation_result) as mock_eval_pron,
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 200
    assert body["result"]["score"] == 70
    # Regression test for BE-18: target_text must actually reach evaluate_pronunciation.
    mock_eval_pron.assert_called_once()
    assert mock_eval_pron.call_args.args[1] == "γεια σου"


# ---------------------------------------------------------------------------
# Auth / permission guards
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_unauthenticated():
    req = make_flask_request(auth_header="")

    with (
        patch("fn_evaluate.verify_firebase_token", side_effect=PermissionError("No token")),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 401
    assert body["error"]["status"] == "UNAUTHENTICATED"


def test_evaluate_attempt_fn_wrong_owner():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})

    other_user_doc = dict(ATTEMPT_DOC)
    other_user_doc["userId"] = "other-user-999"
    db = _make_db(attempt_doc=other_user_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# BE-05: active-user gate
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_inactive_user_rejected():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    db = _make_db()

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user", side_effect=PermissionError("User is not active.")),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# IMP-BE-07: rate limiting
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_rate_limited():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    db = _make_db()

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch(
            "fn_evaluate.check_rate_limit",
            side_effect=fn_evaluate.RateLimitExceeded("Rate limit exceeded for 'evaluate'."),
        ),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 429
    assert body["error"]["status"] == "RESOURCE_EXHAUSTED"


# ---------------------------------------------------------------------------
# State guard — attempt already evaluated
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_attempt_not_pending():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})

    completed_doc = dict(ATTEMPT_DOC)
    completed_doc["status"] = AttemptStatus.completed.value
    db = _make_db(attempt_doc=completed_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 409
    assert body["error"]["status"] == "FAILED_PRECONDITION"


# ---------------------------------------------------------------------------
# BE-02/BE-03/IMP-BE-05: transactional claim + stale "evaluating" reclaim
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_rejects_fresh_evaluating_attempt():
    """A recently-claimed 'evaluating' attempt (not yet stale) must be rejected — this
    is the concurrency guard that BE-02 requires."""
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})

    evaluating_doc = dict(ATTEMPT_DOC)
    evaluating_doc["status"] = AttemptStatus.evaluating.value
    evaluating_doc["evaluatingSince"] = datetime.now(UTC) - timedelta(seconds=5)
    db = _make_db(attempt_doc=evaluating_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 409
    assert body["error"]["status"] == "FAILED_PRECONDITION"


def test_evaluate_attempt_fn_reclaims_stale_evaluating_attempt():
    """IMP-BE-05: an attempt stuck 'evaluating' past the staleness threshold can be
    reclaimed and evaluated rather than being a permanent dead end (BE-03)."""
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})

    stale_doc = dict(ATTEMPT_DOC)
    stale_doc["status"] = AttemptStatus.evaluating.value
    stale_doc["evaluatingSince"] = datetime.now(UTC) - timedelta(seconds=999)
    db = _make_db(attempt_doc=stale_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate.evaluate_attempt", return_value=EVAL_RESULT),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 200
    assert body["result"]["score"] == 80


# ---------------------------------------------------------------------------
# Non-AI-graded exercise type rejected
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_non_ai_type_rejected():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})

    non_ai_doc = dict(ATTEMPT_DOC)
    non_ai_doc["type"] = ExerciseType.word_scramble.value
    db = _make_db(attempt_doc=non_ai_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"


# ---------------------------------------------------------------------------
# Pronunciation without audioBase64 rejected (cost guard at function level)
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_pronunciation_missing_audio():
    """Pronunciation attempt without audioBase64 must be rejected — prevents
    a broken invocation from reaching STT/Gemini and incurring cost."""
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})  # no audioBase64

    pronunciation_doc = dict(ATTEMPT_DOC)
    pronunciation_doc["type"] = ExerciseType.pronunciation_practice.value
    db = _make_db(attempt_doc=pronunciation_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"

    # BE-02/BE-03: the doomed request must never have been marked "evaluating" —
    # validation happens before the state transition, so it isn't stuck.
    attempt_ref = db.collection("exercise_attempts").document(ATTEMPT_ID)
    attempt_ref.update.assert_not_called()


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_attempt_not_found():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    db = _make_db()
    db.collection("exercise_attempts").document(ATTEMPT_ID).get.return_value = MagicMock(exists=False)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 404
    assert body["error"]["status"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# BE-10: chapter/exercise validation
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_chapter_not_found():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    db = _make_db()
    db.collection("chapters").document(CHAPTER_ID).get.return_value = MagicMock(exists=False)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 404
    assert body["error"]["status"] == "NOT_FOUND"

    # The attempt must be marked "error", not left stuck "evaluating" (BE-03/BE-04).
    attempt_ref = db.collection("exercise_attempts").document(ATTEMPT_ID)
    update_calls = [c.args[0] for c in attempt_ref.update.call_args_list]
    assert {"status": AttemptStatus.error.value} in update_calls


def test_evaluate_attempt_fn_exercise_index_out_of_range():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    # CHAPTER_DOC only has 1 exercise (index 0); attempt references ex_0 today,
    # but simulate exerciseId pointing past the end of the array.
    out_of_range_doc = dict(ATTEMPT_DOC)
    out_of_range_doc["exerciseId"] = "ex_5"
    db = _make_db(attempt_doc=out_of_range_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"

    attempt_ref = db.collection("exercise_attempts").document(ATTEMPT_ID)
    update_calls = [c.args[0] for c in attempt_ref.update.call_args_list]
    assert {"status": AttemptStatus.error.value} in update_calls


# ---------------------------------------------------------------------------
# BE-04: a failure in the *final* write must still produce a well-formed
# Callable error response, not a raw 500.
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_final_write_failure_returns_callable_error():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    db = _make_db()
    attempt_ref = db.collection("exercise_attempts").document(ATTEMPT_ID)

    # First update() call is the transactional claim (via FakeTransaction.update),
    # the second is the final "completed" write — make that one blow up.
    attempt_ref.update.side_effect = [None, RuntimeError("Firestore write failed"), None]

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate._get_db", return_value=db),
        patch("fn_evaluate.evaluate_attempt", return_value=EVAL_RESULT),
        patch("fn_evaluate._init_firebase"),
        patch("fn_evaluate.ensure_active_user"),
        patch("fn_evaluate.check_rate_limit"),
    ):
        body, status, _headers = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 500
    assert body["error"]["status"] == "INTERNAL"
    # And CORS headers/envelope shape must still be present (well-formed, not raw).
    assert "error" in body and "message" in body["error"]
