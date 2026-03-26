"""
Node: extract_grammar_outlines
Calls gemini-2.5-flash via structured output to identify grammar concept outlines from the passage.

Runs in parallel with extract_vocabulary after draft_lesson_core.
"""

import logging
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from models.content_models import LESSON_CONFIG, GrammarOutlinesResult, LessonLength
from prompts.content_prompts import EXTRACT_GRAMMAR_OUTLINES_PROMPT
from state import ContentState
from utils.llm_utils import invoke_with_retry

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash"
_INVOKE_RETRIES = 3
_RETRY_SLEEP = 2


def extract_grammar_outlines(state: ContentState) -> dict:
    """LangGraph node — extract grammar concept outlines from the passage via Gemini Flash."""
    logger.info("Extracting grammar outlines for topic: %s", state["chapter_topic"])

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
        timeout=240.0,
        max_retries=1,
    )
    structured_model = model.with_structured_output(GrammarOutlinesResult, method="json_schema")

    lesson_length = state.get("lesson_length", LessonLength.MEDIUM)
    config = LESSON_CONFIG[lesson_length]

    passage_sentences = state.get("passage", [])
    passage_str = "\n".join(f"{i + 1}. {s.greek} ({s.english})" for i, s in enumerate(passage_sentences))

    prompt = EXTRACT_GRAMMAR_OUTLINES_PROMPT.format(
        chapter_title=state["chapter_title"],
        language_skill=state.get("language_skill", ""),
        greek_passage=passage_str,
        target_grammar=state.get("target_grammar", ""),
        grammar_concepts=config["grammar_concepts"],
    )

    result: GrammarOutlinesResult = invoke_with_retry(
        structured_model,
        prompt,
        pydantic_model=GrammarOutlinesResult,
        retries=_INVOKE_RETRIES,
        sleep_sec=_RETRY_SLEEP,
        log_prefix="extract_grammar_outlines",
    )
    return {"grammar_concept_outlines": result.grammar_concept_outlines}
