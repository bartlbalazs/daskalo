#!/usr/bin/env python3
"""
generate_brief.py — helper script for the `lesson-author` opencode skill.

Read-only. Makes NO writes anywhere (no Firestore writes, no file writes).
Run with `uv run --project content-cli python <this file> [chapter_id]`
so it executes inside content-cli's own virtualenv (needs pyyaml,
python-dotenv, and google-cloud-firestore, all already content-cli deps).

Two modes, selected by argument count:

  (no args)     -> preconditions + the full book/chapter listing, for when
                   the operator hasn't picked a chapter yet.
  <chapter_id>  -> preconditions + a curriculum-aware brief for that specific
                   chapter (CEFR level, target grammar, mandatory vocabulary,
                   accumulated prior-chapter knowledge, length options, and a
                   best-effort "has this already been generated?" signal).

The brief is computed by calling content-cli's own `build_context` node
function directly (not a reimplementation) — this guarantees it can never
drift from what `daskalo generate` will actually compute for that chapter at
generation time.

Output: exactly one JSON object on stdout. On error, a message on stderr and
a non-zero exit code.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

# This file lives at <repo_root>/.opencode/skills/lesson-author/scripts/generate_brief.py
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]
_CONTENT_CLI_DIR = _REPO_ROOT / "content-cli"

for _p in (str(_REPO_ROOT), str(_CONTENT_CLI_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import dotenv_values  # noqa: E402

from shared.data.curriculum_loader import find_chapter, load_curriculum  # noqa: E402


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Best-effort TCP reachability check — never raises."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_preconditions() -> dict:
    """
    Checks needed before `daskalo generate --local` will actually work:
      - content-cli/.env exists and sets GOOGLE_CLOUD_PROJECT (required even
        in --local mode, per main.py's _check_env).
      - The Firestore/Storage emulators (dev.sh) are reachable, needed for
        local ingest at the end of the run — not needed for the
        brainstorming conversation itself, so this is informational, not
        blocking, this early.
    """
    env_path = _CONTENT_CLI_DIR / ".env"
    env_values = dotenv_values(env_path) if env_path.is_file() else {}
    return {
        "content_cli_env_exists": env_path.is_file(),
        "google_cloud_project_set": bool(env_values.get("GOOGLE_CLOUD_PROJECT")),
        "firestore_emulator_reachable": _port_open("localhost", 8081),
        "storage_emulator_reachable": _port_open("localhost", 9199),
    }


def _list_books() -> list[dict]:
    curriculum = load_curriculum(_REPO_ROOT)
    return [
        {
            "id": book["id"],
            "title": book["title"],
            "order": book["order"],
            "level": book.get("level"),
            "chapters": [
                {
                    "id": ch["id"],
                    "order": ch["order"],
                    "suggested_length": ch.get("suggested_length"),
                    "language_skill": ch.get("language_skill"),
                }
                for ch in book.get("chapters", [])
            ],
        }
        for book in curriculum["books"]
    ]


def _brief_for_chapter(chapter_id: str) -> dict:
    book, chapter = find_chapter(_REPO_ROOT, chapter_id)
    if chapter is None:
        raise SystemExit(f"Error: chapter ID '{chapter_id}' not found in any book under shared/data/books/.")

    # Calls the pipeline's own node function directly (not a reimplementation)
    # so this brief can never drift from what `daskalo generate` computes.
    from models.content_models import LESSON_CONFIG  # noqa: E402  (content-cli import)
    from nodes.build_context import build_context  # noqa: E402  (content-cli import)

    context = build_context({"curriculum_chapter_id": chapter_id})

    length_options = {
        str(length): {
            "passage_sentences": cfg["passage_sentences"],
            "vocab_count": cfg["vocab_count"],
            "grammar_concepts": cfg["grammar_concepts"],
            "exercise_count": cfg["exercise_count"],
            "available_types": cfg["available_types"],
        }
        for length, cfg in LESSON_CONFIG.items()
    }

    # Best-effort "already generated?" signal — informational only, never blocking
    # (multiple content variants per curriculum chapter are supported by the data model).
    output_dir = _CONTENT_CLI_DIR / "output"
    existing_zips = sorted(p.name for p in output_dir.glob(f"{chapter_id}_*.zip")) if output_dir.is_dir() else []

    existing_variant_ids: list[str] = []
    if _port_open("localhost", 8081):
        try:
            os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "localhost:8081")
            from google.cloud import firestore
            from google.cloud.firestore_v1 import FieldFilter

            fs_client = firestore.Client(project="demo-daskalo")
            query = fs_client.collection("chapters").where(filter=FieldFilter("curriculumChapterId", "==", chapter_id))
            existing_variant_ids = [doc.id for doc in query.stream()]
        except Exception:
            pass  # Emulator probe is informational only; never fail brief generation.

    return {
        "chapter_id": chapter_id,
        "book_id": book["id"],
        "book_title": book["title"],
        "book_order": book["order"],
        "chapter_order": chapter["order"],
        "suggested_length": chapter.get("suggested_length"),
        "cefr_level": context["cefr_level"],
        "language_skill": context["language_skill"],
        "target_grammar": context["target_grammar"],
        "mandatory_vocabulary": context["mandatory_vocabulary"],
        "accumulated_grammar": context["accumulated_grammar"],
        "accumulated_vocabulary": context["accumulated_vocabulary"],
        "length_options": length_options,
        "existing_local_zips": existing_zips,
        "existing_variant_ids_in_emulator": existing_variant_ids,
    }


def main() -> None:
    result: dict = {"preconditions": _check_preconditions()}

    if len(sys.argv) == 1:
        result["books"] = _list_books()
    elif len(sys.argv) == 2:
        result["brief"] = _brief_for_chapter(sys.argv[1])
    else:
        print("Usage: generate_brief.py [curriculum_chapter_id]", file=sys.stderr)
        sys.exit(2)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
