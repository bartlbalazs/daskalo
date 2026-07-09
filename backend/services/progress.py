"""
Progress service — marks a chapter as complete and generates a progress summary
when a student finishes a chapter.

The grammar book is no longer generated per-user here. Instead, each chapter document
contains a pre-generated `grammarSummary` field (Markdown) produced at content-creation
time by the content-cli pipeline. The frontend assembles the grammar book at runtime by
loading the grammarSummary from each completed chapter.

This service is synchronous (blocks until Gemini responds) and is called directly from
the /complete-chapter HTTP endpoint. Blocking for ~10 s is acceptable.

Concurrency design (BE-08, IMP-BE-01): the Gemini call for the progress summary is slow
(~10s) and must not run *inside* a Firestore transaction. So completion happens in two
phases:
  1. A cheap, non-transactional check: if the chapter is already completed, return
     immediately (skips the Gemini call entirely — this is the common, fast path).
  2. After the (possibly duplicated, in a genuine race) Gemini call returns, a
     transactional "finalize" step re-checks completion and only then atomically
     ArrayUnions the chapter id + Increments XP + records the summary. If a concurrent
     call already won this race, this step is a no-op that returns the canonical
     (already-committed) result instead of granting XP twice.
This means the *only* durable write that marks a chapter "done" also carries its XP and
summary in the same atomic transaction — there is no window where a chapter can be marked
complete without XP having been granted, even if this request loses a race.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from functools import lru_cache

from google import genai
from google.cloud.firestore import ArrayUnion, FieldFilter, Increment, Transaction, transactional
from google.cloud.firestore import Client as FirestoreClient

from callable_helpers import PreconditionFailedError
from constants import GEMINI_MODEL_ID
from models.firestore import AI_GRADED_EXERCISE_TYPES, AttemptStatus
from services.gemini_utils import generate_content_with_retry

logger = logging.getLogger(__name__)

_MODEL_ID = GEMINI_MODEL_ID

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


# IMP-BE-03: construct the genai client once and reuse it across invocations
# within the same process, instead of on every single request.
@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    logger.debug("_get_client: initialising google-genai client project=%r region=%r", project, region)
    return genai.Client(vertexai=True, project=project, location=region)


# IMP-BE-03: same treatment for the Firestore client.
@lru_cache(maxsize=1)
def _get_db() -> FirestoreClient:
    return FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))


# ---------------------------------------------------------------------------
# BE-06: verify the user actually attempted a graded exercise before awarding
# chapter-completion XP.
#
# Judgement call (see final report): only chapters with an AI-graded exercise
# type (image_description / translation_challenge / dictation /
# pronunciation_practice) leave a trail in `exercise_attempts` — client-graded
# exercise types (matching, slang_matcher, word_scramble, ...) never write one.
# Some chapter lengths never include an AI-graded exercise at all (see
# docs/planning/BUGS.md#CC-04). Requiring an attempt unconditionally would
# make it *impossible* to ever complete such a chapter, which is worse than
# the abuse this check prevents. So the check only applies when the chapter
# actually contains at least one AI-graded exercise.
# ---------------------------------------------------------------------------


def _chapter_has_ai_graded_exercise(chapter_data: dict) -> bool:
    exercise_types = {ex.get("type") for ex in chapter_data.get("exercises", [])}
    return bool(exercise_types & AI_GRADED_EXERCISE_TYPES)


def _has_completed_attempt(db: FirestoreClient, chapter_id: str, uid: str) -> bool:
    query = (
        db.collection("exercise_attempts")
        .where(filter=FieldFilter("chapterId", "==", chapter_id))
        .where(filter=FieldFilter("userId", "==", uid))
        .where(filter=FieldFilter("status", "==", AttemptStatus.completed.value))
        .limit(1)
    )
    return next(iter(query.stream()), None) is not None


# ---------------------------------------------------------------------------
# Transactional finalize (BE-08, IMP-BE-01, IMP-BE-02)
# ---------------------------------------------------------------------------


@transactional
def _finalize_completion(
    transaction: Transaction,
    user_ref,  # noqa: ANN001 - google.cloud.firestore.DocumentReference
    chapter_id: str,
    xp_gained: int,
    progress_summary: str,
) -> dict:
    """
    Atomically re-check + finalize a chapter completion.

    If `chapter_id` is already present in completedChapterIds (a concurrent
    request won the race while this one was waiting on Gemini), returns the
    existing canonical result and grants no additional XP. Otherwise
    atomically ArrayUnions the id and Increments XP — guaranteed race-free by
    the transaction, so two concurrent completions of the same chapter can
    never both increment XP.
    """
    snap = user_ref.get(transaction=transaction)
    user_data = snap.to_dict() or {}
    progress = user_data.get("progress", {})
    completed_ids: list[str] = progress.get("completedChapterIds", [])

    if chapter_id in completed_ids:
        return {
            "chapter_id": chapter_id,
            "xp_gained": 0,
            "progress_summary": progress.get("lastProgressSummary", ""),
            "completed_chapter_ids": completed_ids,
        }

    transaction.update(
        user_ref,
        {
            "progress.completedChapterIds": ArrayUnion([chapter_id]),
            "progress.lastProgressSummary": progress_summary,
            "progress.xp": Increment(xp_gained),
            "lastActive": datetime.now(UTC),
        },
    )
    return {
        "chapter_id": chapter_id,
        "xp_gained": xp_gained,
        "progress_summary": progress_summary,
        "completed_chapter_ids": [*completed_ids, chapter_id],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def complete_chapter(uid: str, chapter_id: str) -> dict:
    """
    Synchronously:
      1. Loads the chapter document and the user document from Firestore.
      2. Verifies the student attempted at least one graded exercise (BE-06).
      3. Calls Gemini to produce a short progress summary sentence.
      4. Atomically updates the user's progress (completedChapterIds, lastActive,
         progressSummary, xp) — see module docstring for the concurrency design.
      5. Returns a dict with the fields written.

    The grammar book is no longer generated here — it is pre-generated per chapter
    by the content-cli pipeline and stored in chapters/{chapterId}.grammarSummary.

    Raises:
        ValueError               — if the chapter or user document is not found.
        PreconditionFailedError  — if no completed exercise attempt exists yet (BE-06).
        Exception                — propagated from Firestore / Gemini on unexpected errors.
    """
    logger.info("complete_chapter: start — uid=%r chapterId=%r", uid, chapter_id)
    db = _get_db()

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

    # Fast path: already completed — return existing data immediately, skip
    # both the BE-06 attempt check and the Gemini call.
    if chapter_id in completed_ids:
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
    # 3. BE-06 — verify the student attempted at least one graded exercise
    # ------------------------------------------------------------------
    if _chapter_has_ai_graded_exercise(chapter_data) and not _has_completed_attempt(db, chapter_id, uid):
        logger.warning(
            "complete_chapter: no completed exercise attempt found — uid=%r chapterId=%r",
            uid,
            chapter_id,
        )
        raise PreconditionFailedError(
            f"No completed exercise attempt found for chapter '{chapter_id}'. "
            "Complete at least one graded exercise before finishing the chapter."
        )

    # ------------------------------------------------------------------
    # 4. Build concept list for the progress summary prompt
    # ------------------------------------------------------------------
    concept_list = ", ".join(n.get("heading", "") for n in grammar_notes if n.get("heading"))
    logger.info(
        "complete_chapter: concept list for prompt — %r",
        concept_list or "(none)",
    )

    # ------------------------------------------------------------------
    # 5. Call Gemini — progress summary (BE-09: retry + None-check via gemini_utils)
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
    summary_response = generate_content_with_retry(client, model=_MODEL_ID, contents=summary_prompt)
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
    # 6. Calculate XP based on length
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
    # 7. Atomically finalize: re-check + ArrayUnion + Increment (BE-08, IMP-BE-01/02)
    # ------------------------------------------------------------------
    transaction = db.transaction()
    result = _finalize_completion(transaction, user_ref, chapter_id, xp_gained, progress_summary)

    logger.info(
        "complete_chapter: done — uid=%r chapterId=%r xp_gained=%d",
        uid,
        chapter_id,
        result["xp_gained"],
    )

    return result
