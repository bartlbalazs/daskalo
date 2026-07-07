"""
Shared pytest fixtures for Daskalo content-cli tests.

Mirrors the mocking style of backend/tests/conftest.py (small factory helpers,
no heavyweight fixture frameworks), adapted to content-cli's actual
dependencies. Every test in this suite mocks/stubs LLM (LangChain structured
models), TTS (google-cloud-texttospeech), image (google-genai), and GCS
(google-cloud-storage) clients — none of these tests make real network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure both content-cli/ and the repo root are importable the same way every
# content-cli module already arranges for itself at import time (see e.g.
# nodes/build_context.py's sys.path handling) — done explicitly here too so
# tests don't depend on import order.
_CONTENT_CLI_DIR = Path(__file__).parent.parent
_REPO_ROOT = _CONTENT_CLI_DIR.parent
for _path in (_CONTENT_CLI_DIR, _REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


# ---------------------------------------------------------------------------
# Fixture curriculum (nodes/build_context.py tests)
# ---------------------------------------------------------------------------


def make_chapter(
    chapter_id: str,
    order: int,
    target_grammar: str = "",
    mandatory_vocabulary: list[str] | None = None,
) -> dict:
    """Build a minimal curriculum chapter dict, shaped like a parsed book_N.yaml entry."""
    return {
        "id": chapter_id,
        "order": order,
        "suggested_length": "short",
        "language_skill": f"Skill for {chapter_id}",
        "target_grammar": target_grammar,
        "mandatory_vocabulary": mandatory_vocabulary or [],
    }


def make_book(book_id: str, order: int, level: str, chapters: list[dict]) -> dict:
    """Build a minimal curriculum book dict, shaped like a parsed book_N.yaml file."""
    return {
        "id": book_id,
        "title": f"Book {order}",
        "description": "",
        "order": order,
        "level": level,
        "chapters": chapters,
    }


@pytest.fixture
def fixture_curriculum() -> dict:
    """A small, 2-book curriculum with known grammar/vocabulary overlaps, used to
    test build_context.py's prior-knowledge accumulation logic without touching
    the real shared/data/books/*.yaml files.
    """
    book_1 = make_book(
        "book_1",
        order=1,
        level="A1.1",
        chapters=[
            make_chapter(
                "b1_c1",
                order=1,
                target_grammar="1. The verb to be.\n2. Personal pronouns.\n",
                mandatory_vocabulary=["είμαι (I am)", "εσύ (you)"],
            ),
            make_chapter(
                "b1_c2",
                order=2,
                # Deliberately repeats "The verb to be." (different numbering) and
                # "είμαι (I am)" to exercise deduplication.
                target_grammar="1. Definite articles.\n2. The verb to be.\n",
                mandatory_vocabulary=["ο (the)", "είμαι (I am)"],
            ),
        ],
    )
    book_2 = make_book(
        "book_2",
        order=2,
        level="A2.1",
        chapters=[
            make_chapter(
                "b2_c1",
                order=1,
                target_grammar="1. Past tense.\n",
                mandatory_vocabulary=["χθες (yesterday)"],
            ),
        ],
    )
    return {"books": [book_1, book_2]}


# ---------------------------------------------------------------------------
# Mocked GCS bucket (services/ingest_helpers.py tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_bucket() -> MagicMock:
    """A GCS Bucket stand-in: .blob(path) returns a fresh (memoised) MagicMock
    blob per path, and .upload_from_string() is tracked without touching the
    network. `bucket.name` is a plain string, matching the real Bucket API,
    since `_upload_asset` builds the returned gs:// URI from it.
    """
    bucket = MagicMock()
    bucket.name = "test-assets-bucket"

    blobs: dict[str, MagicMock] = {}

    def _blob(path: str) -> MagicMock:
        blob = blobs.setdefault(path, MagicMock())
        blob.name = path
        return blob

    bucket.blob.side_effect = _blob
    bucket._blobs = blobs  # exposed for assertions
    return bucket
