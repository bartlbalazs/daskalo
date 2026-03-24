"""
Node: build_context

Loads the curriculum chapter from the per-book YAML files and computes
prior knowledge dynamically at runtime rather than relying on the
pre-baked (and error-prone) accumulated_grammar_summary / accumulated_vocabulary
fields stored in each YAML chapter entry.

Dynamic computation:
  - Iterates all books/chapters that come *before* the current chapter
    (ordered by book.order, then chapter.order).
  - Grammar: extracts the numbered-list headlines from each prior chapter's
    target_grammar field (lines matching ^\d+\.\s) and collapses them into
    a bulleted list — drops the verbose sub-examples to keep it terse.
  - Vocabulary: collects all mandatory_vocabulary entries from prior chapters
    into a flat deduplicated list (preserving first-seen order).
  - CEFR level: reads the book's `level` field (e.g. "B2") and exposes it
    as `cefr_level` in state.
"""

import logging
import re
import sys
from pathlib import Path

from state import ContentState

# Ensure the shared package is importable regardless of working directory.
_repo_root = Path(__file__).parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.data.curriculum_loader import load_curriculum  # noqa: E402

logger = logging.getLogger(__name__)


def build_context(state: ContentState) -> dict:
    """LangGraph node — loads the curriculum and computes dynamic pedagogical constraints."""
    chapter_id = state["curriculum_chapter_id"]
    logger.info("Building pedagogical context for chapter %s", chapter_id)

    root_dir = Path(__file__).parent.parent.parent
    curriculum = load_curriculum(root_dir)

    # ------------------------------------------------------------------ #
    # Locate the current chapter and all prior chapters                   #
    # ------------------------------------------------------------------ #
    target_book: dict | None = None
    target_chapter: dict | None = None

    prior_chapters: list[dict] = []

    for book in curriculum["books"]:
        for ch in book.get("chapters", []):
            if ch["id"] == chapter_id:
                target_book = book
                target_chapter = ch
                # Stop — everything collected so far is prior knowledge.
                break
            prior_chapters.append(ch)
        if target_chapter is not None:
            break

    if target_chapter is None:
        raise ValueError(f"Chapter ID {chapter_id} not found in curriculum books")

    # ------------------------------------------------------------------ #
    # Compute accumulated grammar (headline lines only)                   #
    # ------------------------------------------------------------------ #
    grammar_headlines: list[str] = []
    seen_headlines: set[str] = set()

    for ch in prior_chapters:
        for line in ch.get("target_grammar", "").splitlines():
            if re.match(r"^\d+\.\s", line):
                # Strip the leading number so duplicates from different
                # chapters collapse correctly (e.g. "1. X" vs "2. X").
                clean = re.sub(r"^\d+\.\s+", "", line).strip()
                if clean and clean not in seen_headlines:
                    seen_headlines.add(clean)
                    grammar_headlines.append(f"- {clean}")

    accumulated_grammar = "\n".join(grammar_headlines) if grammar_headlines else "None"

    # ------------------------------------------------------------------ #
    # Compute accumulated vocabulary (deduplicated, order-preserved)      #
    # ------------------------------------------------------------------ #
    seen_vocab: set[str] = set()
    accumulated_vocab: list[str] = []

    for ch in prior_chapters:
        for word in ch.get("mandatory_vocabulary", []):
            word_str = str(word).strip()
            if word_str and word_str not in seen_vocab:
                seen_vocab.add(word_str)
                accumulated_vocab.append(word_str)

    # ------------------------------------------------------------------ #
    # CEFR level from the current book                                    #
    # ------------------------------------------------------------------ #
    cefr_level: str = target_book.get("level", "A1") if target_book else "A1"

    logger.info(
        "Context built: cefr=%s, prior_grammar_headlines=%d, prior_vocab=%d",
        cefr_level,
        len(grammar_headlines),
        len(accumulated_vocab),
    )

    return {
        "target_grammar": target_chapter["target_grammar"],
        "language_skill": target_chapter.get("language_skill", ""),
        "mandatory_vocabulary": target_chapter["mandatory_vocabulary"],
        "accumulated_grammar": accumulated_grammar,
        "accumulated_vocabulary": accumulated_vocab,
        "cefr_level": cefr_level,
    }
