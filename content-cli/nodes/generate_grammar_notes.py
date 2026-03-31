"""
Node: generate_grammar_notes
Calls gemini-3.1-pro-preview via structured output to expand grammar concept outlines
into detailed grammar notes with tables.

Runs in parallel with generate_exercises after both extract_vocabulary and
extract_grammar_outlines have completed.
"""

import logging
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from models.content_models import GrammarNotesResult
from prompts.content_prompts import GENERATE_GRAMMAR_NOTES_PROMPT
from state import ContentState
from utils.llm_utils import invoke_with_retry

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-pro-preview"
_INVOKE_RETRIES = 3
_RETRY_SLEEP = 2


def generate_grammar_notes(state: ContentState) -> dict:
    """LangGraph node — expand grammar outlines into detailed notes via Gemini Pro."""
    logger.info("Generating grammar notes for topic: %s", state["chapter_topic"])

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
        timeout=240.0,
        max_retries=1,
    )
    structured_model = model.with_structured_output(GrammarNotesResult, method="json_schema")

    passage_sentences = state.get("passage", [])
    passage_str = "\n".join(f"{i + 1}. {s.greek} ({s.english})" for i, s in enumerate(passage_sentences))
    outlines_str = "\n".join(
        [f"- {o.concept}: {o.brief_explanation}" for o in state.get("grammar_concept_outlines", [])]
    )

    prompt = GENERATE_GRAMMAR_NOTES_PROMPT.format(
        chapter_title=state["chapter_title"],
        chapter_summary=state["chapter_summary"],
        language_skill=state.get("language_skill", ""),
        greek_passage=passage_str,
        grammar_concept_outlines=outlines_str,
    )

    result: GrammarNotesResult = invoke_with_retry(
        structured_model,
        prompt,
        pydantic_model=GrammarNotesResult,
        retries=_INVOKE_RETRIES,
        sleep_sec=_RETRY_SLEEP,
        log_prefix="generate_grammar_notes",
    )
    total_examples = sum(len(n.examples) for n in result.grammar_notes)
    logger.info(
        "Grammar notes generated — %d notes, %d examples total",
        len(result.grammar_notes),
        total_examples,
    )
    return {"grammar_notes": result.grammar_notes}
