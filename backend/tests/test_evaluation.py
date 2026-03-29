"""
Tests for services/evaluation.py — evaluate_attempt and evaluate_pronunciation.

Key goals:
- Happy path: Gemini is called and returns a valid EvaluationResult.
- Cost guard: audio exceeding the size threshold is rejected BEFORE STT is called.
- No-speech guard: empty STT transcription returns score=0 without calling Gemini.
- Invalid base64: ValueError is raised before any API call.
- Wrong exercise type: ValueError raised before Gemini is called.
"""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from models.firestore import EvaluationResult, ExerciseType
from services import evaluation as eval_module
from services.evaluation import evaluate_attempt, evaluate_pronunciation
from tests.conftest import make_attempt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GEMINI_JSON = json.dumps({"score": 82, "feedback": "Great job!", "isCorrect": True})


def _mock_gemini_response(text: str = GEMINI_JSON) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


def _make_mock_client(text: str = GEMINI_JSON) -> MagicMock:
    """Return a mock genai.Client whose models.generate_content returns a canned response."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini_response(text)
    return mock_client


def _make_audio_base64(num_bytes: int) -> str:
    return base64.b64encode(b"x" * num_bytes).decode()


# ---------------------------------------------------------------------------
# evaluate_attempt — happy path
# ---------------------------------------------------------------------------


def test_evaluate_attempt_happy_path():
    attempt = make_attempt(exercise_type=ExerciseType.translation_challenge, text="Γεια σου κόσμε")
    mock_client = _make_mock_client()

    with patch.object(eval_module, "_get_client", return_value=mock_client):
        result = evaluate_attempt(attempt, prompt="Translate: Hello world")

    assert isinstance(result, EvaluationResult)
    assert result.score == 82
    assert result.isCorrect is True
    mock_client.models.generate_content.assert_called_once()


def test_evaluate_attempt_dictation_type():
    attempt = make_attempt(exercise_type=ExerciseType.dictation, text="καλημέρα")
    mock_client = _make_mock_client(json.dumps({"score": 95, "feedback": "Perfect!", "isCorrect": True}))

    with patch.object(eval_module, "_get_client", return_value=mock_client):
        result = evaluate_attempt(attempt, prompt="Write what you hear")

    assert result.score == 95


# ---------------------------------------------------------------------------
# evaluate_attempt — isCorrect override (score threshold)
# ---------------------------------------------------------------------------


def test_evaluate_attempt_is_correct_overridden_by_score():
    """isCorrect in the Gemini response is always overridden: score > 60 → True."""
    # Gemini says isCorrect=False but score=70 → backend should override to True
    attempt = make_attempt(exercise_type=ExerciseType.translation_challenge, text="καλός")
    mock_client = _make_mock_client(json.dumps({"score": 70, "feedback": "Decent.", "isCorrect": False}))

    with patch.object(eval_module, "_get_client", return_value=mock_client):
        result = evaluate_attempt(attempt, prompt="Translate: good")

    assert result.isCorrect is True  # 70 > 60


def test_evaluate_attempt_is_correct_false_when_score_low():
    attempt = make_attempt(exercise_type=ExerciseType.translation_challenge, text="blah")
    mock_client = _make_mock_client(json.dumps({"score": 40, "feedback": "Needs work.", "isCorrect": True}))

    with patch.object(eval_module, "_get_client", return_value=mock_client):
        result = evaluate_attempt(attempt, prompt="Translate: good")

    assert result.isCorrect is False  # 40 <= 60


# ---------------------------------------------------------------------------
# evaluate_attempt — wrong type raises before calling Gemini
# ---------------------------------------------------------------------------


def test_evaluate_attempt_raises_for_non_graded_type():
    attempt = make_attempt(exercise_type=ExerciseType.word_scramble)
    mock_client = _make_mock_client()

    with patch.object(eval_module, "_get_client", return_value=mock_client):
        with pytest.raises(ValueError, match="not evaluated by AI"):
            evaluate_attempt(attempt, prompt="")

    mock_client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# evaluate_pronunciation — happy path
# ---------------------------------------------------------------------------


def test_evaluate_pronunciation_happy_path():
    attempt = make_attempt(exercise_type=ExerciseType.pronunciation_practice)
    audio_b64 = _make_audio_base64(1000)  # well within limit

    mock_client = _make_mock_client(json.dumps({"score": 75, "feedback": "Good pronunciation!", "isCorrect": True}))

    with (
        patch.object(eval_module, "_get_client", return_value=mock_client),
        patch.object(eval_module, "_transcribe_audio", return_value="γεια σου"),
    ):
        result = evaluate_pronunciation(attempt, target_text="γεια σου", audio_base64=audio_b64)

    assert result.score == 75
    assert result.isCorrect is True
    mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# evaluate_pronunciation — cost guard (oversized audio rejected before STT)
# ---------------------------------------------------------------------------


def test_evaluate_pronunciation_rejects_oversized_audio_before_stt():
    """Audio payload above the size ceiling must raise ValueError without calling STT."""
    attempt = make_attempt(exercise_type=ExerciseType.pronunciation_practice)

    # _MAX_AUDIO_SECONDS=15, ceiling = 15 * 8000 = 120_000 bytes — exceed it
    oversized_b64 = _make_audio_base64(120_001)

    mock_transcribe = MagicMock()

    with patch.object(eval_module, "_transcribe_audio", mock_transcribe):
        with pytest.raises(ValueError, match="too large"):
            evaluate_pronunciation(attempt, target_text="γεια σου", audio_base64=oversized_b64)

    # STT must NOT have been called — no cost incurred
    mock_transcribe.assert_not_called()


# ---------------------------------------------------------------------------
# evaluate_pronunciation — no speech detected (empty transcription)
# ---------------------------------------------------------------------------


def test_evaluate_pronunciation_no_speech_returns_zero_score():
    """Empty STT transcription returns score=0 and skips Gemini — no LLM cost."""
    attempt = make_attempt(exercise_type=ExerciseType.pronunciation_practice)
    audio_b64 = _make_audio_base64(1000)

    mock_client = _make_mock_client()

    with (
        patch.object(eval_module, "_get_client", return_value=mock_client),
        patch.object(eval_module, "_transcribe_audio", return_value=""),
    ):
        result = evaluate_pronunciation(attempt, target_text="γεια σου", audio_base64=audio_b64)

    assert result.score == 0
    assert result.isCorrect is False
    # Gemini must NOT be called when there is nothing to evaluate
    mock_client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# evaluate_pronunciation — invalid base64
# ---------------------------------------------------------------------------


def test_evaluate_pronunciation_raises_on_invalid_base64():
    attempt = make_attempt(exercise_type=ExerciseType.pronunciation_practice)

    with pytest.raises(ValueError, match="Invalid base64"):
        evaluate_pronunciation(attempt, target_text="γεια σου", audio_base64="!!!not-base64!!!")
