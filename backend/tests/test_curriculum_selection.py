"""Tests for services/curriculum_selection.py."""

from unittest.mock import MagicMock, patch

import pytest

from services.curriculum_selection import set_curriculum_selection
from tests.conftest import FakeTransaction

UID = "user-123"
CURRICULUM_CHAPTER_ID = "b1_c1"
CHAPTER_ID = "b1_c1_airport"


def _make_db(user_data: dict, chapter_data: dict | None) -> MagicMock:
    db = MagicMock()

    user_snap = MagicMock(exists=True)
    user_snap.to_dict.return_value = user_data
    user_ref = MagicMock()
    user_ref.get.return_value = user_snap

    chapter_snap = MagicMock(exists=chapter_data is not None)
    chapter_snap.to_dict.return_value = chapter_data
    chapter_ref = MagicMock()
    chapter_ref.get.return_value = chapter_snap

    def _collection(name):
        col = MagicMock()
        if name == "users":
            col.document.return_value = user_ref
        elif name == "chapters":
            col.document.return_value = chapter_ref
        return col

    db.collection.side_effect = _collection
    db.transaction.side_effect = lambda: FakeTransaction()
    return db


def test_set_curriculum_selection_writes_manual_selection():
    db = _make_db(
        user_data={"curriculum": {"selectedChapterIdsByCurriculumChapterId": {}}},
        chapter_data={"curriculumChapterId": CURRICULUM_CHAPTER_ID},
    )

    with patch("services.curriculum_selection._get_db", return_value=db):
        result = set_curriculum_selection(UID, CURRICULUM_CHAPTER_ID, CHAPTER_ID)

    assert result == {"curriculum_chapter_id": CURRICULUM_CHAPTER_ID, "chapter_id": CHAPTER_ID}
    user_ref = db.collection("users").document(UID)
    written = user_ref.update.call_args.args[0]
    assert written[f"curriculum.selectedChapterIdsByCurriculumChapterId.{CURRICULUM_CHAPTER_ID}"] == CHAPTER_ID
    assert f"curriculum.manualSelectionsByCurriculumChapterId.{CURRICULUM_CHAPTER_ID}" in written
    assert "curriculum.updatedAt" in written


def test_set_curriculum_selection_rejects_hidden_unless_already_selected():
    db = _make_db(
        user_data={"curriculum": {"selectedChapterIdsByCurriculumChapterId": {}}},
        chapter_data={"curriculumChapterId": CURRICULUM_CHAPTER_ID, "isSelectableAlternative": False},
    )

    with patch("services.curriculum_selection._get_db", return_value=db):
        with pytest.raises(PermissionError, match="not selectable"):
            set_curriculum_selection(UID, CURRICULUM_CHAPTER_ID, CHAPTER_ID)


def test_set_curriculum_selection_allows_hidden_when_already_selected():
    db = _make_db(
        user_data={"curriculum": {"selectedChapterIdsByCurriculumChapterId": {CURRICULUM_CHAPTER_ID: CHAPTER_ID}}},
        chapter_data={"curriculumChapterId": CURRICULUM_CHAPTER_ID, "isSelectableAlternative": False},
    )

    with patch("services.curriculum_selection._get_db", return_value=db):
        result = set_curriculum_selection(UID, CURRICULUM_CHAPTER_ID, CHAPTER_ID)

    assert result["chapter_id"] == CHAPTER_ID
