"""
Node: package_output
Assembles the descriptor.json and all generated assets into a .zip file
ready for operator review and upload to the GCS ingestion bucket.

The descriptor follows the schema defined in docs/DATA_MODEL.md.
Internal-only fields (image_prompts, audioPath absolute paths) are
excluded or replaced with relative ZIP-internal paths during packaging.
"""

import json
import logging
import zipfile
from pathlib import Path

from models.content_models import (
    ConversationExercise,
    GrammarNote,
    ImageDescriptionExercise,
    PronunciationPracticeExercise,
    VocabularyItem,
)
from state import ContentState

logger = logging.getLogger(__name__)


def package_output(state: ContentState) -> dict:
    """LangGraph node — build the final .zip file from generated content and assets."""
    work_dir = Path(state["work_dir"])
    chapter_id = state["variant_id"]
    output_zip = work_dir.parent / f"{chapter_id}.zip"

    book_id: str = state["book_id"]

    passage: list = state.get("passage", [])
    passage_for_descriptor = [s.model_dump() for s in passage]

    passage_audio_path = None
    for p in state.get("audio_files", []):
        if "passage" in Path(p).name and not Path(p).name.startswith("conv_"):
            passage_audio_path = f"assets/audio/{Path(p).name}"
            break

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
            "languageSkill": state.get("language_skill", ""),
            "passage": passage_for_descriptor,
            "passageAudioPath": passage_audio_path,
            "sentenceAudioPaths": sentence_audio_paths,
            "coverImagePath": (
                f"assets/images/{Path(state['chapter_image_path']).name}" if state.get("chapter_image_path") else None
            ),
            "grammarNotes": [_serialise_grammar_note(n) for n in state.get("grammar_notes", [])],
            "vocabulary": [_serialise_vocab(v) for v in state.get("vocabulary", [])],
            "exercises": [_serialise_exercise(ex) for ex in state.get("exercises", [])],
        },
    }

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("descriptor.json", json.dumps(descriptor, ensure_ascii=False, indent=2))

        for audio_path in state.get("audio_files", []):
            name = Path(audio_path).name
            # Conversation line audio goes into a sub-folder for tidiness
            if name.startswith(f"{chapter_id}") and "_conv_" in name:
                _pack_file(zf, audio_path, "assets/audio/conversation")
            # Grammar note audio goes into its own sub-folder
            elif "_grammar_note_" in name and name.endswith("_audio.mp3"):
                _pack_file(zf, audio_path, "assets/audio/grammar")
            else:
                _pack_file(zf, audio_path, "assets/audio")

        for sent_path in state.get("sentence_audio_files", []):
            _pack_file(zf, sent_path, "assets/audio/sentences")

        # Chapter cover image
        _pack_file(zf, state.get("chapter_image_path", ""), "assets/images")

        # All other images (grammar notes + exercise images)
        for image_path in state.get("image_files", []):
            _pack_file(zf, image_path, "assets/images")

    logger.info("Output ZIP created: %s", output_zip)
    return {"output_zip_path": str(output_zip)}


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_grammar_note(note: GrammarNote) -> dict:
    """Serialise a GrammarNote, converting absolute imagePath/audioPath to ZIP-relative paths.
    Strips the internal image_prompt field (not needed in the descriptor).
    Includes grammar_table (Markdown string) if present.
    """
    d = note.model_dump(exclude={"image_prompt"})
    if d.get("imagePath"):
        d["imagePath"] = f"assets/images/{Path(d['imagePath']).name}"
    if d.get("audioPath"):
        d["audioPath"] = f"assets/audio/grammar/{Path(d['audioPath']).name}"
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

    return d


def _pack_file(zf: zipfile.ZipFile, file_path: str, arc_dir: str) -> None:
    """Add a file to the ZIP under arc_dir if it exists. Silently skips empty paths."""
    if not file_path:
        return
    p = Path(file_path)
    if p.exists():
        zf.write(p, arcname=f"{arc_dir}/{p.name}")
        logger.info("Packed: %s/%s", arc_dir, p.name)
    else:
        logger.warning("Asset file not found, skipping: %s", file_path)
