"""
Integration tests for fn_evaluate.py — the Cloud Function entry point.

Strategy: mock Firestore, Firebase token verification, and the evaluation
service so we exercise the routing logic of the Cloud Function without
hitting any real infrastructure.
"""

import base64
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import fn_evaluate
from models.firestore import AttemptStatus, ExerciseType
from tests.conftest import make_flask_request

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
    return db


# ---------------------------------------------------------------------------
# Happy path — text-based exercise
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_happy_path():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})
    db = _make_db()

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate.firestore.client", return_value=db),
        patch("fn_evaluate.evaluate_attempt", return_value=EVAL_RESULT),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 200
    assert body["result"]["score"] == 80


# ---------------------------------------------------------------------------
# Happy path — pronunciation exercise with audioBase64
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_pronunciation_happy_path():
    audio_b64 = base64.b64encode(b"fake-audio").decode()
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID, "audioBase64": audio_b64}})

    pronunciation_doc = dict(ATTEMPT_DOC)
    pronunciation_doc["type"] = ExerciseType.pronunciation_practice.value
    chapter_doc = {"exercises": [{"prompt": "", "data": {"targetText": "γεια σου"}}]}
    db = _make_db(attempt_doc=pronunciation_doc, chapter_doc=chapter_doc)

    pronunciation_result = MagicMock(score=70, feedback="Good try!", isCorrect=False)
    pronunciation_result.model_dump.return_value = {"score": 70, "feedback": "Good try!", "isCorrect": False}

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate.firestore.client", return_value=db),
        patch("fn_evaluate.evaluate_pronunciation", return_value=pronunciation_result),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 200
    assert body["result"]["score"] == 70


# ---------------------------------------------------------------------------
# Auth / permission guards
# ---------------------------------------------------------------------------


def test_evaluate_attempt_fn_unauthenticated():
    req = make_flask_request(auth_header="")

    with (
        patch("fn_evaluate.verify_firebase_token", side_effect=PermissionError("No token")),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 401
    assert body["error"]["status"] == "UNAUTHENTICATED"


def test_evaluate_attempt_fn_wrong_owner():
    req = make_flask_request(body={"data": {"attemptId": ATTEMPT_ID}})

    other_user_doc = dict(ATTEMPT_DOC)
    other_user_doc["userId"] = "other-user-999"
    db = _make_db(attempt_doc=other_user_doc)

    with (
        patch("fn_evaluate.verify_firebase_token", return_value={"uid": CALLER_UID}),
        patch("fn_evaluate.firestore.client", return_value=db),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 403
    assert body["error"]["status"] == "PERMISSION_DENIED"


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
        patch("fn_evaluate.firestore.client", return_value=db),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 409
    assert body["error"]["status"] == "FAILED_PRECONDITION"


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
        patch("fn_evaluate.firestore.client", return_value=db),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status = fn_evaluate.evaluate_attempt_fn(req)

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
        patch("fn_evaluate.firestore.client", return_value=db),
        patch("fn_evaluate._init_firebase"),
    ):
        body, status = fn_evaluate.evaluate_attempt_fn(req)

    assert status == 400
    assert body["error"]["status"] == "INVALID_ARGUMENT"
