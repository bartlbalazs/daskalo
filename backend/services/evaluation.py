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
from vertexai.generative_models import GenerativeModel, Part

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
Provide your feedback following this exact structure and strictly observing the language rules, using \\n to separate the sections:
1. Start with a warm, encouraging summary about the quality of the student's solution. THIS OPENING SUMMARY MUST BE WRITTEN IN GREEK.
2. Next, if there were any grammar, spelling, or vocabulary mistakes, clearly explain the rules IN ENGLISH, but write any corrected words, examples, or phrases IN GREEK.
3. Next, if the student's solution lacked detail or was not rich enough, provide a corrected, extended, and more native-sounding version of their solution IN GREEK to help them learn, followed by its English translation in parentheses.

CRITICAL LANGUAGE RULE: Even if the student's answer is entirely in Greek, do not write your entire feedback in Greek. Your explanations and analysis (step 2) MUST be in English. Only the opening encouragement, the improved version, and the corrected examples should be in Greek.

IMPORTANT: Never use the word "prompt" in your feedback. Refer to the task naturally (e.g. "the exercise", "the task", or simply address their answer directly).

Respond ONLY as valid JSON with the following shape:
{{"score": <int>, "feedback": "<string>", "isCorrect": <bool>}}
"""

_EVAL_PROMPT_WITH_IMAGE = """
You are an expert, encouraging Greek language teacher grading a student's exercise.

The student was shown the attached image and asked to describe it in Greek.
Exercise prompt: {prompt}
Student's answer: {student_answer}

Evaluate both:
1. How accurately the student's description reflects the actual image content (relevance).
2. The quality of the Greek language used (grammar, vocabulary, fluency).

Grade on a scale of 0-100.
Provide your feedback following this exact structure and strictly observing the language rules, using \\n to separate the sections:
1. Start with a warm, encouraging summary covering both content accuracy and language quality. THIS OPENING SUMMARY MUST BE WRITTEN IN GREEK.
2. If the student missed important elements visible in the image, point them out IN ENGLISH.
3. If there were grammar, spelling, or vocabulary mistakes, clearly explain the rules IN ENGLISH, but write any corrected words, examples, or phrases IN GREEK.
4. If the description lacked detail or native fluency, provide a corrected, extended, more native-sounding version IN GREEK, followed by its English translation in parentheses.

CRITICAL LANGUAGE RULE: Even if the student's answer is entirely in Greek, do not write your entire feedback in Greek. Your explanations and analysis (steps 2 and 3) MUST be in English. Only the opening encouragement, the improved version, and the corrected examples should be in Greek.

IMPORTANT: Never use the word "prompt" in your feedback. Refer to the task naturally (e.g. "the image", "the picture", or simply address their answer directly).

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

IMPORTANT: Never use the word "prompt" in your feedback. Refer to the task naturally (e.g. "the text", "the sentence", or simply address their pronunciation directly).

Respond ONLY as valid JSON with the following shape:
{{"score": <int>, "feedback": "<string>", "isCorrect": <bool>}}
"""

# Maximum audio duration in seconds before we reject the request
_MAX_AUDIO_SECONDS = 15

# Maximum length of a student's free-text answer
_MAX_ANSWER_CHARS = 300


def _get_model() -> GenerativeModel:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    vertexai.init(project=project, location=region)
    return GenerativeModel("gemini-2.5-flash")


def evaluate_attempt(attempt: ExerciseAttempt, prompt: str, *, image_url: str = "") -> EvaluationResult:
    """
    Call Gemini to evaluate a free-text student answer.

    For ``image_description`` exercises, pass ``image_url`` (a ``gs://`` URI)
    to enable multimodal evaluation — Gemini receives both the image and the
    student's Greek text and can verify whether the description matches the image.

    Raises ValueError if the attempt type is not graded by AI.
    """
    if attempt.type not in _GRADED_TYPES:
        raise ValueError(f"Exercise type {attempt.type} is not evaluated by AI.")

    answer_text = attempt.payload.text or ""
    if len(answer_text) > _MAX_ANSWER_CHARS:
        raise ValueError(
            f"Answer exceeds maximum allowed length of {_MAX_ANSWER_CHARS} characters (got {len(answer_text)})."
        )

    logger.info(
        "evaluate_attempt: attemptId=%s type=%s answer=%r prompt=%r image_url=%r",
        attempt.exerciseId,
        attempt.type.value,
        (attempt.payload.text or ""),
        prompt,
        image_url,
    )

    model = _get_model()

    use_image = attempt.type == ExerciseType.image_description and image_url.startswith("gs://")

    if use_image:
        text_prompt = _EVAL_PROMPT_WITH_IMAGE.format(
            prompt=prompt,
            student_answer=attempt.payload.text or "",
        )
        image_part = Part.from_uri(image_url, mime_type="image/jpeg")
        contents: list = [image_part, text_prompt]
        logger.info("evaluate_attempt: multimodal request — image_url=%r", image_url)
    else:
        text_prompt = _EVAL_PROMPT.format(
            exercise_type=attempt.type.value,
            prompt=prompt,
            student_answer=attempt.payload.text or "",
        )
        contents = [text_prompt]

    logger.info("evaluate_attempt: sending request to Gemini (model=gemini-2.5-flash)")
    response = model.generate_content(contents)
    logger.debug("evaluate_attempt: raw Gemini response: %s", response.text)

    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    data = json.loads(raw)
    # Override AI's boolean judgment: anything above 60 is considered correct.
    data["isCorrect"] = data.get("score", 0) > 60
    result = EvaluationResult(**data)
    logger.info(
        "evaluate_attempt: done — attemptId=%s score=%d isCorrect=%s",
        attempt.exerciseId,
        result.score,
        result.isCorrect,
    )
    return result


def _transcribe_audio(audio_bytes: bytes) -> str:
    """
    Send audio bytes to Google Cloud STT and return the transcription.
    Assumes WebM/Opus audio in Greek (el-GR). Sample rate is auto-detected
    from the WEBM container header (browsers typically record at 48 kHz).
    """
    logger.info("_transcribe_audio: calling STT (encoding=WEBM_OPUS lang=el-GR payload=%d bytes)", len(audio_bytes))
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        language_code="el-GR",
        enable_automatic_punctuation=True,
    )
    response = client.recognize(config=config, audio=audio)
    logger.info("_transcribe_audio: STT returned %d result(s)", len(response.results))
    transcript_parts = [result.alternatives[0].transcript for result in response.results if result.alternatives]
    transcript = " ".join(transcript_parts).strip()
    logger.info("_transcribe_audio: transcript=%r", transcript)
    return transcript


def evaluate_pronunciation(attempt: ExerciseAttempt, target_text: str, audio_base64: str) -> EvaluationResult:
    """
    Evaluate a pronunciation attempt:
      1. Decode + validate audio duration (< 15 s).
      2. Transcribe via Google Cloud STT.
      3. Grade via Gemini 2.5 Flash.
    Raises ValueError for invalid/oversized audio.
    """
    logger.info(
        "evaluate_pronunciation: attemptId=%s target_text=%r audio_base64_len=%d",
        attempt.exerciseId,
        target_text,
        len(audio_base64),
    )

    # 1. Decode base64
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as exc:
        raise ValueError(f"Invalid base64 audio data: {exc}") from exc

    logger.info("evaluate_pronunciation: decoded audio payload=%d bytes", len(audio_bytes))

    # 2. Rough duration guard: WebM/Opus at ~16 kbps → ~2000 bytes/s.
    # We perform a conservative upper-bound check: if the payload is larger
    # than 15 s * 64 kbps (8000 bytes/s) we reject early without calling STT.
    max_bytes = _MAX_AUDIO_SECONDS * 8000  # generous ceiling
    if len(audio_bytes) > max_bytes:
        logger.warning(
            "evaluate_pronunciation: audio payload too large (%d bytes, max=%d) — rejecting",
            len(audio_bytes),
            max_bytes,
        )
        raise ValueError(
            f"Audio payload too large ({len(audio_bytes)} bytes). "
            f"Maximum allowed is {max_bytes} bytes (~{_MAX_AUDIO_SECONDS} seconds)."
        )

    # 3. STT
    transcription = _transcribe_audio(audio_bytes)

    if not transcription:
        logger.warning("evaluate_pronunciation: STT returned empty transcription — returning score=0")
        # No speech detected — give zero score with helpful feedback
        return EvaluationResult(
            score=0,
            feedback="No speech was detected in the recording. Please make sure your microphone is working and try again.",
            isCorrect=False,
        )

    # 4. Gemini evaluation
    logger.info(
        "evaluate_pronunciation: sending transcription to Gemini for grading — target=%r transcription=%r",
        target_text,
        transcription,
    )
    model = _get_model()
    full_prompt = _PRONUNCIATION_PROMPT.format(
        target_text=target_text,
        transcription=transcription,
    )
    response = model.generate_content(full_prompt)
    logger.debug("evaluate_pronunciation: raw Gemini response: %s", response.text)

    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    data = json.loads(raw)
    # Override AI's boolean judgment: anything above 60 is considered correct.
    data["isCorrect"] = data.get("score", 0) > 60
    result = EvaluationResult(**data)
    logger.info(
        "evaluate_pronunciation: done — attemptId=%s score=%d isCorrect=%s",
        attempt.exerciseId,
        result.score,
        result.isCorrect,
    )
    return result
