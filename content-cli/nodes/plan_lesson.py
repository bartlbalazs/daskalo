"""
Node: plan_lesson
Calls gemini-2.5-flash via structured output to produce the lesson plan:
creative scenario, Greek passage, vocabulary, and grammar concepts outline.
"""

import json
import logging
import os
import re
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from models.content_models import LESSON_CONFIG, LessonLength, LessonPlan
from prompts.content_prompts import PLAN_LESSON_PROMPT
from state import ContentState

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-pro-preview"
MAX_RETRIES = 2  # Max generation+review cycles before proceeding regardless
_INVOKE_RETRIES = 3  # Max LLM call retries on parse/validation failure
_RETRY_SLEEP = 2  # Seconds between LLM retries


def plan_lesson(state: ContentState) -> dict:
    """LangGraph node — generate lesson plan via Gemini."""
    attempts = state.get("generation_attempts", 0) + 1
    logger.info("Planning lesson (attempt %d/%d) for topic: %s", attempts, MAX_RETRIES, state["chapter_topic"])

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
    )
    structured_model = model.with_structured_output(LessonPlan, method="json_schema")

    lesson_length = state.get("lesson_length", LessonLength.MEDIUM)
    config = LESSON_CONFIG[lesson_length]

    feedback = state.get("review_feedback", "")
    prompt = PLAN_LESSON_PROMPT.format(
        chapter_topic=state["chapter_topic"],
        student_interests=state.get("student_interests", "general"),
        language_skill=state.get("language_skill", ""),
        target_grammar=state.get("target_grammar", ""),
        mandatory_vocabulary=", ".join(state.get("mandatory_vocabulary", [])),
        accumulated_grammar=state.get("accumulated_grammar", "None"),
        accumulated_vocabulary=", ".join(state.get("accumulated_vocabulary", [])),
        lesson_length=lesson_length,
        passage_sentences=config["passage_sentences"],
        vocab_count=config["vocab_count"],
        grammar_concepts=config["grammar_concepts"],
    )
    if feedback:
        prompt += f"\n\nPREVIOUS REVIEW FEEDBACK TO ADDRESS:\n{feedback}"

    plan: LessonPlan = _invoke_with_retry(structured_model, prompt)

    # Derive a clean variant_id from the LLM-generated title instead of the raw topic.
    # e.g. chapter_id="p1_c2", title="Lost in Monastiraki" → variant_id="p1_c2_lost_in_monastiraki"
    chapter_id = state["curriculum_chapter_id"]
    title_slug = _slugify(plan.chapter_title)
    variant_id = f"{chapter_id}_{title_slug}"
    logger.info("Derived variant_id from generated title: %s", variant_id)

    return {
        "generation_attempts": attempts,
        "variant_id": variant_id,
        "chapter_title": plan.chapter_title,
        "chapter_summary": plan.chapter_summary,
        "chapter_image_prompt": plan.chapter_image_prompt,
        "passage": plan.passage,
        "vocabulary": plan.vocabulary,
        "grammar_concept_outlines": plan.grammar_concept_outlines,
        "review_feedback": "",  # Reset feedback for the new attempt
    }


def _slugify(text: str) -> str:
    """Convert text to a safe lowercase slug for use as a Firestore document ID."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _invoke_with_retry(structured_model, prompt: str) -> LessonPlan:
    """Invoke the structured LLM with simple retry-on-failure logic."""
    last_exc: Exception | None = None
    for attempt in range(1, _INVOKE_RETRIES + 1):
        try:
            result = structured_model.invoke(prompt)
            if not isinstance(result, LessonPlan):
                result = LessonPlan.model_validate(result)
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
