"""
Tests for prompts/content_prompts.py's conditional prompt-fragment helpers (CC-04).

`pronunciation_practice` only appears in the `long`-length exercise type pool
(models/content_models.py LESSON_CONFIG). `pronunciation_requirement_text` /
`pronunciation_review_note_text` must only request / check for it when it's
actually available for the given lesson length, so the generator and reviewer
prompts never contradict the allowed exercise-type set.
"""

from models.content_models import LESSON_CONFIG, LessonLength
from prompts.content_prompts import (
    pronunciation_requirement_text,
    pronunciation_review_note_text,
)


class TestPronunciationRequirementText:
    def test_non_empty_and_mentions_the_type_when_available(self):
        text = pronunciation_requirement_text(["pronunciation_practice", "conversation"])

        assert text.strip() != ""
        assert "pronunciation_practice" in text

    def test_empty_when_not_available(self):
        assert pronunciation_requirement_text(["conversation", "image_description"]) == ""

    def test_empty_for_empty_available_types(self):
        assert pronunciation_requirement_text([]) == ""


class TestPronunciationReviewNoteText:
    def test_non_empty_and_mentions_the_type_when_available(self):
        text = pronunciation_review_note_text(["pronunciation_practice"])

        assert text.strip() != ""
        assert "pronunciation_practice" in text

    def test_empty_when_not_available(self):
        assert pronunciation_review_note_text(["conversation"]) == ""


class TestAgreementWithLessonConfig:
    """Regression coverage for the actual bug (CC-04): the two helpers must agree
    with each other, and with LESSON_CONFIG's available_types, for every real
    lesson length — short/medium must never mention pronunciation_practice,
    long always must.
    """

    def test_short_excludes_pronunciation_practice(self):
        available = LESSON_CONFIG[LessonLength.SHORT]["available_types"]
        assert "pronunciation_practice" not in available
        assert pronunciation_requirement_text(available) == ""
        assert pronunciation_review_note_text(available) == ""

    def test_medium_excludes_pronunciation_practice(self):
        available = LESSON_CONFIG[LessonLength.MEDIUM]["available_types"]
        assert "pronunciation_practice" not in available
        assert pronunciation_requirement_text(available) == ""
        assert pronunciation_review_note_text(available) == ""

    def test_long_includes_pronunciation_practice(self):
        available = LESSON_CONFIG[LessonLength.LONG]["available_types"]
        assert "pronunciation_practice" in available
        assert pronunciation_requirement_text(available) != ""
        assert pronunciation_review_note_text(available) != ""

    def test_generator_and_reviewer_never_disagree_for_any_lesson_length(self):
        for length in LessonLength:
            available = LESSON_CONFIG[length]["available_types"]
            requirement_present = bool(pronunciation_requirement_text(available))
            review_note_present = bool(pronunciation_review_note_text(available))
            expected = "pronunciation_practice" in available

            assert requirement_present == expected
            assert review_note_present == expected
