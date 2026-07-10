"""Onboarding service helpers."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from google.cloud.firestore import SERVER_TIMESTAMP, Transaction, transactional
from google.cloud.firestore import Client as FirestoreClient

logger = logging.getLogger(__name__)

HOW_IT_WORKS_KEY = "howItWorks"


@lru_cache(maxsize=1)
def _get_db() -> FirestoreClient:
    return FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))


@transactional
def _mark_onboarding_seen_tx(
    transaction: Transaction,
    user_ref,  # noqa: ANN001 - google.cloud.firestore.DocumentReference
    uid: str,
    key: str,
) -> dict:
    user_snap = user_ref.get(transaction=transaction)
    if not user_snap.exists:
        raise ValueError(f"User '{uid}' not found in Firestore.")

    user_data = user_snap.to_dict() or {}
    onboarding = user_data.get("onboarding", {})
    if onboarding is None:
        onboarding = {}
    if not isinstance(onboarding, dict):
        raise ValueError(f"User '{uid}' has malformed onboarding data.")

    if key == HOW_IT_WORKS_KEY:
        if onboarding.get("howItWorksSeenAt") is not None:
            return {"key": key, "alreadySeen": True}

        transaction.update(user_ref, {"onboarding.howItWorksSeenAt": SERVER_TIMESTAMP})
        logger.info("mark_onboarding_seen: marked %s for user '%s'.", key, uid)
        return {"key": key, "alreadySeen": False}

    raise ValueError(f"Unsupported onboarding key: {key!r}.")


def mark_onboarding_seen(uid: str, key: str) -> dict:
    """Idempotently marks one onboarding item as seen for the user."""
    db = _get_db()
    user_ref = db.collection("users").document(uid)
    transaction = db.transaction()
    return _mark_onboarding_seen_tx(transaction, user_ref, uid, key)
