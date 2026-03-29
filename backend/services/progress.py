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
import time
from datetime import UTC, datetime

from google import genai
from google.cloud import firestore as gc_firestore
from google.cloud.firestore import Client as FirestoreClient

logger = logging.getLogger(__name__)

_MODEL_ID = "gemini-2.5-flash"

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


def _get_client() -> genai.Client:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    logger.debug("_get_client: initialising google-genai client project=%r region=%r", project, region)
    return genai.Client(vertexai=True, project=project, location=region)


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
    logger.info("complete_chapter: start — uid=%r chapterId=%r", uid, chapter_id)
    db = FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))

    # ------------------------------------------------------------------
    # 1. Load chapter
    # ------------------------------------------------------------------
    logger.info("complete_chapter: loading chapter document — chapterId=%r", chapter_id)
    chapter_snap = db.collection("chapters").document(chapter_id).get()
    if not chapter_snap.exists:
        logger.warning("complete_chapter: chapter not found — chapterId=%r", chapter_id)
        raise ValueError(f"Chapter '{chapter_id}' not found in Firestore.")
    chapter_data = chapter_snap.to_dict() or {}

    chapter_title: str = chapter_data.get("title", chapter_id)
    chapter_summary: str = chapter_data.get("summary", "")
    chapter_length: str = chapter_data.get("length", "short")
    grammar_notes: list[dict] = chapter_data.get("grammarNotes", [])

    logger.info(
        "complete_chapter: chapter loaded — title=%r length=%s grammar_notes=%d",
        chapter_title,
        chapter_length,
        len(grammar_notes),
    )

    # ------------------------------------------------------------------
    # 2. Load user
    # ------------------------------------------------------------------
    logger.info("complete_chapter: loading user document — uid=%r", uid)
    user_ref = db.collection("users").document(uid)
    user_snap = user_ref.get()
    if not user_snap.exists:
        logger.warning("complete_chapter: user not found — uid=%r", uid)
        raise ValueError(f"User '{uid}' not found in Firestore.")
    user_data = user_snap.to_dict() or {}

    progress: dict = user_data.get("progress", {})
    completed_ids: list[str] = progress.get("completedChapterIds", [])

    logger.info(
        "complete_chapter: user loaded — uid=%r completed_chapters=%d",
        uid,
        len(completed_ids),
    )

    # Guard: already completed — return existing data immediately, skip Gemini call.
    already_done = chapter_id in completed_ids
    if already_done:
        logger.info(
            "complete_chapter: chapter already completed — uid=%r chapterId=%r — skipping Gemini call",
            uid,
            chapter_id,
        )
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
    logger.info(
        "complete_chapter: concept list for prompt — %r",
        concept_list or "(none)",
    )

    # ------------------------------------------------------------------
    # 4. Call Gemini — progress summary
    # ------------------------------------------------------------------
    summary_prompt = _PROGRESS_SUMMARY_PROMPT.format(
        chapter_title=chapter_title,
        chapter_summary=chapter_summary,
        concept_list=concept_list or "general Greek language concepts",
    )
    logger.info(
        "complete_chapter: calling Gemini for progress summary — model=%s uid=%r chapterId=%r prompt_chars=%d",
        _MODEL_ID,
        uid,
        chapter_id,
        len(summary_prompt),
    )

    client = _get_client()
    t0 = time.perf_counter()
    summary_response = client.models.generate_content(
        model=_MODEL_ID,
        contents=summary_prompt,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    progress_summary: str = summary_response.text.strip()

    logger.info(
        "complete_chapter: Gemini progress summary received — elapsed=%.0fms chars=%d uid=%r",
        elapsed_ms,
        len(progress_summary),
        uid,
    )
    logger.debug("complete_chapter: progress summary text: %s", progress_summary)

    # ------------------------------------------------------------------
    # 5. Calculate XP based on length
    # ------------------------------------------------------------------
    xp_map = {"short": 100, "medium": 150, "long": 200}
    xp_gained = xp_map.get(chapter_length, 100)
    logger.info(
        "complete_chapter: XP calculation — length=%s xp_gained=%d uid=%r",
        chapter_length,
        xp_gained,
        uid,
    )

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

    logger.info(
        "complete_chapter: writing progress to Firestore — uid=%r chapterId=%r xp_gained=%d total_completed=%d",
        uid,
        chapter_id,
        xp_gained,
        len(completed_ids),
    )
    user_ref.update(update_payload)

    logger.info(
        "complete_chapter: done — uid=%r chapterId=%r xp_gained=%d",
        uid,
        chapter_id,
        xp_gained,
    )

    return {
        "chapter_id": chapter_id,
        "xp_gained": xp_gained,
        "progress_summary": progress_summary,
        "completed_chapter_ids": completed_ids,
    }
