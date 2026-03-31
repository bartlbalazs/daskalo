"""
Node: review_content
Uses gemini-3.1-pro-preview to review the generated lesson for quality, tone, and accuracy.
Returns a structured ReviewResult with per-category booleans and an issues list.
"""

import json
import logging
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from models.content_models import ReviewResult
from nodes.draft_lesson_core import _INVOKE_RETRIES, _RETRY_SLEEP, MAX_RETRIES
from prompts.content_prompts import REVIEW_CONTENT_PROMPT
from state import ContentState
from utils.llm_utils import invoke_with_retry

logger = logging.getLogger(__name__)

_ASSET_PATH_KEYS = {"imagePath", "audioPath"}

MODEL_NAME = "gemini-2.5-flash"


def review_content(state: ContentState) -> dict:
    """LangGraph node — review generated content and return structured feedback."""
    logger.info("Reviewing content for topic: %s", state["chapter_topic"])

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("VERTEX_REGION", "europe-west1"),
        timeout=240.0,
        max_retries=1,
    )
    structured_model = model.with_structured_output(ReviewResult, method="json_schema")

    content_summary = {
        "passage": [s.model_dump() for s in state.get("passage", [])],
        "grammar_notes": [_strip_asset_paths(n.model_dump()) for n in state.get("grammar_notes", [])],
        "vocabulary": [_strip_asset_paths(v.model_dump()) for v in state.get("vocabulary", [])],
        "exercises": [_strip_asset_paths(_exercise_to_dict(ex)) for ex in state.get("exercises", [])],
    }

    prompt = REVIEW_CONTENT_PROMPT.format(
        chapter_topic=state["chapter_topic"],
        cefr_level=state.get("cefr_level", "A1"),
        target_grammar=state.get("target_grammar", ""),
        mandatory_vocabulary=", ".join(state.get("mandatory_vocabulary", [])),
        accumulated_grammar=state.get("accumulated_grammar", "None"),
        content_json=json.dumps(content_summary, ensure_ascii=False, indent=2),
    )

    result: ReviewResult = invoke_with_retry(
        structured_model,
        prompt,
        pydantic_model=ReviewResult,
        retries=_INVOKE_RETRIES,
        sleep_sec=_RETRY_SLEEP,
        log_prefix="review_content",
    )

    if result.approved:
        logger.info(
            "Content APPROVED by reviewer — tone=%s, accuracy=%s, level=%s, slang=%s, exercises=%s, culture=%s",
            "OK" if result.tone_ok else "FAIL",
            "OK" if result.accuracy_ok else "FAIL",
            "OK" if result.level_ok else "FAIL",
            "OK" if result.slang_ok else "FAIL",
            "OK" if result.exercises_ok else "FAIL",
            "OK" if result.culture_ok else "FAIL",
        )
        return {"review_feedback": ""}

    feedback_lines = result.issues or _build_feedback_from_flags(result)
    feedback = "\n".join(f"- {line}" for line in feedback_lines)
    logger.warning(
        "Content needs revision — tone=%s, accuracy=%s, level=%s, slang=%s, exercises=%s, culture=%s\n%s",
        "OK" if result.tone_ok else "FAIL",
        "OK" if result.accuracy_ok else "FAIL",
        "OK" if result.level_ok else "FAIL",
        "OK" if result.slang_ok else "FAIL",
        "OK" if result.exercises_ok else "FAIL",
        "OK" if result.culture_ok else "FAIL",
        feedback,
    )
    return {"review_feedback": feedback}


def should_regenerate(state: ContentState) -> str:
    """
    Conditional edge after review_content.
    Routes back to plan_lesson if feedback exists AND retries remain.
    Otherwise routes to generate_media.
    """
    feedback = state.get("review_feedback", "")
    attempts = state.get("generation_attempts", 0)

    if feedback and attempts < MAX_RETRIES:
        logger.info("Routing back to plan_lesson (attempt %d of %d).", attempts, MAX_RETRIES)
        return "plan_lesson"

    if feedback:
        logger.warning("Max retries reached (%d). Proceeding with current content despite feedback.", MAX_RETRIES)

    return "generate_media"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_asset_paths(obj):
    """Recursively remove asset path fields that are populated after review by generate_media."""
    if isinstance(obj, dict):
        return {k: _strip_asset_paths(v) for k, v in obj.items() if k not in _ASSET_PATH_KEYS}
    if isinstance(obj, list):
        return [_strip_asset_paths(item) for item in obj]
    return obj


def _exercise_to_dict(exercise) -> dict:
    """Serialize an exercise Pydantic model to a plain dict for the review prompt."""
    if hasattr(exercise, "model_dump"):
        return exercise.model_dump()
    return dict(exercise)


def _build_feedback_from_flags(result: ReviewResult) -> list[str]:
    """Fallback: derive issue strings from the per-category booleans if issues list is empty."""
    issues = []
    if not result.tone_ok:
        issues.append("Tone is not conversational or warm enough.")
    if not result.accuracy_ok:
        issues.append("Greek text contains grammatical errors or unnatural phrasing.")
    if not result.level_ok:
        issues.append("Content level is not appropriate for beginner-to-intermediate learners.")
    if not result.slang_ok:
        issues.append("Slang usage is incorrect, outdated, or contextually inappropriate.")
    if not result.exercises_ok:
        issues.append("Exercises are poorly tied to the passage or contain errors.")
    if not result.culture_ok:
        issues.append("Content relies on shallow stereotypes instead of deep cultural nuance.")
    return issues
