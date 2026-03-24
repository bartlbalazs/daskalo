"""
Node: draft_lesson_core
Calls gemini-3.1-pro-preview via structured output to produce the core lesson draft:
creative scenario, chapter title, summary, cover image prompt, and Greek passage.

Vocabulary extraction and grammar outline extraction run in parallel after this node.
"""

import json
import logging
import os
import re
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from models.content_models import LESSON_CONFIG, DraftLesson, LessonLength
from prompts.content_prompts import DRAFT_LESSON_CORE_PROMPT
from state import ContentState

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-pro-preview"
MAX_RETRIES = 2  # Max generation+review cycles before proceeding regardless
_INVOKE_RETRIES = 3  # Max LLM call retries on parse/validation failure
_RETRY_SLEEP = 2  # Seconds between LLM retries


def draft_lesson_core(state: ContentState) -> dict:
    """LangGraph node — generate core lesson draft (title, summary, image prompt, passage)."""
    attempts = state.get("generation_attempts", 0) + 1
    logger.info("Drafting lesson core (attempt %d/%d) for topic: %s", attempts, MAX_RETRIES, state["chapter_topic"])

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
    )
    structured_model = model.with_structured_output(DraftLesson, method="json_schema")

    lesson_length = state.get("lesson_length", LessonLength.MEDIUM)
    config = LESSON_CONFIG[lesson_length]

    feedback = state.get("review_feedback", "")
    prompt = DRAFT_LESSON_CORE_PROMPT.format(
        chapter_topic=state["chapter_topic"],
        student_interests=state.get("student_interests", "general"),
        language_skill=state.get("language_skill", ""),
        cefr_level=state.get("cefr_level", "A1"),
        target_grammar=state.get("target_grammar", ""),
        accumulated_grammar=state.get("accumulated_grammar", "None"),
        accumulated_vocabulary=", ".join(state.get("accumulated_vocabulary", [])),
        lesson_length=lesson_length,
        passage_sentences=config["passage_sentences"],
    )
    if feedback:
        prompt += f"\n\nPREVIOUS REVIEW FEEDBACK TO ADDRESS:\n{feedback}"

    draft: DraftLesson = _invoke_with_retry(structured_model, prompt)

    # Derive a clean variant_id from the LLM-generated title.
    # e.g. chapter_id="b1_c2", title="Lost in Monastiraki" → variant_id="b1_c2_lost_in_monastiraki"
    chapter_id = state["curriculum_chapter_id"]
    title_slug = _slugify(draft.chapter_title)
    variant_id = f"{chapter_id}_{title_slug}"
    logger.info("Derived variant_id from generated title: %s", variant_id)

    return {
        "generation_attempts": attempts,
        "variant_id": variant_id,
        "chapter_title": draft.chapter_title,
        "chapter_summary": draft.chapter_summary,
        "chapter_image_prompt": draft.chapter_image_prompt,
        "passage": draft.passage,
        "review_feedback": "",  # Reset feedback for the new attempt
    }


def _slugify(text: str) -> str:
    """Convert text to a safe lowercase slug for use as a Firestore document ID."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _invoke_with_retry(structured_model, prompt: str) -> DraftLesson:
    """Invoke the structured LLM with simple retry-on-failure logic."""
    last_exc: Exception | None = None
    for attempt in range(1, _INVOKE_RETRIES + 1):
        try:
            result = structured_model.invoke(prompt)
            if not isinstance(result, DraftLesson):
                result = DraftLesson.model_validate(result)
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
