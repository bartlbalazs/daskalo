"""
Tests for services/practice_progress.py — complete_practice().

Covers idempotency, not-found errors, and (BE-07/BE-08/IMP-BE-01/IMP-BE-02)
that XP is granted via Increment and the id via ArrayUnion, inside a single
transaction.
"""

from unittest.mock import MagicMock, patch

import pytest
from google.cloud.firestore import ArrayUnion, Increment

from constants import PRACTICE_XP
from services.practice_progress import complete_practice
from tests.conftest import FakeTransaction

UID = "user-123"
PRACTICE_SET_ID = "ps_p1_c1_airport_01"


def _make_db(user_data: dict | None, ps_exists: bool = True) -> MagicMock:
    db = MagicMock()

    user_snap = MagicMock(exists=user_data is not None)
    user_snap.to_dict.return_value = user_data
    user_ref = MagicMock()
    user_ref.get.return_value = user_snap

    ps_snap = MagicMock(exists=ps_exists)
    ps_snap.to_dict.return_value = {"chapterId": "chapter-xyz"} if ps_exists else None
    ps_ref = MagicMock()
    ps_ref.get.return_value = ps_snap

    def _collection(name):
        col = MagicMock()
        if name == "users":
            col.document.return_value = user_ref
        elif name == "practice_sets":
            col.document.return_value = ps_ref
        return col

    db.collection.side_effect = _collection
    db.transaction.side_effect = lambda: FakeTransaction()
    return db


def test_complete_practice_happy_path_awards_xp():
    db = _make_db(user_data={"progress": {"completedPracticeSetIds": [], "xp": 300}})

    with patch("services.practice_progress._get_db", return_value=db):
        result = complete_practice(uid=UID, practice_set_id=PRACTICE_SET_ID)

    assert result == {"practice_set_id": PRACTICE_SET_ID, "xp_gained": PRACTICE_XP}

    user_ref = db.collection("users").document(UID)
    user_ref.update.assert_called_once()
    written = user_ref.update.call_args.args[0]
    # BE-07/IMP-BE-02: XP must be granted via Increment, not a stale-read sum.
    assert written["progress.xp"] == Increment(PRACTICE_XP)
    # BE-08/IMP-BE-02: the id must be appended via ArrayUnion, not a Python list.
    assert written["progress.completedPracticeSetIds"] == ArrayUnion([PRACTICE_SET_ID])


def test_complete_practice_idempotent_when_already_completed():
    db = _make_db(user_data={"progress": {"completedPracticeSetIds": [PRACTICE_SET_ID], "xp": 300}})

    with patch("services.practice_progress._get_db", return_value=db):
        result = complete_practice(uid=UID, practice_set_id=PRACTICE_SET_ID)

    assert result == {"practice_set_id": PRACTICE_SET_ID, "xp_gained": 0}
    user_ref = db.collection("users").document(UID)
    user_ref.update.assert_not_called()


def test_complete_practice_raises_when_user_not_found():
    db = _make_db(user_data=None)

    with patch("services.practice_progress._get_db", return_value=db):
        with pytest.raises(ValueError, match="not found"):
            complete_practice(uid=UID, practice_set_id=PRACTICE_SET_ID)


def test_complete_practice_raises_when_practice_set_not_found():
    db = _make_db(user_data={"progress": {"completedPracticeSetIds": [], "xp": 0}}, ps_exists=False)

    with patch("services.practice_progress._get_db", return_value=db):
        with pytest.raises(ValueError, match="Practice set"):
            complete_practice(uid=UID, practice_set_id=PRACTICE_SET_ID)

    user_ref = db.collection("users").document(UID)
    user_ref.update.assert_not_called()


def test_complete_practice_handles_missing_progress_dict():
    """A brand-new user with no `progress` key yet must not crash."""
    db = _make_db(user_data={})

    with patch("services.practice_progress._get_db", return_value=db):
        result = complete_practice(uid=UID, practice_set_id=PRACTICE_SET_ID)

    assert result["xp_gained"] == PRACTICE_XP
