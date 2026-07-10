"""Tests for content-cli user activation curriculum defaulting."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from main import _build_curriculum_selection


def _snap(doc_id: str, data: dict) -> MagicMock:
    snap = MagicMock()
    snap.id = doc_id
    snap.to_dict.return_value = data
    return snap


def _db(chapters: list[tuple[str, dict]]) -> MagicMock:
    db = MagicMock()
    chapters_collection = MagicMock()
    chapters_collection.stream.return_value = [_snap(doc_id, data) for doc_id, data in chapters]
    db.collection.return_value = chapters_collection
    return db


def test_build_curriculum_selection_uses_newest_selectable_for_automatic_rows():
    db = _db(
        [
            ("old", {"curriculumChapterId": "b1_c1", "generatedAt": datetime(2024, 1, 1, tzinfo=UTC)}),
            ("new", {"curriculumChapterId": "b1_c1", "generatedAt": datetime(2025, 1, 1, tzinfo=UTC)}),
        ]
    )

    selected, repair_needed = _build_curriculum_selection(db, user={})

    assert selected == {"b1_c1": "new"}
    assert repair_needed == {}


def test_build_curriculum_selection_preserves_manual_selection():
    db = _db(
        [
            ("old", {"curriculumChapterId": "b1_c1", "generatedAt": datetime(2024, 1, 1, tzinfo=UTC)}),
            ("new", {"curriculumChapterId": "b1_c1", "generatedAt": datetime(2025, 1, 1, tzinfo=UTC)}),
        ]
    )
    user = {
        "curriculum": {
            "selectedChapterIdsByCurriculumChapterId": {"b1_c1": "old"},
            "manualSelectionsByCurriculumChapterId": {"b1_c1": datetime(2026, 1, 1, tzinfo=UTC)},
        }
    }

    selected, repair_needed = _build_curriculum_selection(db, user=user)

    assert selected == {"b1_c1": "old"}
    assert repair_needed == {}


def test_build_curriculum_selection_preserves_selected_hidden_variant_when_no_selectable_exists():
    db = _db([("hidden", {"curriculumChapterId": "b1_c1", "isSelectableAlternative": False})])
    user = {"curriculum": {"selectedChapterIdsByCurriculumChapterId": {"b1_c1": "hidden"}}}

    selected, repair_needed = _build_curriculum_selection(db, user=user)

    assert selected == {"b1_c1": "hidden"}
    assert repair_needed == {}


def test_build_curriculum_selection_reports_missing_manual_selection_for_repair():
    db = _db([("new", {"curriculumChapterId": "b1_c1", "generatedAt": datetime(2025, 1, 1, tzinfo=UTC)})])
    user = {
        "curriculum": {
            "selectedChapterIdsByCurriculumChapterId": {"b1_c2": "deleted"},
            "manualSelectionsByCurriculumChapterId": {"b1_c2": datetime(2026, 1, 1, tzinfo=UTC)},
        }
    }

    selected, repair_needed = _build_curriculum_selection(db, user=user)

    assert selected == {"b1_c1": "new", "b1_c2": "deleted"}
    assert repair_needed == {"b1_c2": "deleted"}
