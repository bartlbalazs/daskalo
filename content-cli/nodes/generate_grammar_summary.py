"""
Node: generate_grammar_summary
Calls gemini-3.1-pro-preview to produce a thorough, self-contained Markdown grammar
reference summary for the chapter. This summary is stored on the chapter document and
is shared by all students — it is NOT generated per-user.

The summary covers:
  - All grammar concepts with full explanations and Markdown tables
  - A curated key vocabulary section
  - Practical tips and common mistakes per concept

Runs after generate_grammar_notes (needs expanded notes + vocabulary) and before
review_content. Runs in parallel with generate_exercises.
"""

import logging
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from prompts.content_prompts import GENERATE_GRAMMAR_SUMMARY_PROMPT
from state import ContentState
from utils.llm_utils import invoke_with_retry

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-pro-preview"
_INVOKE_RETRIES = 3
_RETRY_SLEEP = 2


def generate_grammar_summary(state: ContentState) -> dict:
    """LangGraph node — generate a pre-built grammar reference summary via Gemini Pro."""
    logger.info("Generating grammar summary for chapter: %s", state.get("chapter_title", ""))

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GEMINI_LOCATION", "global"),
        timeout=240.0,
        max_retries=1,
    )

    grammar_notes_text = _format_grammar_notes(state.get("grammar_notes", []))
    vocabulary_text = _format_vocabulary(state.get("vocabulary", []))

    prompt = GENERATE_GRAMMAR_SUMMARY_PROMPT.format(
        chapter_title=state["chapter_title"],
        chapter_summary=state.get("chapter_summary", ""),
        cefr_level=state.get("cefr_level", ""),
        grammar_notes_text=grammar_notes_text,
        vocabulary_text=vocabulary_text,
    )

    summary = invoke_with_retry(
        model,
        prompt,
        retries=_INVOKE_RETRIES,
        sleep_sec=_RETRY_SLEEP,
        log_prefix="generate_grammar_summary",
    )
    logger.info("Grammar summary generated (%d chars) for chapter: %s", len(summary), state["chapter_title"])
    return {"grammar_summary": summary}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_grammar_notes(notes: list) -> str:
    """Format grammar note Pydantic models into a readable text block for the prompt."""
    if not notes:
        return "(no grammar notes for this chapter)"

    parts: list[str] = []
    for note in notes:
        # Support both Pydantic model instances and plain dicts
        if hasattr(note, "heading"):
            heading = note.heading or ""
            explanation = note.explanation or ""
            table = note.grammar_table or ""
            examples = note.examples or []
            example_lines = [f"- {ex.greek} — {ex.english}" + (f" ({ex.note})" if ex.note else "") for ex in examples]
        else:
            heading = note.get("heading", "")
            explanation = note.get("explanation", "")
            table = note.get("grammar_table") or ""
            examples = note.get("examples", [])
            example_lines = [
                f"- {ex.get('greek', '')} — {ex.get('english', '')}" + (f" ({ex['note']})" if ex.get("note") else "")
                for ex in examples
            ]

        part = f"### {heading}\n{explanation}"
        if table:
            part += f"\n\n{table}"
        if example_lines:
            part += "\n\nExamples:\n" + "\n".join(example_lines)
        parts.append(part)

    return "\n\n".join(parts)


def _format_vocabulary(vocab_items: list) -> str:
    """Format vocabulary items into a readable list for the prompt."""
    if not vocab_items:
        return "(no vocabulary for this chapter)"

    lines: list[str] = []
    for item in vocab_items:
        if hasattr(item, "greek"):
            lines.append(f"- {item.greek} — {item.english}")
        else:
            lines.append(f"- {item.get('greek', '')} — {item.get('english', '')}")
    return "\n".join(lines)
