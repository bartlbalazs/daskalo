"""
Tests for nodes/build_context.py — the pure prior-knowledge accumulation helpers
(IMP-CC-08).

Covers _find_target_and_prior_chapters, _accumulate_grammar_headlines, and
_accumulate_vocabulary against the small fixture curriculum in conftest.py, plus
the build_context node itself with the curriculum loader monkeypatched out.
No real I/O and no LLM/TTS/GCS clients are involved anywhere in this module —
the accumulation logic is pure.
"""

import pytest

from nodes.build_context import (
    _accumulate_grammar_headlines,
    _accumulate_vocabulary,
    _find_target_and_prior_chapters,
    build_context,
)


class TestFindTargetAndPriorChapters:
    def test_first_chapter_has_no_prior_chapters(self, fixture_curriculum):
        book, chapter, prior = _find_target_and_prior_chapters(fixture_curriculum, "b1_c1")

        assert book["id"] == "book_1"
        assert chapter["id"] == "b1_c1"
        assert prior == []

    def test_second_chapter_in_same_book_sees_first_as_prior(self, fixture_curriculum):
        book, chapter, prior = _find_target_and_prior_chapters(fixture_curriculum, "b1_c2")

        assert chapter["id"] == "b1_c2"
        assert [c["id"] for c in prior] == ["b1_c1"]

    def test_chapter_in_second_book_sees_all_of_book_one_as_prior(self, fixture_curriculum):
        book, chapter, prior = _find_target_and_prior_chapters(fixture_curriculum, "b2_c1")

        assert book["id"] == "book_2"
        assert chapter["id"] == "b2_c1"
        assert [c["id"] for c in prior] == ["b1_c1", "b1_c2"]

    def test_unknown_chapter_id_raises_value_error(self, fixture_curriculum):
        with pytest.raises(ValueError, match="not found"):
            _find_target_and_prior_chapters(fixture_curriculum, "does_not_exist")


class TestAccumulateGrammarHeadlines:
    def test_no_prior_chapters_returns_none_literal(self):
        assert _accumulate_grammar_headlines([]) == "None"

    def test_collects_numbered_headlines_as_bullets_stripping_numbers(self):
        prior = [{"target_grammar": "1. The verb to be.\n2. Personal pronouns.\n"}]

        result = _accumulate_grammar_headlines(prior)

        assert result == "- The verb to be.\n- Personal pronouns."

    def test_deduplicates_across_chapters_keeping_first_seen_order(self):
        prior = [
            {"target_grammar": "1. The verb to be.\n"},
            {"target_grammar": "1. Definite articles.\n2. The verb to be.\n"},
        ]

        result = _accumulate_grammar_headlines(prior)

        # "The verb to be." must appear exactly once, in first-seen order —
        # even though it's re-numbered "2." the second time it appears.
        assert result == "- The verb to be.\n- Definite articles."

    def test_ignores_lines_that_are_not_numbered_headlines(self):
        prior = [{"target_grammar": "Some prose that is not a numbered headline.\n1. Real headline.\n"}]

        result = _accumulate_grammar_headlines(prior)

        assert result == "- Real headline."

    def test_missing_target_grammar_field_does_not_crash(self):
        assert _accumulate_grammar_headlines([{}]) == "None"


class TestAccumulateVocabulary:
    def test_no_prior_chapters_returns_empty_list(self):
        assert _accumulate_vocabulary([]) == []

    def test_collects_vocabulary_preserving_order(self):
        prior = [{"mandatory_vocabulary": ["είμαι (I am)", "εσύ (you)"]}]

        assert _accumulate_vocabulary(prior) == ["είμαι (I am)", "εσύ (you)"]

    def test_deduplicates_across_chapters_keeping_first_seen_order(self):
        prior = [
            {"mandatory_vocabulary": ["είμαι (I am)", "εσύ (you)"]},
            {"mandatory_vocabulary": ["ο (the)", "είμαι (I am)"]},
        ]

        result = _accumulate_vocabulary(prior)

        assert result == ["είμαι (I am)", "εσύ (you)", "ο (the)"]

    def test_missing_mandatory_vocabulary_field_does_not_crash(self):
        assert _accumulate_vocabulary([{}]) == []


class TestBuildContextNode:
    """The full node, still fully offline: the curriculum loader is monkeypatched
    so no real filesystem YAML files are read.
    """

    def test_returns_expected_state_update_for_second_chapter(self, fixture_curriculum, monkeypatch):
        monkeypatch.setattr("nodes.build_context.load_curriculum", lambda root_dir: fixture_curriculum)

        result = build_context({"curriculum_chapter_id": "b1_c2"})

        assert result["cefr_level"] == "A1.1"
        assert result["target_grammar"] == "1. Definite articles.\n2. The verb to be.\n"
        assert result["language_skill"] == "Skill for b1_c2"
        assert result["mandatory_vocabulary"] == ["ο (the)", "είμαι (I am)"]
        assert result["accumulated_grammar"] == "- The verb to be.\n- Personal pronouns."
        assert result["accumulated_vocabulary"] == ["είμαι (I am)", "εσύ (you)"]

    def test_first_chapter_has_no_accumulated_knowledge(self, fixture_curriculum, monkeypatch):
        monkeypatch.setattr("nodes.build_context.load_curriculum", lambda root_dir: fixture_curriculum)

        result = build_context({"curriculum_chapter_id": "b1_c1"})

        assert result["accumulated_grammar"] == "None"
        assert result["accumulated_vocabulary"] == []

    def test_second_book_cefr_level_reflects_its_own_book_not_the_first(self, fixture_curriculum, monkeypatch):
        monkeypatch.setattr("nodes.build_context.load_curriculum", lambda root_dir: fixture_curriculum)

        result = build_context({"curriculum_chapter_id": "b2_c1"})

        assert result["cefr_level"] == "A2.1"
        assert result["accumulated_vocabulary"] == ["είμαι (I am)", "εσύ (you)", "ο (the)"]

    def test_raises_for_unknown_chapter(self, fixture_curriculum, monkeypatch):
        monkeypatch.setattr("nodes.build_context.load_curriculum", lambda root_dir: fixture_curriculum)

        with pytest.raises(ValueError, match="not found"):
            build_context({"curriculum_chapter_id": "does_not_exist"})
