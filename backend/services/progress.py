"""
Progress service — marks a chapter as complete and generates a progress summary
when a student finishes a chapter.

The grammar book is no longer generated per-user here. Instead, each chapter document
contains a pre-generated `grammarSummary` field (Markdown) produced at content-creation
time by the content-cli pipeline. The frontend assembles the grammar book at runtime by
loading the grammarSummary from each completed chapter.

This service is synchronous (blocks until Gemini responds) and is called directly from
the /complete-chapter HTTP endpoint. Blocking for ~10 s is acceptable.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import vertexai
from google.cloud import firestore as gc_firestore
from google.cloud.firestore import Client as FirestoreClient
from vertexai.generative_models import GenerativeModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

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
      2. Calls Gemini to produce a short progress summary sentence.
      3. Updates the user's progress (completedChapterIds, lastActive, progressSummary, xp).
      4. Returns a dict with the fields written.

    The grammar book is no longer generated here — it is pre-generated per chapter
    by the content-cli pipeline and stored in chapters/{chapterId}.grammarSummary.

    Raises:
        ValueError  — if the chapter or user document is not found.
        Exception   — propagated from Firestore / Gemini on unexpected errors.
    """
    db = FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))

    # ------------------------------------------------------------------
    # 1. Load chapter
    # ------------------------------------------------------------------
    chapter_snap = db.collection("chapters").document(chapter_id).get()
    if not chapter_snap.exists:
        raise ValueError(f"Chapter '{chapter_id}' not found in Firestore.")
    chapter_data = chapter_snap.to_dict() or {}

    chapter_title: str = chapter_data.get("title", chapter_id)
    chapter_summary: str = chapter_data.get("summary", "")
    chapter_length: str = chapter_data.get("length", "short")
    grammar_notes: list[dict] = chapter_data.get("grammarNotes", [])

    # ------------------------------------------------------------------
    # 2. Load user
    # ------------------------------------------------------------------
    user_ref = db.collection("users").document(uid)
    user_snap = user_ref.get()
    if not user_snap.exists:
        raise ValueError(f"User '{uid}' not found in Firestore.")
    user_data = user_snap.to_dict() or {}

    progress: dict = user_data.get("progress", {})
    completed_ids: list[str] = progress.get("completedChapterIds", [])

    # Guard: already completed — return existing data immediately, skip Gemini call.
    already_done = chapter_id in completed_ids
    if already_done:
        logger.info("Chapter '%s' already completed for user '%s' — skipping.", chapter_id, uid)
        return {
            "chapter_id": chapter_id,
            "xp_gained": 0,
            "progress_summary": progress.get("lastProgressSummary", ""),
            "completed_chapter_ids": completed_ids,
        }

    # ------------------------------------------------------------------
    # 3. Build concept list for the progress summary prompt
    # ------------------------------------------------------------------
    concept_list = ", ".join(n.get("heading", "") for n in grammar_notes if n.get("heading"))

    # ------------------------------------------------------------------
    # 4. Call Gemini — progress summary
    # ------------------------------------------------------------------
    model = _get_model()
    logger.info("Requesting progress summary from Gemini for chapter='%s' uid='%s'", chapter_id, uid)
    summary_prompt = _PROGRESS_SUMMARY_PROMPT.format(
        chapter_title=chapter_title,
        chapter_summary=chapter_summary,
        concept_list=concept_list or "general Greek language concepts",
    )
    summary_response = model.generate_content(summary_prompt)
    progress_summary: str = summary_response.text.strip()

    # ------------------------------------------------------------------
    # 5. Calculate XP based on length
    # ------------------------------------------------------------------
    xp_map = {"short": 100, "medium": 150, "long": 200}
    xp_gained = xp_map.get(chapter_length, 100)

    # ------------------------------------------------------------------
    # 6. Update completedChapterIds and XP
    # ------------------------------------------------------------------
    completed_ids = [*completed_ids, chapter_id]

    now = datetime.now(UTC)
    update_payload = {
        "progress.completedChapterIds": completed_ids,
        "progress.lastProgressSummary": progress_summary,
        "progress.xp": gc_firestore.Increment(xp_gained),
        "lastActive": now,
    }

    user_ref.update(update_payload)
    logger.info("User '%s' chapter '%s' completion saved (+%d XP).", uid, chapter_id, xp_gained)

    return {
        "chapter_id": chapter_id,
        "xp_gained": xp_gained,
        "progress_summary": progress_summary,
        "completed_chapter_ids": completed_ids,
    }
