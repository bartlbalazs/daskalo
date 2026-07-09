"""Tests for services/own_word.py — _sanitize_greek, doc ID logic, and the
full create_own_word pipeline (IMP-BE-08)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.own_word import _sanitize_greek, create_own_word


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


# ---------------------------------------------------------------------------
# create_own_word — full pipeline (IMP-BE-08)
# ---------------------------------------------------------------------------

USER_ID = "user-123"
CHAPTER_ID = "b1_c01_airport"
BOOK_ID = "b1"
ASSETS_BUCKET = "demo-daskalo-assets"


def _mock_gemini_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps(payload)
    return resp


def _mock_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.models.generate_content.return_value = _mock_gemini_response(payload)
    return client


def _mock_tts_client() -> MagicMock:
    tts_client = MagicMock()
    tts_response = MagicMock()
    tts_response.audio_content = b"fake-mp3-bytes"
    tts_client.synthesize_speech.return_value = tts_response
    return tts_client


class TestCreateOwnWord:
    def test_happy_path_returns_word_card(self):
        client = _mock_client({"greek": "ο δάσκαλος", "english": "the teacher"})
        db = MagicMock()

        with (
            patch("services.own_word._get_client", return_value=client),
            patch("services.own_word._get_db", return_value=db),
            patch("services.own_word.texttospeech.TextToSpeechClient", return_value=_mock_tts_client()),
            patch("services.own_word.storage.Client", return_value=MagicMock()),
        ):
            result = create_own_word(
                raw_input="δασκαλος",
                user_id=USER_ID,
                chapter_id=CHAPTER_ID,
                book_id=BOOK_ID,
                assets_bucket=ASSETS_BUCKET,
            )

        assert result["greek"] == "ο δάσκαλος"
        assert result["english"] == "the teacher"
        assert result["chapterId"] == CHAPTER_ID
        assert result["bookId"] == BOOK_ID
        assert result["alreadyExisted"] is False
        assert result["audioUrl"] == f"gs://{ASSETS_BUCKET}/users/{USER_ID}/own_words/{CHAPTER_ID}__ο_δάσκαλος.mp3"
        assert result["docId"] == f"{CHAPTER_ID}__ο_δάσκαλος"

        # Firestore write happened at the deterministic doc ID (BE-13's real dedup path).
        doc_ref = (
            db.collection.return_value.document.return_value.collection.return_value.document.return_value
        )
        doc_ref.set.assert_called_once()
        written = doc_ref.set.call_args.args[0]
        assert written["greek"] == "ο δάσκαλος"
        assert written["english"] == "the teacher"

    def test_non_greek_input_raises_value_error(self):
        client = _mock_client({"error": "not_greek"})

        with (
            patch("services.own_word._get_client", return_value=client),
            patch("services.own_word._get_db", return_value=MagicMock()),
        ):
            with pytest.raises(ValueError, match="does not appear to be a Greek word"):
                create_own_word(
                    raw_input="asdkjhasd",
                    user_id=USER_ID,
                    chapter_id=CHAPTER_ID,
                    book_id=BOOK_ID,
                    assets_bucket=ASSETS_BUCKET,
                )

    def test_malformed_gemini_json_raises_value_error(self):
        client = MagicMock()
        response = MagicMock()
        response.text = "not valid json {{"
        client.models.generate_content.return_value = response

        with (
            patch("services.own_word._get_client", return_value=client),
            patch("services.own_word._get_db", return_value=MagicMock()),
        ):
            with pytest.raises(ValueError, match="Could not process the input"):
                create_own_word(
                    raw_input="δάσκαλος",
                    user_id=USER_ID,
                    chapter_id=CHAPTER_ID,
                    book_id=BOOK_ID,
                    assets_bucket=ASSETS_BUCKET,
                )

    def test_incomplete_gemini_fields_raises_value_error(self):
        client = _mock_client({"greek": "", "english": ""})

        with (
            patch("services.own_word._get_client", return_value=client),
            patch("services.own_word._get_db", return_value=MagicMock()),
        ):
            with pytest.raises(ValueError, match="Could not generate a valid word card"):
                create_own_word(
                    raw_input="δάσκαλος",
                    user_id=USER_ID,
                    chapter_id=CHAPTER_ID,
                    book_id=BOOK_ID,
                    assets_bucket=ASSETS_BUCKET,
                )

    def test_empty_input_raises_value_error(self):
        with pytest.raises(ValueError, match="must not be empty"):
            create_own_word(
                raw_input="   ",
                user_id=USER_ID,
                chapter_id=CHAPTER_ID,
                book_id=BOOK_ID,
                assets_bucket=ASSETS_BUCKET,
            )

    def test_input_too_long_raises_value_error(self):
        with pytest.raises(ValueError, match="exceeds maximum allowed length"):
            create_own_word(
                raw_input="α" * 51,
                user_id=USER_ID,
                chapter_id=CHAPTER_ID,
                book_id=BOOK_ID,
                assets_bucket=ASSETS_BUCKET,
            )

    def test_adjective_slash_form_uses_first_form_for_tts(self):
        """TTS should only speak the main form, e.g. "καλός/ή/ό" -> "καλός"."""
        client = _mock_client({"greek": "καλός/ή/ό", "english": "good"})
        tts_client = _mock_tts_client()

        with (
            patch("services.own_word._get_client", return_value=client),
            patch("services.own_word._get_db", return_value=MagicMock()),
            patch("services.own_word.texttospeech.TextToSpeechClient", return_value=tts_client),
            patch("services.own_word.storage.Client", return_value=MagicMock()),
        ):
            create_own_word(
                raw_input="καλος",
                user_id=USER_ID,
                chapter_id=CHAPTER_ID,
                book_id=BOOK_ID,
                assets_bucket=ASSETS_BUCKET,
            )

        synthesis_input = tts_client.synthesize_speech.call_args.kwargs["input"]
        assert synthesis_input.text == "καλός"
