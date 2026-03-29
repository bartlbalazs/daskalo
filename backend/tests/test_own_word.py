"""Tests for services/own_word.py — focusing on _sanitize_greek and the doc ID logic."""

import pytest

from services.own_word import _sanitize_greek


class TestSanitizeGreek:
    def test_plain_greek_word_unchanged(self):
        assert _sanitize_greek("δάσκαλος") == "δάσκαλος"

    def test_noun_with_article(self):
        assert _sanitize_greek("ο δάσκαλος") == "ο_δάσκαλος"

    def test_adjective_slash_format(self):
        # "καλός/ή/ό" — slashes replaced, no leading/trailing underscores
        assert _sanitize_greek("καλός/ή/ό") == "καλός_ή_ό"

    def test_adjective_slash_with_spaces(self):
        # "ήσυχος / ήσυχη / ήσυχο" — spaces+slashes collapsed to single underscore
        assert _sanitize_greek("ήσυχος / ήσυχη / ήσυχο") == "ήσυχος_ήσυχη_ήσυχο"

    def test_short_phrase(self):
        assert _sanitize_greek("καλημέρα σας") == "καλημέρα_σας"

    def test_multiple_spaces_collapsed(self):
        assert _sanitize_greek("καλή  νύχτα") == "καλή_νύχτα"

    def test_leading_trailing_spaces_stripped(self):
        assert _sanitize_greek("  θάλασσα  ") == "θάλασσα"

    def test_empty_string_returns_fallback(self):
        assert _sanitize_greek("") == "word"

    def test_only_slashes_returns_fallback(self):
        assert _sanitize_greek("///") == "word"

    def test_truncates_at_80_chars(self):
        long = "α" * 100
        result = _sanitize_greek(long)
        assert len(result) == 80

    def test_two_different_words_produce_different_ids(self):
        """Core regression: distinct Greek words must not collide."""
        id1 = _sanitize_greek("ο δάσκαλος")
        id2 = _sanitize_greek("η θάλασσα")
        assert id1 != id2

    def test_doc_id_format(self):
        """Doc ID constructed the same way as in create_own_word should be unique per word."""
        chapter_id = "b1_c1_seaside_chills_in_modern_korinthos"
        words = ["ο δάσκαλος", "η θάλασσα", "καλός/ή/ό", "τρέχω"]
        doc_ids = {f"{chapter_id}__{_sanitize_greek(w)}" for w in words}
        assert len(doc_ids) == len(words), "Each word must produce a unique doc ID"
