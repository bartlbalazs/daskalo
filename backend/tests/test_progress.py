"""
Tests for services/progress.py — complete_chapter().

Covers the fast idempotent path, BE-06 (attempt verification, gated on whether
the chapter has any AI-graded exercise at all), the Gemini-call integration via
gemini_utils, and (BE-08/IMP-BE-01/IMP-BE-02) that the final write uses
ArrayUnion/Increment inside a transaction that re-checks the race.
"""

from unittest.mock import MagicMock, patch

import pytest
from google.cloud.firestore import ArrayUnion, Increment

from services.progress import complete_chapter
from tests.conftest import FakeTransaction

UID = "user-123"
CHAPTER_ID = "chapter-xyz"

CHAPTER_NO_AI_EXERCISES = {
    "title": "Lost in Monastiraki",
    "summary": "Wandering the flea market.",
    "length": "short",
    "grammarNotes": [{"heading": "The Accusative Case"}],
    "exercises": [{"type": "slang_matcher"}, {"type": "matching"}],
}

CHAPTER_WITH_AI_EXERCISE = {
    **CHAPTER_NO_AI_EXERCISES,
    "length": "medium",
    "exercises": [{"type": "slang_matcher"}, {"type": "translation_challenge"}],
}


def _make_query_mock(has_results: bool) -> MagicMock:
    query = MagicMock()
    query.where.return_value = query
    query.limit.return_value = query
    query.stream.return_value = [MagicMock()] if has_results else []
    return query


def _make_db(
    chapter_data: dict | None,
    user_data: dict | None,
    has_completed_attempt: bool = True,
) -> MagicMock:
    db = MagicMock()

    chapter_snap = MagicMock(exists=chapter_data is not None)
    chapter_snap.to_dict.return_value = chapter_data
    chapter_ref = MagicMock()
    chapter_ref.get.return_value = chapter_snap

    user_snap = MagicMock(exists=user_data is not None)
    user_snap.to_dict.return_value = user_data
    user_ref = MagicMock()
    user_ref.get.return_value = user_snap

    attempts_query = _make_query_mock(has_completed_attempt)

    def _collection(name):
        if name == "chapters":
            col = MagicMock()
            col.document.return_value = chapter_ref
            return col
        if name == "users":
            col = MagicMock()
            col.document.return_value = user_ref
            return col
        if name == "exercise_attempts":
            return attempts_query
        return MagicMock()

    db.collection.side_effect = _collection
    db.transaction.side_effect = lambda: FakeTransaction()
    return db


def _make_gemini_client(summary_text: str = "You did great with the accusative case today.") -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.text = summary_text
    client.models.generate_content.return_value = response
    return client


# ---------------------------------------------------------------------------
# Happy path — chapter with no AI-graded exercises (BE-06 check skipped)
# ---------------------------------------------------------------------------


def test_complete_chapter_happy_path_no_ai_graded_exercises():
    db = _make_db(
        chapter_data=CHAPTER_NO_AI_EXERCISES,
        user_data={"progress": {"completedChapterIds": [], "xp": 0}},
        has_completed_attempt=False,  # irrelevant — chapter has no AI-graded exercises
    )
    client = _make_gemini_client()

    with (
        patch("services.progress._get_db", return_value=db),
        patch("services.progress._get_client", return_value=client),
    ):
        result = complete_chapter(uid=UID, chapter_id=CHAPTER_ID)

    assert result["chapter_id"] == CHAPTER_ID
    assert result["xp_gained"] == 100  # "short" length
    assert result["progress_summary"] == "You did great with the accusative case today."
    assert result["completed_chapter_ids"] == [CHAPTER_ID]

    user_ref = db.collection("users").document(UID)
    written = user_ref.update.call_args.args[0]
    assert written["progress.xp"] == Increment(100)
    assert written["progress.completedChapterIds"] == ArrayUnion([CHAPTER_ID])


# ---------------------------------------------------------------------------
# BE-06 — chapter WITH an AI-graded exercise requires a completed attempt
# ---------------------------------------------------------------------------


def test_complete_chapter_with_ai_exercise_and_completed_attempt_succeeds():
    db = _make_db(
        chapter_data=CHAPTER_WITH_AI_EXERCISE,
        user_data={"progress": {"completedChapterIds": [], "xp": 0}},
        has_completed_attempt=True,
    )
    client = _make_gemini_client()

    with (
        patch("services.progress._get_db", return_value=db),
        patch("services.progress._get_client", return_value=client),
    ):
        result = complete_chapter(uid=UID, chapter_id=CHAPTER_ID)

    assert result["xp_gained"] == 150  # "medium" length


def test_complete_chapter_with_ai_exercise_and_no_attempt_raises_precondition():
    from callable_helpers import PreconditionFailedError

    db = _make_db(
        chapter_data=CHAPTER_WITH_AI_EXERCISE,
        user_data={"progress": {"completedChapterIds": [], "xp": 0}},
        has_completed_attempt=False,
    )
    client = _make_gemini_client()

    with (
        patch("services.progress._get_db", return_value=db),
        patch("services.progress._get_client", return_value=client),
    ):
        with pytest.raises(PreconditionFailedError, match="No completed exercise attempt"):
            complete_chapter(uid=UID, chapter_id=CHAPTER_ID)

    # Must fail before ever calling Gemini.
    client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# Idempotency — already completed skips both BE-06 check and Gemini call
# ---------------------------------------------------------------------------


def test_complete_chapter_already_completed_is_idempotent():
    db = _make_db(
        chapter_data=CHAPTER_WITH_AI_EXERCISE,
        user_data={
            "progress": {
                "completedChapterIds": [CHAPTER_ID],
                "lastProgressSummary": "Previously recorded summary.",
                "xp": 500,
            }
        },
        has_completed_attempt=False,  # would fail BE-06 if it were (wrongly) checked
    )
    client = _make_gemini_client()

    with (
        patch("services.progress._get_db", return_value=db),
        patch("services.progress._get_client", return_value=client),
    ):
        result = complete_chapter(uid=UID, chapter_id=CHAPTER_ID)

    assert result == {
        "chapter_id": CHAPTER_ID,
        "xp_gained": 0,
        "progress_summary": "Previously recorded summary.",
        "completed_chapter_ids": [CHAPTER_ID],
    }
    client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


def test_complete_chapter_raises_when_chapter_not_found():
    db = _make_db(chapter_data=None, user_data={"progress": {}})

    with patch("services.progress._get_db", return_value=db):
        with pytest.raises(ValueError, match="Chapter"):
            complete_chapter(uid=UID, chapter_id=CHAPTER_ID)


def test_complete_chapter_raises_when_user_not_found():
    db = _make_db(chapter_data=CHAPTER_NO_AI_EXERCISES, user_data=None)

    with patch("services.progress._get_db", return_value=db):
        with pytest.raises(ValueError, match="User"):
            complete_chapter(uid=UID, chapter_id=CHAPTER_ID)


# ---------------------------------------------------------------------------
# BE-08/IMP-BE-01 — race: a concurrent request wins while this one waits on Gemini
# ---------------------------------------------------------------------------


def test_complete_chapter_finalize_detects_concurrent_winner():
    """If another request's transaction commits the completion while this request
    was blocked on the (slow) Gemini call, the re-check inside _finalize_completion
    must detect that and avoid granting XP a second time."""
    db = _make_db(
        chapter_data=CHAPTER_NO_AI_EXERCISES,
        user_data={"progress": {"completedChapterIds": [], "xp": 0}},
    )
    client = _make_gemini_client()

    user_ref = db.collection("users").document(UID)
    # First .get() (non-transactional, in complete_chapter's own flow) -> not completed yet.
    not_completed_snap = MagicMock(exists=True)
    not_completed_snap.to_dict.return_value = {"progress": {"completedChapterIds": [], "xp": 0}}
    # Second .get() (transactional, inside _finalize_completion) -> a concurrent
    # request has already committed the completion in the meantime.
    now_completed_snap = MagicMock(exists=True)
    now_completed_snap.to_dict.return_value = {
        "progress": {
            "completedChapterIds": [CHAPTER_ID],
            "lastProgressSummary": "The other request's summary.",
            "xp": 100,
        }
    }
    user_ref.get.side_effect = [not_completed_snap, now_completed_snap]

    with (
        patch("services.progress._get_db", return_value=db),
        patch("services.progress._get_client", return_value=client),
    ):
        result = complete_chapter(uid=UID, chapter_id=CHAPTER_ID)

    assert result["xp_gained"] == 0
    assert result["progress_summary"] == "The other request's summary."
    user_ref.update.assert_not_called()


# ---------------------------------------------------------------------------
# XP tiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("length", "expected_xp"),
    [("short", 100), ("medium", 150), ("long", 200), ("unknown-length", 100)],
)
def test_complete_chapter_xp_by_length(length: str, expected_xp: int):
    chapter_data = {**CHAPTER_NO_AI_EXERCISES, "length": length}
    db = _make_db(chapter_data=chapter_data, user_data={"progress": {"completedChapterIds": [], "xp": 0}})
    client = _make_gemini_client()

    with (
        patch("services.progress._get_db", return_value=db),
        patch("services.progress._get_client", return_value=client),
    ):
        result = complete_chapter(uid=UID, chapter_id=CHAPTER_ID)

    assert result["xp_gained"] == expected_xp
