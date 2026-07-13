"""
Tests for nodes/package_output.py — asset-role routing, locking in CC-01/CC-02's
fix (IMP-CC-08).

Every state built here uses a variant_id/topic deliberately containing both
"passage" and "grammar" as substrings once combined with the asset filename
prefix — this recreates the exact scenario that used to break filename-
substring routing (see docs/planning/BUGS.md CC-01/CC-02):
  - `passageAudioPath` must come from the dedicated `passage_audio_path` state
    field, never from scanning `audio_files` for a "passage" substring match.
  - Audio routing to `assets/audio/grammar/` / `assets/audio/conversation/`
    must be driven purely by each `audio_assets` entry's `role`, never by
    checking whether the (prefixed) filename contains "_grammar_" or "_conv_".
  - A `matching` exercise's pair audioPath must be rewritten to a ZIP-relative
    path (CC-03), the same way package_practice_output.py already does.
"""

import json
import zipfile
from pathlib import Path

import pytest

from models.content_models import (
    ConversationData,
    ConversationExercise,
    ConversationLine,
    GrammarExample,
    GrammarNote,
    MatchingData,
    MatchingExercise,
    MatchingPair,
    PassageSentence,
    VocabularyItem,
)
from nodes.package_output import package_output

# variant_id deliberately contains both "passage" and "grammar" as substrings —
# once combined with the "{variant_id}_{order:02d}_" asset prefix, *every*
# generated filename (including plain vocab clips) contains both substrings,
# e.g. "..._a_passage_to_grammar_town_01_vocab_00_test.mp3".
_VARIANT_ID = "b1_c1_a_passage_to_grammar_town"
_PREFIX = f"{_VARIANT_ID}_01_"


def _write(path: Path, content: bytes = b"fake-audio-bytes") -> str:
    path.write_bytes(content)
    return str(path)


def _build_state(work_dir: Path) -> dict:
    vocab_audio = _write(work_dir / f"{_PREFIX}vocab_00_test.mp3")
    passage_audio = _write(work_dir / f"{_PREFIX}passage.mp3")
    grammar_audio = _write(work_dir / f"{_PREFIX}grammar_00_ex_00.mp3")
    conv_audio = _write(work_dir / f"{_PREFIX}conv_00_line_00_male_test.mp3")
    matching_audio = _write(work_dir / f"{_PREFIX}matching_00_pair_00_test.mp3")

    vocabulary = [VocabularyItem(greek="καλημέρα", english="good morning", audioPath=vocab_audio)]

    grammar_notes = [
        GrammarNote(
            heading="Test concept",
            explanation="Explanation",
            examples=[GrammarExample(greek="Παράδειγμα", english="Example", audioPath=grammar_audio)],
        )
    ]

    conversation_exercise = ConversationExercise(
        type="conversation",
        prompt="Listen to the conversation",
        data=ConversationData(
            topic_description="A test conversation",
            lines=[ConversationLine(speaker="male", text="Γεια σου", translation="Hello", audioPath=conv_audio)],
            checkpoints=[],
        ),
    )
    matching_exercise = MatchingExercise(
        type="matching",
        prompt="Match the words",
        data=MatchingData(pairs=[MatchingPair(greek="σκύλος", english="dog", audioPath=matching_audio)]),
    )

    # This mirrors exactly what generate_media.py now produces: a flat list of
    # every audio path (for logging/counting) plus a role-tagged manifest that
    # package_output must use instead of sniffing filenames.
    audio_files = [vocab_audio, passage_audio, grammar_audio, conv_audio, matching_audio]
    audio_assets = [
        {"role": "vocab", "path": vocab_audio},
        {"role": "passage", "path": passage_audio},
        {"role": "grammar", "path": grammar_audio},
        {"role": "conversation", "path": conv_audio},
        {"role": "matching", "path": matching_audio},
    ]

    return {
        "work_dir": str(work_dir),
        "variant_id": _VARIANT_ID,
        "book_id": "book_1",
        "curriculum_chapter_id": "b1_c1",
        "chapter_topic": "A passage to grammar town",
        "chapter_title": "A Passage To Grammar Town",
        "chapter_order": 1,
        "chapter_summary": "summary",
        "lesson_length": "short",
        "chapter_introduction": "intro",
        "language_skill": "skill",
        "passage": [PassageSentence(greek="Γεια", english="Hello")],
        "passage_audio_path": passage_audio,
        "sentence_audio_files": [],
        "chapter_image_path": "",
        "grammar_notes": grammar_notes,
        "grammar_summary": "",
        "vocabulary": vocabulary,
        "exercises": [conversation_exercise, matching_exercise],
        "audio_files": audio_files,
        "audio_assets": audio_assets,
        "image_files": [],
    }


def test_passage_audio_path_uses_dedicated_field_not_filename_sniffing(tmp_path):
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        descriptor = json.loads(zf.read("descriptor.json"))

    # CC-01: passageAudioPath must point at the real passage clip, not the
    # vocab clip that also happens to contain "passage" in its (prefixed) name
    # and is listed *before* the passage clip in audio_files.
    assert descriptor["chapter"]["passageAudioPath"] == f"assets/audio/{_PREFIX}passage.mp3"


def test_descriptor_includes_legacy_passage_text_from_structured_passage(tmp_path):
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        descriptor = json.loads(zf.read("descriptor.json"))

    assert descriptor["chapter"]["passage"] == [{"greek": "Γεια", "english": "Hello"}]
    assert descriptor["chapter"]["passage_text"] == "Γεια"


def test_package_output_rejects_empty_passage(tmp_path):
    state = _build_state(tmp_path)
    state["passage"] = []

    with pytest.raises(ValueError, match="Cannot package chapter without a passage"):
        package_output(state)


def test_grammar_role_audio_routes_to_grammar_folder_others_do_not(tmp_path):
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        names = zf.namelist()

    grammar_folder_files = [n for n in names if n.startswith("assets/audio/grammar/")]
    assert grammar_folder_files == [f"assets/audio/grammar/{_PREFIX}grammar_00_ex_00.mp3"]

    # CC-02: the vocab clip's filename contains "_grammar_" (via the poisoned
    # "..._to_grammar_town..." prefix), but its *role* is "vocab" — it must
    # land in the assets/audio root, never in assets/audio/grammar/.
    vocab_files = [n for n in names if "vocab_00_test" in n]
    assert vocab_files == [f"assets/audio/{_PREFIX}vocab_00_test.mp3"]


def test_conversation_role_audio_routes_to_conversation_folder(tmp_path):
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        names = zf.namelist()

    conv_files = [n for n in names if n.startswith("assets/audio/conversation/")]
    assert conv_files == [f"assets/audio/conversation/{_PREFIX}conv_00_line_00_male_test.mp3"]


def test_matching_role_audio_is_packed_in_default_audio_folder(tmp_path):
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        names = zf.namelist()

    matching_files = [n for n in names if "matching_00_pair_00" in n]
    assert matching_files == [f"assets/audio/{_PREFIX}matching_00_pair_00_test.mp3"]


def test_matching_exercise_pair_audio_path_rewritten_to_relative_zip_path(tmp_path):
    """CC-03: matching pair audioPath must be rewritten the same way
    package_practice_output.py already does for practice sets, instead of
    leaking the absolute local work_dir path into the descriptor.
    """
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        descriptor = json.loads(zf.read("descriptor.json"))
        names = zf.namelist()

    matching_exercises = [ex for ex in descriptor["chapter"]["exercises"] if ex["type"] == "matching"]
    assert len(matching_exercises) == 1
    pair = matching_exercises[0]["data"]["pairs"][0]

    assert pair["audioPath"] == f"assets/audio/{_PREFIX}matching_00_pair_00_test.mp3"
    assert not pair["audioPath"].startswith("/")
    assert not Path(pair["audioPath"]).is_absolute()
    assert pair["audioPath"] in names


def test_conversation_line_audio_path_rewritten_to_relative_zip_path(tmp_path):
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        descriptor = json.loads(zf.read("descriptor.json"))

    conversation_exercises = [ex for ex in descriptor["chapter"]["exercises"] if ex["type"] == "conversation"]
    line = conversation_exercises[0]["data"]["lines"][0]

    assert line["audioPath"] == f"assets/audio/conversation/{_PREFIX}conv_00_line_00_male_test.mp3"


def test_chapter_descriptor_includes_curriculum_selection_fields(tmp_path):
    state = _build_state(tmp_path)

    result = package_output(state)

    with zipfile.ZipFile(result["output_zip_path"]) as zf:
        descriptor = json.loads(zf.read("descriptor.json"))

    chapter = descriptor["chapter"]
    assert chapter["isSelectableAlternative"] is True
    assert isinstance(chapter["generatedAt"], str)
    assert chapter["generatedAt"].endswith("+00:00")
