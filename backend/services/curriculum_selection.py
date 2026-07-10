"""Curriculum selection service.

Writes a user's selected concrete chapter variant for one canonical
curriculumChapterId. Read-side fallback/defaulting lives in the frontend and
content-cli activation code; this service only validates explicit selections.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from functools import lru_cache

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import Transaction, transactional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_db() -> FirestoreClient:
    return FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))


@transactional
def _set_curriculum_selection_tx(
    transaction: Transaction,
    db: FirestoreClient,
    uid: str,
    curriculum_chapter_id: str,
    chapter_id: str,
) -> dict:
    user_ref = db.collection("users").document(uid)
    chapter_ref = db.collection("chapters").document(chapter_id)

    user_snap = user_ref.get(transaction=transaction)
    if not user_snap.exists:
        raise ValueError(f"User '{uid}' not found in Firestore.")

    chapter_snap = chapter_ref.get(transaction=transaction)
    if not chapter_snap.exists:
        raise ValueError(f"Chapter '{chapter_id}' not found in Firestore.")

    user_data = user_snap.to_dict() or {}
    chapter = chapter_snap.to_dict() or {}
    actual_curriculum_chapter_id = chapter.get("curriculumChapterId")

    if actual_curriculum_chapter_id != curriculum_chapter_id:
        raise ValueError(
            f"Chapter '{chapter_id}' belongs to curriculumChapterId "
            f"{actual_curriculum_chapter_id!r}, not {curriculum_chapter_id!r}."
        )

    selected_by_slot = (
        user_data.get("curriculum", {}).get("selectedChapterIdsByCurriculumChapterId", {})
    )
    already_selected = selected_by_slot.get(curriculum_chapter_id) == chapter_id
    selectable = chapter.get("isSelectableAlternative") is not False
    if not selectable and not already_selected:
        raise PermissionError(f"Chapter '{chapter_id}' is not selectable for new curriculum choices.")

    now = datetime.now(UTC)
    transaction.update(
        user_ref,
        {
            f"curriculum.selectedChapterIdsByCurriculumChapterId.{curriculum_chapter_id}": chapter_id,
            f"curriculum.manualSelectionsByCurriculumChapterId.{curriculum_chapter_id}": now,
            "curriculum.updatedAt": now,
            "lastActive": now,
        },
    )

    logger.info(
        "set_curriculum_selection: user '%s' selected chapter '%s' for slot '%s'.",
        uid,
        chapter_id,
        curriculum_chapter_id,
    )
    return {
        "curriculum_chapter_id": curriculum_chapter_id,
        "chapter_id": chapter_id,
    }


def set_curriculum_selection(uid: str, curriculum_chapter_id: str, chapter_id: str) -> dict:
    """Validate and persist one explicit curriculum selection."""
    if not curriculum_chapter_id.strip():
        raise ValueError("curriculumChapterId must not be empty.")
    if not chapter_id.strip():
        raise ValueError("chapterId must not be empty.")

    db = _get_db()
    transaction = db.transaction()
    return _set_curriculum_selection_tx(transaction, db, uid, curriculum_chapter_id, chapter_id)
