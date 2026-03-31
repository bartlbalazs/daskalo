"""
Practice progress service — marks a practice set as complete and awards XP.

Idempotent: if the practice set is already in the user's completedPracticeSetIds,
the function returns the same result without modifying Firestore or awarding XP again.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from google.cloud.firestore import ArrayUnion, Client as FirestoreClient

logger = logging.getLogger(__name__)

PRACTICE_XP = 175


def complete_practice(uid: str, practice_set_id: str) -> dict:
    """
    Idempotently marks a practice set as complete and awards 175 XP.

    Steps:
      1. Load the user document to check if already completed.
      2. If already completed, return early with xp_gained=0 (idempotent).
      3. Verify the practice set document exists in Firestore.
      4. ArrayUnion the practice_set_id into completedPracticeSetIds and increment XP.
      5. Return { practice_set_id, xp_gained }.

    Raises:
        ValueError  — if the practice set or user document is not found.
    """
    logger.info("complete_practice: start — uid=%r practice_set_id=%r", uid, practice_set_id)
    db = FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))

    # 1. Load user
    user_ref = db.collection("users").document(uid)
    user_snap = user_ref.get()
    if not user_snap.exists:
        raise ValueError(f"User '{uid}' not found in Firestore.")

    user_data = user_snap.to_dict() or {}
    progress = user_data.get("progress", {})
    completed_ids: list[str] = progress.get("completedPracticeSetIds", [])

    # 2. Idempotent check
    if practice_set_id in completed_ids:
        logger.info(
            "complete_practice: practice '%s' already completed for user '%s' — skipping.",
            practice_set_id,
            uid,
        )
        return {"practice_set_id": practice_set_id, "xp_gained": 0}

    # 3. Verify practice set exists
    ps_snap = db.collection("practice_sets").document(practice_set_id).get()
    if not ps_snap.exists:
        raise ValueError(f"Practice set '{practice_set_id}' not found in Firestore.")

    # 4. Update user document
    current_xp: int = progress.get("xp", 0)
    user_ref.update(
        {
            "progress.completedPracticeSetIds": ArrayUnion([practice_set_id]),
            "progress.xp": current_xp + PRACTICE_XP,
            "lastActive": datetime.now(UTC),
        }
    )

    logger.info(
        "complete_practice: user '%s' completed practice '%s' — awarded %d XP (total %d).",
        uid,
        practice_set_id,
        PRACTICE_XP,
        current_xp + PRACTICE_XP,
    )

    return {"practice_set_id": practice_set_id, "xp_gained": PRACTICE_XP}
