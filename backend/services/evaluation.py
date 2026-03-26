"""
Evaluation service — uses Gemini to grade complex free-text exercises,
and Google Cloud STT + Gemini for pronunciation practice.
"""

import base64
import json
import logging
import os

import vertexai
from google.cloud import speech_v1 as speech
from vertexai.generative_models import GenerativeModel

from models.firestore import EvaluationResult, ExerciseAttempt, ExerciseType

logger = logging.getLogger(__name__)

_GRADED_TYPES = {
    ExerciseType.image_description,
    ExerciseType.translation_challenge,
    ExerciseType.dictation,
    ExerciseType.pronunciation_practice,
}

_EVAL_PROMPT = """
You are an expert, encouraging Greek language teacher grading a student's exercise.

Exercise type: {exercise_type}
Exercise prompt: {prompt}
Student's answer: {student_answer}

Grade the answer on a scale of 0-100.
Provide your feedback in English following this exact structure, using \\n to separate the sections:
1. Start with a warm, encouraging summary about the quality of the student's solution.
2. Next, if there were any grammar, spelling, or vocabulary mistakes, clearly correct them.
3. Next, if the student's solution lacked detail or was not rich enough, provide a corrected, extended, and more native-sounding version of their solution in Greek to help them learn, followed by its English translation in parentheses.

Respond ONLY as valid JSON with the following shape:
{{"score": <int>, "feedback": "<string>", "isCorrect": <bool>}}
"""

_PRONUNCIATION_PROMPT = """
You are an expert, encouraging Greek language teacher evaluating a student's pronunciation.

Target Greek text: {target_text}
Student's transcription (from speech recognition): {transcription}

Compare the transcription to the target text and evaluate the student's pronunciation accuracy.
Consider:
- Accuracy of individual words
- Overall intelligibility
- Common Greek phoneme challenges for learners

Grade the pronunciation on a scale of 0-100.
Provide feedback in English:
1. Start with a warm, encouraging summary.
2. Point out any words or sounds that were mispronounced or missing, comparing the target to what was heard.
3. Offer a practical tip for improving the most prominent error, if any.

Respond ONLY as valid JSON with the following shape:
{{"score": <int>, "feedback": "<string>", "isCorrect": <bool>}}
"""

# Maximum audio duration in seconds before we reject the request
_MAX_AUDIO_SECONDS = 15


def _get_model() -> GenerativeModel:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    vertexai.init(project=project, location=region)
    return GenerativeModel("gemini-2.5-flash")


def evaluate_attempt(attempt: ExerciseAttempt, prompt: str) -> EvaluationResult:
    """
    Call Gemini to evaluate a free-text student answer.
    Raises ValueError if the attempt type is not graded by AI.
    """
    if attempt.type not in _GRADED_TYPES:
        raise ValueError(f"Exercise type {attempt.type} is not evaluated by AI.")

    model = _get_model()
    full_prompt = _EVAL_PROMPT.format(
        exercise_type=attempt.type.value,
        prompt=prompt,
        student_answer=attempt.payload.text or "",
    )

    logger.info("Sending evaluation request to Gemini for attempt (type=%s)", attempt.type)
    response = model.generate_content(full_prompt)

    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    data = json.loads(raw)
    # Override AI's boolean judgment: anything above 60 is considered correct.
    data["isCorrect"] = data.get("score", 0) > 60
    return EvaluationResult(**data)


def _transcribe_audio(audio_bytes: bytes) -> str:
    """
    Send audio bytes to Google Cloud STT and return the transcription.
    Assumes WebM/Opus audio at 16kHz in Greek (el-GR).
    """
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=16000,
        language_code="el-GR",
        enable_automatic_punctuation=True,
    )
    response = client.recognize(config=config, audio=audio)
    transcript_parts = [result.alternatives[0].transcript for result in response.results if result.alternatives]
    return " ".join(transcript_parts).strip()


def evaluate_pronunciation(attempt: ExerciseAttempt, target_text: str, audio_base64: str) -> EvaluationResult:
    """
    Evaluate a pronunciation attempt:
      1. Decode + validate audio duration (< 15 s).
      2. Transcribe via Google Cloud STT.
      3. Grade via Gemini 2.5 Flash.
    Raises ValueError for invalid/oversized audio.
    """
    # 1. Decode base64
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as exc:
        raise ValueError(f"Invalid base64 audio data: {exc}") from exc

    # 2. Rough duration guard: WebM/Opus at ~16 kbps → ~2000 bytes/s.
    # We perform a conservative upper-bound check: if the payload is larger
    # than 15 s * 64 kbps (8000 bytes/s) we reject early without calling STT.
    max_bytes = _MAX_AUDIO_SECONDS * 8000  # generous ceiling
    if len(audio_bytes) > max_bytes:
        raise ValueError(
            f"Audio payload too large ({len(audio_bytes)} bytes). "
            f"Maximum allowed is {max_bytes} bytes (~{_MAX_AUDIO_SECONDS} seconds)."
        )

    logger.info("Transcribing pronunciation attempt via STT (payload=%d bytes)", len(audio_bytes))

    # 3. STT
    transcription = _transcribe_audio(audio_bytes)
    logger.info("STT transcription: %r", transcription)

    if not transcription:
        # No speech detected — give zero score with helpful feedback
        return EvaluationResult(
            score=0,
            feedback="No speech was detected in the recording. Please make sure your microphone is working and try again.",
            isCorrect=False,
        )

    # 4. Gemini evaluation
    model = _get_model()
    full_prompt = _PRONUNCIATION_PROMPT.format(
        target_text=target_text,
        transcription=transcription,
    )
    response = model.generate_content(full_prompt)
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    data = json.loads(raw)
    # Override AI's boolean judgment: anything above 60 is considered correct.
    data["isCorrect"] = data.get("score", 0) > 60
    return EvaluationResult(**data)
