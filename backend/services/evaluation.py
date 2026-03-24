"""
Evaluation service — uses Gemini to grade complex free-text exercises.
"""

import logging
import os

import vertexai
from vertexai.generative_models import GenerativeModel

from models.firestore import EvaluationResult, ExerciseAttempt, ExerciseType

logger = logging.getLogger(__name__)

_GRADED_TYPES = {
    ExerciseType.image_description,
    ExerciseType.translation_challenge,
    ExerciseType.dictation,
}

_EVAL_PROMPT = """
You are a Greek language teacher grading a student's exercise.

Exercise type: {exercise_type}
Exercise prompt: {prompt}
Student's answer: {student_answer}

Grade the answer on a scale of 0-100.
Provide short, encouraging feedback in English (2-3 sentences max).
Respond ONLY as valid JSON with the following shape:
{{"score": <int>, "feedback": "<string>", "isCorrect": <bool>}}
"""


def _get_model() -> GenerativeModel:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    vertexai.init(project=project, location=region)
    return GenerativeModel("gemini-2.0-flash")


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

    import json

    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    data = json.loads(raw)
    return EvaluationResult(**data)
