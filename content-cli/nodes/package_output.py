"""
Node: package_output
Assembles the descriptor.json and all generated assets into a .zip file
ready for operator review and upload to the GCS ingestion bucket.

The descriptor follows the schema defined in docs/DATA_MODEL.md.
Internal-only fields (image_prompts, audioPath absolute paths) are
excluded or replaced with relative ZIP-internal paths during packaging.

Audio ZIP-folder routing is driven purely by the `role` tag that
`generate_media.py` attaches to every generated file in `state["audio_assets"]`
— never by sniffing filenames for substrings like "passage" or "_grammar_"
(see CC-01/CC-02 in docs/planning/BUGS.md).
"""

import json
import logging
import zipfile
from pathlib import Path

from models.content_models import (
    ConversationExercise,
    GrammarNote,
    ImageDescriptionExercise,
    MatchingExercise,
    PronunciationPracticeExercise,
    VocabularyItem,
)
from state import ContentState

logger = logging.getLogger(__name__)

# Audio ZIP-subfolder per semantic role. Any role not listed here (vocab,
# passage, pronunciation, matching) is packed directly under "assets/audio".
_ROLE_SUBDIR: dict[str, str] = {
    "conversation": "assets/audio/conversation",
    "grammar": "assets/audio/grammar",
}
_DEFAULT_AUDIO_SUBDIR = "assets/audio"


def _audio_subdir_for_role(role: str) -> str:
    """Return the ZIP subfolder for a given audio asset role (never filename-based)."""
    return _ROLE_SUBDIR.get(role, _DEFAULT_AUDIO_SUBDIR)


def package_output(state: ContentState) -> dict:
    """LangGraph node — build the final .zip file from generated content and assets."""
    work_dir = Path(state["work_dir"])
    chapter_id = state["variant_id"]
    output_zip = work_dir.parent / f"{chapter_id}.zip"

    book_id: str = state["book_id"]

    passage: list = state.get("passage", [])
    passage_for_descriptor = [s.model_dump() for s in passage]

    # CC-01: passage audio identity comes from the dedicated state field set by
    # generate_media.py, not from scanning audio_files for a "passage" substring.
    passage_audio_local_path = state.get("passage_audio_path", "")
    passage_audio_path = f"assets/audio/{Path(passage_audio_local_path).name}" if passage_audio_local_path else None

    sentence_audio_paths = []
    for p in state.get("sentence_audio_files", []):
        if p:
            sentence_audio_paths.append(f"assets/audio/sentences/{Path(p).name}")
        else:
            sentence_audio_paths.append("")

    descriptor = {
        "version": "1.0",
        "action": "create_or_update_chapter",
        "bookId": book_id,
        "chapter": {
            "id": chapter_id,
            "curriculumChapterId": state["curriculum_chapter_id"],
            "topic": state["chapter_topic"],
            "title": state["chapter_title"],
            "order": state["chapter_order"],
            "summary": state.get("chapter_summary", ""),
            "length": state.get("lesson_length", "medium"),
            "introduction": state.get("chapter_introduction", ""),
            "languageSkill": state.get("language_skill", ""),
            "passage": passage_for_descriptor,
            "passageAudioPath": passage_audio_path,
            "sentenceAudioPaths": sentence_audio_paths,
            "coverImagePath": (
                f"assets/images/{Path(state['chapter_image_path']).name}" if state.get("chapter_image_path") else None
            ),
            "grammarNotes": [_serialise_grammar_note(n) for n in state.get("grammar_notes", [])],
            "grammarSummary": state.get("grammar_summary", ""),
            "vocabulary": [_serialise_vocab(v) for v in state.get("vocabulary", [])],
            "exercises": [_serialise_exercise(ex) for ex in state.get("exercises", [])],
        },
    }

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("descriptor.json", json.dumps(descriptor, ensure_ascii=False, indent=2))

        # CC-02: route every audio file to its ZIP subfolder purely off the
        # `role` tag recorded in state["audio_assets"] — never off filename content.
        for asset in state.get("audio_assets", []):
            _pack_file(zf, asset["path"], _audio_subdir_for_role(asset.get("role", "")))

        for sent_path in state.get("sentence_audio_files", []):
            _pack_file(zf, sent_path, "assets/audio/sentences")

        # Chapter cover image
        _pack_file(zf, state.get("chapter_image_path", ""), "assets/images")

        # All other images (grammar notes + exercise images)
        for image_path in state.get("image_files", []):
            _pack_file(zf, image_path, "assets/images")

        file_count = len(zf.namelist())

    logger.info("Output ZIP created: %s (%d files)", output_zip, file_count)
    return {"output_zip_path": str(output_zip)}


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_grammar_note(note: GrammarNote) -> dict:
    """Serialise a GrammarNote, converting absolute imagePath/audioPath to ZIP-relative paths.
    Strips the internal image_prompt field (not needed in the descriptor).
    Includes grammar_table (Markdown string) if present.
    Per-example audioPath on each example is converted to a ZIP-relative path.
    """
    d = note.model_dump(exclude={"image_prompt"})
    if d.get("imagePath"):
        d["imagePath"] = f"assets/images/{Path(d['imagePath']).name}"
    # Legacy note-level audioPath (should be None for newly generated chapters)
    if d.get("audioPath"):
        d["audioPath"] = f"assets/audio/grammar/{Path(d['audioPath']).name}"
    # Per-example audio paths
    for example in d.get("examples", []):
        if example.get("audioPath"):
            example["audioPath"] = f"assets/audio/grammar/{Path(example['audioPath']).name}"
    return d


def _serialise_vocab(vocab: VocabularyItem) -> dict:
    """Serialise a VocabularyItem, converting absolute audioPath to a ZIP-relative path."""
    d = vocab.model_dump(exclude_none=False)
    if d.get("audioPath"):
        d["audioPath"] = f"assets/audio/{Path(d['audioPath']).name}"
    return d


def _serialise_exercise(exercise) -> dict:
    """Serialise an exercise Pydantic model for descriptor.json.

    - Strips internal-only fields (image_generation_prompt is now in image_prompts state,
      not on the model itself).
    - Converts absolute imagePath / audioPath to ZIP-relative paths.
    - For ConversationExercise, converts each line's audioPath to a ZIP-relative path.
    - For MatchingExercise, converts each pair's audioPath to a ZIP-relative path (CC-03;
      matching exercises aren't normally emitted for chapters, but are handled defensively
      the same way package_practice_output.py already does for practice sets).
    """
    if hasattr(exercise, "model_dump"):
        d = exercise.model_dump(exclude_none=False)
    else:
        d = dict(exercise)

    # Convert absolute paths to ZIP-internal relative paths
    if isinstance(exercise, ImageDescriptionExercise) and d.get("imagePath"):
        d["imagePath"] = f"assets/images/{Path(d['imagePath']).name}"

    if isinstance(exercise, PronunciationPracticeExercise) and d.get("audioPath"):
        d["audioPath"] = f"assets/audio/{Path(d['audioPath']).name}"

    if isinstance(exercise, ConversationExercise):
        for line in d.get("data", {}).get("lines", []):
            if line.get("audioPath"):
                line["audioPath"] = f"assets/audio/conversation/{Path(line['audioPath']).name}"

    if isinstance(exercise, MatchingExercise):
        for pair in d.get("data", {}).get("pairs", []):
            if pair.get("audioPath"):
                pair["audioPath"] = f"assets/audio/{Path(pair['audioPath']).name}"

    return d


def _pack_file(zf: zipfile.ZipFile, file_path: str, arc_dir: str) -> None:
    """Add a file to the ZIP under arc_dir if it exists. Silently skips empty paths."""
    if not file_path:
        return
    p = Path(file_path)
    if p.exists():
        zf.write(p, arcname=f"{arc_dir}/{p.name}")
        logger.debug("Packed: %s/%s", arc_dir, p.name)
    else:
        logger.warning("Asset file not found, skipping: %s", file_path)
