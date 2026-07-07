"""
Tests for services/ingest_helpers.py — asset path-rewriting during ingest
(IMP-CC-08).

Uses the `fake_bucket` fixture from conftest.py in place of a real GCS
`storage.Bucket` — no network calls are made anywhere in this module. Covers:
  - process_chapter_assets rewriting every `*Path` field to `*Url` (including
    matching-pair audio for chapters, CC-03, and conversation-line audio
    renamed consistently to `audioUrl` instead of keeping the `*Path` key
    name after rewriting its value, CC-08).
  - process_practice_set_assets doing the same for practice-set descriptors
    (the reference implementation CC-03/CC-08 bring chapters in line with).
"""

from __future__ import annotations

import io
import zipfile

import pytest

from services.ingest_helpers import process_chapter_assets, process_practice_set_assets


def _make_zip(files: dict[str, bytes]) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return zipfile.ZipFile(buf)


class TestProcessChapterAssets:
    def test_cover_image_path_becomes_url_and_path_key_removed(self, fake_bucket):
        zf = _make_zip({"assets/images/cover.jpg": b"img-bytes"})
        chapter = {"coverImagePath": "assets/images/cover.jpg"}

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        assert "coverImagePath" not in chapter
        assert chapter["coverImageUrl"] == "gs://test-assets-bucket/chapters/chapter-1/cover.jpg"

    def test_upload_asset_writes_correct_bytes_and_content_type(self, fake_bucket):
        zf = _make_zip({"assets/images/cover.jpg": b"some-jpeg-bytes"})
        chapter = {"coverImagePath": "assets/images/cover.jpg"}

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        blob = fake_bucket._blobs["chapters/chapter-1/cover.jpg"]
        blob.upload_from_string.assert_called_once_with(b"some-jpeg-bytes", content_type="image/jpeg")

    def test_vocabulary_audio_path_becomes_url(self, fake_bucket):
        zf = _make_zip({"assets/audio/vocab_00.mp3": b"audio"})
        chapter = {"vocabulary": [{"greek": "test", "english": "test", "audioPath": "assets/audio/vocab_00.mp3"}]}

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        vocab = chapter["vocabulary"][0]
        assert "audioPath" not in vocab
        assert vocab["audioUrl"] == "gs://test-assets-bucket/chapters/chapter-1/vocab_00.mp3"

    def test_grammar_note_image_and_per_example_audio_become_urls(self, fake_bucket):
        zf = _make_zip(
            {
                "assets/images/grammar_note_00.jpg": b"img",
                "assets/audio/grammar/grammar_00_ex_00.mp3": b"audio",
            }
        )
        chapter = {
            "grammarNotes": [
                {
                    "imagePath": "assets/images/grammar_note_00.jpg",
                    "examples": [{"audioPath": "assets/audio/grammar/grammar_00_ex_00.mp3"}],
                }
            ]
        }

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        note = chapter["grammarNotes"][0]
        assert "imagePath" not in note
        assert note["imageUrl"] == "gs://test-assets-bucket/chapters/chapter-1/grammar_note_00.jpg"
        example = note["examples"][0]
        assert "audioPath" not in example
        assert example["audioUrl"] == "gs://test-assets-bucket/chapters/chapter-1/grammar_00_ex_00.mp3"

    def test_sentence_audio_paths_become_urls_preserving_empty_slots(self, fake_bucket):
        zf = _make_zip({"assets/audio/sentences/sentence_00.mp3": b"audio"})
        chapter = {"sentenceAudioPaths": ["assets/audio/sentences/sentence_00.mp3", ""]}

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        assert "sentenceAudioPaths" not in chapter
        assert chapter["sentenceAudioUrls"] == [
            "gs://test-assets-bucket/chapters/chapter-1/sentence_00.mp3",
            "",
        ]

    def test_passage_audio_path_becomes_url(self, fake_bucket):
        zf = _make_zip({"assets/audio/passage.mp3": b"audio"})
        chapter = {"passageAudioPath": "assets/audio/passage.mp3"}

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        assert "passageAudioPath" not in chapter
        assert chapter["passageAudioUrl"] == "gs://test-assets-bucket/chapters/chapter-1/passage.mp3"

    def test_matching_exercise_pair_audio_uploaded_and_renamed(self, fake_bucket):
        """CC-03: chapter-level matching exercises (defensive — not normally
        emitted for chapters) must have their pair audio uploaded, mirroring
        how practice-set ingest already handles it.
        """
        zf = _make_zip({"assets/audio/matching_00_pair_00.mp3": b"audio"})
        chapter = {
            "exercises": [
                {
                    "type": "matching",
                    "data": {
                        "pairs": [
                            {
                                "greek": "test",
                                "english": "test",
                                "audioPath": "assets/audio/matching_00_pair_00.mp3",
                            }
                        ]
                    },
                }
            ]
        }

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        pair = chapter["exercises"][0]["data"]["pairs"][0]
        assert "audioPath" not in pair
        assert pair["audioUrl"] == "gs://test-assets-bucket/chapters/chapter-1/matching_00_pair_00.mp3"

    def test_conversation_line_audio_renamed_to_audio_url(self, fake_bucket):
        """CC-08: conversation line audio must be renamed audioPath -> audioUrl,
        consistent with every other asset, instead of keeping the `*Path` key
        after rewriting its value to a gs:// URL.
        """
        zf = _make_zip({"assets/audio/conversation/conv_00_line_00.mp3": b"audio"})
        chapter = {
            "exercises": [
                {
                    "type": "conversation",
                    "data": {
                        "lines": [
                            {
                                "speaker": "male",
                                "text": "Γεια",
                                "audioPath": "assets/audio/conversation/conv_00_line_00.mp3",
                            }
                        ]
                    },
                }
            ]
        }

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        line = chapter["exercises"][0]["data"]["lines"][0]
        assert "audioPath" not in line
        assert line["audioUrl"] == "gs://test-assets-bucket/chapters/chapter-1/conv_00_line_00.mp3"

    def test_conversation_line_audio_already_a_url_is_left_alone(self, fake_bucket):
        """Idempotency guard: a line whose audioPath is already a gs:// URL (e.g.
        re-ingesting an already-processed descriptor) must not be re-uploaded.
        """
        zf = _make_zip({})
        chapter = {
            "exercises": [
                {
                    "type": "conversation",
                    "data": {
                        "lines": [{"speaker": "male", "text": "Γεια", "audioPath": "gs://already/uploaded.mp3"}]
                    },
                }
            ]
        }

        process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)

        line = chapter["exercises"][0]["data"]["lines"][0]
        assert line["audioPath"] == "gs://already/uploaded.mp3"
        fake_bucket.blob.assert_not_called()

    def test_missing_asset_in_zip_raises_value_error(self, fake_bucket):
        zf = _make_zip({})
        chapter = {"coverImagePath": "assets/images/missing.jpg"}

        with pytest.raises(ValueError, match="not found in ZIP"):
            process_chapter_assets(zf, chapter, "chapter-1", fake_bucket)


class TestProcessPracticeSetAssets:
    def test_cover_image_path_becomes_url_under_practice_sets_prefix(self, fake_bucket):
        zf = _make_zip({"assets/images/practice_cover.jpg": b"img"})
        practice_set = {"coverImagePath": "assets/images/practice_cover.jpg"}

        process_practice_set_assets(zf, practice_set, "ps-1", fake_bucket)

        assert "coverImagePath" not in practice_set
        assert practice_set["coverImageUrl"] == "gs://test-assets-bucket/practice_sets/ps-1/practice_cover.jpg"

    def test_matching_pair_audio_uploaded_under_practice_sets_prefix(self, fake_bucket):
        zf = _make_zip({"assets/audio/matching_00_pair_00.mp3": b"audio"})
        practice_set = {
            "exercises": [
                {
                    "type": "matching",
                    "data": {
                        "pairs": [
                            {
                                "greek": "test",
                                "english": "test",
                                "audioPath": "assets/audio/matching_00_pair_00.mp3",
                            }
                        ]
                    },
                }
            ]
        }

        process_practice_set_assets(zf, practice_set, "ps-1", fake_bucket)

        pair = practice_set["exercises"][0]["data"]["pairs"][0]
        assert "audioPath" not in pair
        assert pair["audioUrl"] == "gs://test-assets-bucket/practice_sets/ps-1/matching_00_pair_00.mp3"

    def test_conversation_line_audio_renamed_to_audio_url(self, fake_bucket):
        zf = _make_zip({"assets/audio/conversation/conv_00_line_00.mp3": b"audio"})
        practice_set = {
            "exercises": [
                {
                    "type": "conversation",
                    "data": {
                        "lines": [
                            {
                                "speaker": "female",
                                "text": "Γεια",
                                "audioPath": "assets/audio/conversation/conv_00_line_00.mp3",
                            }
                        ]
                    },
                }
            ]
        }

        process_practice_set_assets(zf, practice_set, "ps-1", fake_bucket)

        line = practice_set["exercises"][0]["data"]["lines"][0]
        assert "audioPath" not in line
        assert line["audioUrl"] == "gs://test-assets-bucket/practice_sets/ps-1/conv_00_line_00.mp3"
