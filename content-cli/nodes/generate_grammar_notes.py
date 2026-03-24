"""
Node: generate_grammar_notes
Calls gemini-3.1-pro-preview via structured output to expand grammar concept outlines
into detailed grammar notes with tables.

Runs in parallel with generate_exercises after both extract_vocabulary and
extract_grammar_outlines have completed.
"""

import json
import logging
import os
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from models.content_models import GrammarNotesResult
from prompts.content_prompts import GENERATE_GRAMMAR_NOTES_PROMPT
from state import ContentState

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

    result: GrammarNotesResult = _invoke_with_retry(structured_model, prompt)
    return {"grammar_notes": result.grammar_notes}


def _invoke_with_retry(structured_model, prompt: str) -> GrammarNotesResult:
    """Invoke the structured LLM with simple retry-on-failure logic."""
    last_exc: Exception | None = None
    for attempt in range(1, _INVOKE_RETRIES + 1):
        try:
            result = structured_model.invoke(prompt)
            if not isinstance(result, GrammarNotesResult):
                result = GrammarNotesResult.model_validate(result)
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
