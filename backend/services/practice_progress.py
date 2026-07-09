"""
Practice progress service — marks a practice set as complete and awards XP.

Idempotent: if the practice set is already in the user's completedPracticeSetIds,
the function returns the same result without modifying Firestore or awarding XP again.

Unlike chapter completion, this has no slow external call (no Gemini), so the entire
idempotency check + XP award happens inside a single Firestore transaction
(IMP-BE-01) — simpler than services/progress.py's two-phase design, and race-free
by construction.

BE-06 note (judgement call — see also the final report): unlike chapters,
practice-set exercises (matching, etc.) are graded entirely client-side and never
write an `exercise_attempts` document, so that collection can't be used here as an
attempt-verification signal the way it is in services/progress.py. Gating
completion on "the parent chapter is already completed" was also considered and
rejected: frontend/src/app/pages/chapters/chapters.page.ts renders each practice
set's "start" button unconditionally whenever practiceSetIds exist, with no
completed-chapter check — so enforcing that server-side would reject a currently
legitimate, supported navigation path. Absent a real attempt-tracking signal (and
without inventing a new Firestore field, which AGENTS.md rules out), this function
does not enforce a BE-06 precondition; idempotency (each id can only ever grant XP
once) plus the active-user gate and per-user rate limit are the abuse mitigations
in place for this endpoint.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from functools import lru_cache

from google.cloud.firestore import ArrayUnion, Increment, Transaction, transactional
from google.cloud.firestore import Client as FirestoreClient

from constants import PRACTICE_XP

logger = logging.getLogger(__name__)


# IMP-BE-03: construct the Firestore client once and reuse it across
# invocations within the same process, instead of on every single request.
@lru_cache(maxsize=1)
def _get_db() -> FirestoreClient:
    return FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))


@transactional
def _complete_practice_tx(
    transaction: Transaction,
    db: FirestoreClient,
    user_ref,  # noqa: ANN001 - google.cloud.firestore.DocumentReference
    uid: str,
    practice_set_id: str,
) -> dict:
    """
    Atomically:
      1. Check idempotency (already completed -> return early, no XP).
      2. Verify the practice set document exists.
      3. ArrayUnion the id + Increment XP (BE-07, IMP-BE-02) — atomically, so
         two concurrent completions of the same practice set can't both grant
         XP (BE-08, IMP-BE-01).
    """
    user_snap = user_ref.get(transaction=transaction)
    if not user_snap.exists:
        raise ValueError(f"User '{uid}' not found in Firestore.")
    user_data = user_snap.to_dict() or {}
    progress = user_data.get("progress", {})
    completed_ids: list[str] = progress.get("completedPracticeSetIds", [])

    if practice_set_id in completed_ids:
        logger.info(
            "complete_practice: practice '%s' already completed for user '%s' — skipping.",
            practice_set_id,
            uid,
        )
        return {"practice_set_id": practice_set_id, "xp_gained": 0}

    ps_snap = db.collection("practice_sets").document(practice_set_id).get(transaction=transaction)
    if not ps_snap.exists:
        raise ValueError(f"Practice set '{practice_set_id}' not found in Firestore.")

    transaction.update(
        user_ref,
        {
            "progress.completedPracticeSetIds": ArrayUnion([practice_set_id]),
            "progress.xp": Increment(PRACTICE_XP),
            "lastActive": datetime.now(UTC),
        },
    )

    logger.info(
        "complete_practice: user '%s' completed practice '%s' — awarded %d XP.",
        uid,
        practice_set_id,
        PRACTICE_XP,
    )

    return {"practice_set_id": practice_set_id, "xp_gained": PRACTICE_XP}


def complete_practice(uid: str, practice_set_id: str) -> dict:
    """
    Idempotently marks a practice set as complete and awards PRACTICE_XP.

    Raises:
        ValueError — if the practice set or user document is not found.
    """
    logger.info("complete_practice: start — uid=%r practice_set_id=%r", uid, practice_set_id)
    db = _get_db()
    user_ref = db.collection("users").document(uid)
    transaction = db.transaction()
    return _complete_practice_tx(transaction, db, user_ref, uid, practice_set_id)
