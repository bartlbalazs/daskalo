"""
Node: generate_exercises
Calls gemini-3.1-pro-preview via structured output to generate interactive exercises.

Runs in parallel with generate_grammar_notes after both extract_vocabulary and
extract_grammar_outlines have completed.

Grammar notes are generated separately by generate_grammar_notes and passed to this
node only as context — this node does NOT generate them.
"""

import json
import logging
import os
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from models.content_models import LESSON_CONFIG, ExercisesResult, LessonLength
from prompts.content_prompts import GENERATE_EXERCISES_PROMPT
from state import ContentState

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-pro-preview"
_INVOKE_RETRIES = 3
_RETRY_SLEEP = 2


def generate_exercises(state: ContentState) -> dict:
    """LangGraph node — generate interactive exercises via Gemini Pro."""
    logger.info("Generating exercises for topic: %s", state["chapter_topic"])

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
    )
    structured_model = model.with_structured_output(ExercisesResult, method="json_schema")

    lesson_length = state.get("lesson_length", LessonLength.MEDIUM)
    config = LESSON_CONFIG[lesson_length]

    # Passage_comprehension question count scales with lesson length
    comprehension_questions = {"short": "1", "medium": "2-3", "long": "3-4"}.get(lesson_length, "2-3")

    vocab_str = "\n".join([f"- {v.greek} ({v.english})" for v in state.get("vocabulary", [])])
    outlines_str = "\n".join(
        [f"- {o.concept}: {o.brief_explanation}" for o in state.get("grammar_concept_outlines", [])]
    )

    passage_sentences = state.get("passage", [])
    passage_str = "\n".join(f"{i + 1}. {s.greek} ({s.english})" for i, s in enumerate(passage_sentences))

    prompt = GENERATE_EXERCISES_PROMPT.format(
        chapter_title=state["chapter_title"],
        chapter_summary=state["chapter_summary"],
        language_skill=state.get("language_skill", ""),
        greek_passage=passage_str,
        vocabulary=vocab_str,
        grammar_concept_outlines=outlines_str,
        exercise_count=config["exercise_count"],
        available_types=", ".join(config["available_types"]),
        comprehension_questions=comprehension_questions,
    )

    result: ExercisesResult = _invoke_with_retry(structured_model, prompt)

    return {
        "exercises": result.exercises,
        "image_prompts": result.image_prompts,
    }


def _invoke_with_retry(structured_model, prompt: str) -> ExercisesResult:
    """Invoke the structured LLM with simple retry-on-failure logic."""
    last_exc: Exception | None = None
    for attempt in range(1, _INVOKE_RETRIES + 1):
        try:
            result = structured_model.invoke(prompt)
            if not isinstance(result, ExercisesResult):
                result = ExercisesResult.model_validate(result)
            return result
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "Structured output parse failed (attempt %d/%d): %s",
                attempt,
                _INVOKE_RETRIES,
                exc,
            )
            if attempt < _INVOKE_RETRIES:
                time.sleep(_RETRY_SLEEP)
    raise RuntimeError(f"Failed to get valid structured output after {_INVOKE_RETRIES} attempts") from last_exc
