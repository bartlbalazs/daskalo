"""
curriculum_loader.py — shared utility for loading the split curriculum.

Instead of a single monolithic curriculum.yaml, the curriculum is stored as
individual per-book YAML files under shared/data/books/book_N.yaml.

This loader globs all book files, loads them in order, and returns the same
dict structure that the old monolithic file provided:

    {
        "books": [
            {"id": "book_1", "title": "...", "order": 1, "chapters": [...]},
            ...
        ]
    }

Usage:
    from pathlib import Path
    from shared.data.curriculum_loader import load_curriculum

    data = load_curriculum(Path(__file__).parent.parent.parent)  # pass repo root
    for book in data["books"]:
        ...
"""

from __future__ import annotations

from pathlib import Path

import yaml


def load_curriculum(repo_root: Path | str) -> dict:
    """Load all per-book YAML files and return a unified curriculum dict.

    Args:
        repo_root: Absolute path to the repository root (the directory that
                   contains the ``shared/`` folder).

    Returns:
        A dict with a single key ``"books"`` whose value is a list of book
        dicts sorted by their ``order`` field, each containing a ``chapters``
        list.
    """
    books_dir = Path(repo_root) / "shared" / "data" / "books"
    book_files = sorted(books_dir.glob("book_*.yaml"))

    if not book_files:
        raise FileNotFoundError(
            f"No per-book YAML files found in {books_dir}. "
            "Expected files named book_1.yaml, book_2.yaml, etc."
        )

    books = []
    for path in book_files:
        with open(path, encoding="utf-8") as f:
            book = yaml.safe_load(f)
        books.append(book)

    # Sort by the `order` field so insertion order of glob matches canonical order.
    books.sort(key=lambda b: b.get("order", 0))

    return {"books": books}


def find_chapter(
    repo_root: Path | str, chapter_id: str
) -> tuple[dict, dict] | tuple[None, None]:
    """Find a (book, chapter) pair by chapter ID.

    Returns:
        ``(book_dict, chapter_dict)`` if found, ``(None, None)`` otherwise.
    """
    data = load_curriculum(repo_root)
    for book in data["books"]:
        for ch in book.get("chapters", []):
            if ch["id"] == chapter_id:
                return book, ch
    return None, None


def get_previous_chapters_vocabulary(
    repo_root: Path | str, chapter_id: str, lookback: int = 5
) -> list[str]:
    """Return mandatory vocabulary from the previous ``lookback`` chapters.

    Flattens all chapters across all books in canonical order (book order,
    then chapter order within each book), finds the current chapter, and
    returns the mandatory_vocabulary items from the preceding chapters.

    Args:
        repo_root: Absolute path to the repository root.
        chapter_id: The curriculum chapter ID of the *current* chapter (e.g. "b1_c3").
        lookback: How many preceding chapters to include (default 5).

    Returns:
        A flat list of vocabulary strings (e.g. ["είμαι (I am)", "εσύ (you)", ...]).
        Returns an empty list if the chapter is the very first one.
    """
    data = load_curriculum(repo_root)

    # Flatten all chapters in canonical order
    all_chapters: list[dict] = []
    for book in sorted(data["books"], key=lambda b: b.get("order", 0)):
        for ch in book.get("chapters", []):
            all_chapters.append(ch)

    # Find the index of the current chapter
    current_idx = next(
        (i for i, ch in enumerate(all_chapters) if ch["id"] == chapter_id), None
    )
    if current_idx is None:
        return []

    # Collect mandatory_vocabulary from the previous `lookback` chapters
    start_idx = max(0, current_idx - lookback)
    previous_vocab: list[str] = []
    for ch in all_chapters[start_idx:current_idx]:
        previous_vocab.extend(ch.get("mandatory_vocabulary", []))

    return previous_vocab
