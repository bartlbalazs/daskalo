"""
Node: extract_vocabulary
Calls gemini-2.5-flash via structured output to extract the vocabulary list from the passage.

Runs in parallel with extract_grammar_outlines after draft_lesson_core.
"""

import logging
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from models.content_models import LESSON_CONFIG, LessonLength, VocabularyResult
from prompts.content_prompts import EXTRACT_VOCABULARY_PROMPT
from state import ContentState
from utils.llm_utils import invoke_with_retry

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash"
_INVOKE_RETRIES = 3
_RETRY_SLEEP = 2


def extract_vocabulary(state: ContentState) -> dict:
    """LangGraph node — extract vocabulary list from the passage via Gemini Flash."""
    logger.info("Extracting vocabulary for topic: %s", state["chapter_topic"])

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
        timeout=240.0,
        max_retries=1,
    )
    structured_model = model.with_structured_output(VocabularyResult, method="json_schema")

    lesson_length = state.get("lesson_length", LessonLength.MEDIUM)
    config = LESSON_CONFIG[lesson_length]

    passage_sentences = state.get("passage", [])
    passage_str = "\n".join(f"{i + 1}. {s.greek} ({s.english})" for i, s in enumerate(passage_sentences))

    prompt = EXTRACT_VOCABULARY_PROMPT.format(
        chapter_title=state["chapter_title"],
        language_skill=state.get("language_skill", ""),
        cefr_level=state.get("cefr_level", "A1"),
        lesson_length=lesson_length,
        greek_passage=passage_str,
        mandatory_vocabulary=", ".join(state.get("mandatory_vocabulary", [])),
        accumulated_vocabulary=", ".join(state.get("accumulated_vocabulary", [])),
        vocab_count=config["vocab_count"],
    )

    result: VocabularyResult = invoke_with_retry(
        structured_model,
        prompt,
        pydantic_model=VocabularyResult,
        retries=_INVOKE_RETRIES,
        sleep_sec=_RETRY_SLEEP,
        log_prefix="extract_vocabulary",
    )
    logger.info("Vocabulary extracted — %d items", len(result.vocabulary))
    return {"vocabulary": result.vocabulary}
