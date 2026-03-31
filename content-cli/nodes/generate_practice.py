"""
Node: generate_practice
Calls gemini-3.1-pro-preview via structured output to generate a Practice Set
for a previously generated chapter.

A Practice Set is a 10-12 exercise homework drill that:
  - MUST include at least one `matching` exercise (4 current vocab + 1 previous vocab words).
  - MUST include at least one `conversation` exercise.
  - MUST include at least one `image_description` exercise.
  - MUST NOT include `word_card` or `vocab_flashcard` exercises.
  - Generates its own cover image prompt with a 'homework / study' aesthetic.

Inputs from PracticeState:
  chapter_id          — the Firestore chapter doc ID of the parent chapter
  chapter_topic       — the chapter topic seed (for theming)
  chapter_title       — the chapter title (for context)
  chapter_summary     — the chapter summary (for context)
  curriculum_chapter_id — used to look up the 5 previous chapters' vocabulary
  vocabulary          — VocabularyItem list extracted from the chapter descriptor
  book_id             — used for media generation (speaking rate)
"""

import logging
import os
import sys
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI

from models.content_models import PracticeSetResult
from prompts.content_prompts import GENERATE_PRACTICE_PROMPT
from utils.llm_utils import invoke_with_retry

# Ensure shared package is importable
_repo_root = Path(__file__).parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.data.curriculum_loader import get_previous_chapters_vocabulary  # noqa: E402

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-pro-preview"
_INVOKE_RETRIES = 3
_RETRY_SLEEP = 2


def generate_practice(state: dict) -> dict:
    """LangGraph node — generate Practice Set exercises via Gemini Pro."""
    chapter_title = state.get("chapter_title", "")
    chapter_summary = state.get("chapter_summary", "")
    curriculum_chapter_id = state.get("curriculum_chapter_id", "")

    logger.info(
        "Generating practice set for chapter '%s' (%s)",
        chapter_title,
        curriculum_chapter_id,
    )

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
        timeout=300.0,
        max_retries=1,
    )
    structured_model = model.with_structured_output(PracticeSetResult, method="json_schema")

    # Build the chapter theme description for the prompt
    chapter_theme = f"Title: {chapter_title}\nSummary: {chapter_summary}"
    if state.get("chapter_topic"):
        chapter_theme = f"Topic: {state['chapter_topic']}\n" + chapter_theme

    # Current vocabulary: the words from the chapter
    vocabulary = state.get("vocabulary", [])
    current_vocab_lines = [f"- {v.greek} ({v.english})" for v in vocabulary]
    current_vocab_json = "\n".join(current_vocab_lines) if current_vocab_lines else "(no vocabulary available)"

    # Previous vocabulary: mandatory words from the 5 chapters before this one
    previous_vocab: list[str] = []
    if curriculum_chapter_id:
        try:
            previous_vocab = get_previous_chapters_vocabulary(_repo_root, curriculum_chapter_id, lookback=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load previous vocabulary for '%s': %s", curriculum_chapter_id, exc)

    if previous_vocab:
        previous_vocab_json = "\n".join(f"- {v}" for v in previous_vocab)
    else:
        previous_vocab_json = "(no previous chapters available — use current vocabulary for all 5 pairs)"

    prompt = GENERATE_PRACTICE_PROMPT.format(
        chapter_theme=chapter_theme,
        current_vocab_json=current_vocab_json,
        previous_vocab_json=previous_vocab_json,
    )

    result: PracticeSetResult = invoke_with_retry(
        structured_model,
        prompt,
        pydantic_model=PracticeSetResult,
        retries=_INVOKE_RETRIES,
        sleep_sec=_RETRY_SLEEP,
        log_prefix="generate_practice",
    )

    type_counts: dict[str, int] = {}
    for ex in result.exercises:
        ex_type = getattr(ex, "type", "unknown")
        type_counts[ex_type] = type_counts.get(ex_type, 0) + 1
    type_summary = ", ".join(f"{t}={n}" for t, n in sorted(type_counts.items()))
    logger.info(
        "Practice set generated — %d exercises: %s",
        len(result.exercises),
        type_summary,
    )

    return {
        "introduction": result.introduction,
        "skills": result.skills,
        "exercises": result.exercises,
        "image_prompts": result.image_prompts,
        "chapter_image_prompt": result.cover_image_prompt,
    }
