"""
Progress service — builds / updates the per-user grammar book when a chapter is completed.

The grammar book is stored as a Markdown string in the user's Firestore document at the
path  users/{uid}.grammar_book  (nested field, not a subcollection).

The service is synchronous (blocks until Gemini responds) and is called directly from the
/users/{uid}/complete-chapter HTTP endpoint.  Blocking for 10-30 s is acceptable.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import vertexai
from firebase_admin import firestore
from vertexai.generative_models import GenerativeModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

_GRAMMAR_BOOK_PROMPT = """
You are an expert Greek language teacher writing concise, well-structured grammar reference notes.

A student has just completed a chapter of a Greek language course.  Your job is to produce a
SHORT additive entry (in Markdown) that summarises only the new grammar concepts introduced in
this chapter and should be appended to their personal grammar book.

=== EXISTING GRAMMAR BOOK (may be empty) ===
{existing_grammar_book}

=== CHAPTER TITLE ===
{chapter_title}

=== CHAPTER SUMMARY ===
{chapter_summary}

=== GRAMMAR NOTES FROM THIS CHAPTER ===
{grammar_notes_text}

=== INSTRUCTIONS ===
1. Write a single Markdown section starting with  ## {chapter_title}
2. For each grammar concept in the chapter:
   - Write a short ### heading with the concept name.
   - Give a 1-3 sentence plain-English explanation.
   - If the note contains a conjugation/declension table, reproduce it in Markdown pipe-table format.
   - Include 1-2 illustrative Greek examples with English translation.
3. Do NOT repeat content that is already present in the existing grammar book.
4. Do NOT include vocabulary lists or exercise summaries.
5. Respond with ONLY the Markdown text — no preamble, no code fences.
"""

_PROGRESS_SUMMARY_PROMPT = """
You are a language learning coach.  Write a short, encouraging progress note (2-4 sentences,
plain text, no Markdown) for a student who has just completed the following Greek language chapter.

Chapter title: {chapter_title}
Chapter summary: {chapter_summary}
Grammar concepts covered: {concept_list}

Keep it warm, specific to the content, and motivating.  Do not use generic phrases like
"Great job!" or "Keep it up!".  Respond with ONLY the plain text.
"""


def _get_model() -> GenerativeModel:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    vertexai.init(project=project, location=region)
    return GenerativeModel("gemini-2.0-flash")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def complete_chapter(uid: str, chapter_id: str) -> dict:
    """
    Synchronously:
      1. Loads the chapter document and the user document from Firestore.
      2. Calls Gemini to produce a new grammar-book entry for this chapter.
      3. Calls Gemini to produce a short progress summary sentence.
      4. Additively appends the grammar entry to the user's grammar_book field.
      5. Updates the user's progress (completedChapterIds, lastActive, progressSummary).
      6. Returns a dict with the fields written.

    Raises:
        ValueError  — if the chapter or user document is not found.
        Exception   — propagated from Firestore / Gemini on unexpected errors.
    """
    db = firestore.client()

    # ------------------------------------------------------------------
    # 1. Load chapter
    # ------------------------------------------------------------------
    chapter_snap = db.collection("chapters").document(chapter_id).get()
    if not chapter_snap.exists:
        raise ValueError(f"Chapter '{chapter_id}' not found in Firestore.")
    chapter_data = chapter_snap.to_dict() or {}

    chapter_title: str = chapter_data.get("title", chapter_id)
    chapter_summary: str = chapter_data.get("summary", "")
    grammar_notes: list[dict] = chapter_data.get("grammarNotes", [])

    # ------------------------------------------------------------------
    # 2. Load user
    # ------------------------------------------------------------------
    user_ref = db.collection("users").document(uid)
    user_snap = user_ref.get()
    if not user_snap.exists:
        raise ValueError(f"User '{uid}' not found in Firestore.")
    user_data = user_snap.to_dict() or {}

    existing_grammar_book: str = user_data.get("grammar_book", "") or ""
    progress: dict = user_data.get("progress", {})
    completed_ids: list[str] = progress.get("completedChapterIds", [])

    # Guard: already completed — return existing data immediately, skip Gemini calls.
    already_done = chapter_id in completed_ids
    if already_done:
        logger.info("Chapter '%s' already completed for user '%s' — skipping Gemini calls.", chapter_id, uid)
        return {
            "chapter_id": chapter_id,
            "grammar_entry_appended": "",
            "progress_summary": progress.get("lastProgressSummary", ""),
            "completed_chapter_ids": completed_ids,
        }

    # ------------------------------------------------------------------
    # 3. Build grammar-notes text for the prompt
    # ------------------------------------------------------------------
    grammar_notes_text = _format_grammar_notes(grammar_notes)
    concept_list = ", ".join(n.get("heading", "") for n in grammar_notes if n.get("heading"))

    # ------------------------------------------------------------------
    # 4. Call Gemini — grammar book entry
    # ------------------------------------------------------------------
    model = _get_model()
    logger.info("Requesting grammar book entry from Gemini for chapter='%s' uid='%s'", chapter_id, uid)

    grammar_prompt = _GRAMMAR_BOOK_PROMPT.format(
        existing_grammar_book=existing_grammar_book or "(empty — this is the student's first entry)",
        chapter_title=chapter_title,
        chapter_summary=chapter_summary,
        grammar_notes_text=grammar_notes_text,
    )
    grammar_response = model.generate_content(grammar_prompt)
    new_grammar_entry: str = grammar_response.text.strip()

    # ------------------------------------------------------------------
    # 5. Call Gemini — progress summary
    # ------------------------------------------------------------------
    logger.info("Requesting progress summary from Gemini for chapter='%s' uid='%s'", chapter_id, uid)
    summary_prompt = _PROGRESS_SUMMARY_PROMPT.format(
        chapter_title=chapter_title,
        chapter_summary=chapter_summary,
        concept_list=concept_list or "general Greek language concepts",
    )
    summary_response = model.generate_content(summary_prompt)
    progress_summary: str = summary_response.text.strip()

    # ------------------------------------------------------------------
    # 6. Compose updated grammar book (additive append)
    # ------------------------------------------------------------------
    separator = "\n\n---\n\n" if existing_grammar_book else ""
    updated_grammar_book = existing_grammar_book + separator + new_grammar_entry

    # ------------------------------------------------------------------
    # 7. Update completedChapterIds (chapter not yet in the list)
    # ------------------------------------------------------------------
    completed_ids = [*completed_ids, chapter_id]

    now = datetime.now(UTC)
    update_payload = {
        "grammar_book": updated_grammar_book,
        "progress.completedChapterIds": completed_ids,
        "progress.lastProgressSummary": progress_summary,
        "lastActive": now,
    }

    user_ref.update(update_payload)
    logger.info("User '%s' chapter '%s' completion saved.", uid, chapter_id)

    return {
        "chapter_id": chapter_id,
        "grammar_entry_appended": new_grammar_entry,
        "progress_summary": progress_summary,
        "completed_chapter_ids": completed_ids,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_grammar_notes(notes: list[dict]) -> str:
    """Convert grammar notes dicts to a readable text block for the prompt."""
    if not notes:
        return "(no grammar notes for this chapter)"

    parts: list[str] = []
    for note in notes:
        heading = note.get("heading", "")
        explanation = note.get("explanation", "")
        table = note.get("grammar_table") or ""
        examples = note.get("examples", [])

        part = f"### {heading}\n{explanation}"
        if table:
            part += f"\n\n{table}"
        if examples:
            ex_lines = "\n".join(f"- {ex.get('greek', '')} — {ex.get('english', '')}" for ex in examples)
            part += f"\n\nExamples:\n{ex_lines}"
        parts.append(part)

    return "\n\n".join(parts)
