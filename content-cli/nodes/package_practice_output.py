"""
Node: package_practice_output
Assembles the descriptor.json and all generated assets for a Practice Set into a .zip file.

The descriptor uses action "create_practice_set" so ingest scripts know to write to
the `practice_sets` collection and ArrayUnion the ID onto the parent chapter document.
"""

import json
import logging
import zipfile
from pathlib import Path

from models.content_models import ConversationExercise, ImageDescriptionExercise, MatchingExercise

logger = logging.getLogger(__name__)


def package_practice_output(state: dict) -> dict:
    """LangGraph node — build the practice-set .zip file."""
    work_dir = Path(state["work_dir"])
    practice_set_id = state["practice_set_id"]
    output_zip = work_dir.parent / f"{practice_set_id}.zip"

    descriptor = {
        "version": "1.0",
        "action": "create_practice_set",
        "bookId": state["book_id"],
        "chapterId": state["chapter_id"],
        "practiceSet": {
            "id": practice_set_id,
            "chapterId": state["chapter_id"],
            "title": f"Practice: {state.get('chapter_title', '')}",
            "coverImagePath": (
                f"assets/images/{Path(state['chapter_image_path']).name}" if state.get("chapter_image_path") else None
            ),
            "exercises": [_serialise_exercise(ex) for ex in state.get("exercises", [])],
        },
    }

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("descriptor.json", json.dumps(descriptor, ensure_ascii=False, indent=2))

        for audio_path in state.get("audio_files", []):
            name = Path(audio_path).name
            if "_conv_" in name:
                _pack_file(zf, audio_path, "assets/audio/conversation")
            else:
                _pack_file(zf, audio_path, "assets/audio")

        _pack_file(zf, state.get("chapter_image_path", ""), "assets/images")

        for image_path in state.get("image_files", []):
            _pack_file(zf, image_path, "assets/images")

        file_count = len(zf.namelist())

    logger.info("Practice output ZIP created: %s (%d files)", output_zip, file_count)
    return {"output_zip_path": str(output_zip)}


def _serialise_exercise(exercise) -> dict:
    if hasattr(exercise, "model_dump"):
        d = exercise.model_dump(exclude_none=False)
    else:
        d = dict(exercise)

    if isinstance(exercise, ImageDescriptionExercise) and d.get("imagePath"):
        d["imagePath"] = f"assets/images/{Path(d['imagePath']).name}"

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
    if not file_path:
        return
    p = Path(file_path)
    if p.exists():
        zf.write(p, arcname=f"{arc_dir}/{p.name}")
    else:
        logger.warning("Asset not found, skipping: %s", file_path)
