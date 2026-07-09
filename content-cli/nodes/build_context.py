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
    target_grammar field (lines matching ^\\d+\\.\\s) and collapses them into
    a bulleted list — drops the verbose sub-examples to keep it terse.
  - Vocabulary: collects all mandatory_vocabulary entries from prior chapters
    into a flat deduplicated list (preserving first-seen order).
  - CEFR level: reads the book's `level` field (e.g. "B2") and exposes it
    as `cefr_level` in state.

The lookup/accumulation logic below is factored into plain, pure functions
(`_find_target_and_prior_chapters`, `_accumulate_grammar_headlines`,
`_accumulate_vocabulary`) that take a plain curriculum dict and return plain
data — no I/O, no LangGraph state. `build_context` itself stays a thin node
that loads the curriculum and delegates to them (see AGENTS.md: "keep node
functions pure and focused"). This also makes the accumulation logic directly
unit-testable against a small fixture curriculum without touching the
filesystem (see tests/test_build_context.py).
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


def _find_target_and_prior_chapters(curriculum: dict, chapter_id: str) -> tuple[dict, dict, list[dict]]:
    """Pure function — locate the target book/chapter and every chapter that precedes it.

    "Precedes" means canonical order: book order, then chapter order within each book.
    Everything collected before the target chapter is is returned as `prior_chapters`.

    Raises:
        ValueError: if `chapter_id` is not found in any book.
    """
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

    return target_book, target_chapter, prior_chapters


def _accumulate_grammar_headlines(prior_chapters: list[dict]) -> str:
    """Pure function — collapse prior chapters' numbered target_grammar headlines.

    Extracts lines matching ``^\\d+\\.\\s`` from each prior chapter's `target_grammar`
    field, strips the leading number, deduplicates (first-seen order), and renders
    as a Markdown bullet list. Returns the literal string "None" if there is no
    prior knowledge at all (e.g. the very first chapter).
    """
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

    return "\n".join(grammar_headlines) if grammar_headlines else "None"


def _accumulate_vocabulary(prior_chapters: list[dict]) -> list[str]:
    """Pure function — flat, deduplicated, order-preserved mandatory_vocabulary
    collected across every prior chapter.
    """
    seen_vocab: set[str] = set()
    accumulated_vocab: list[str] = []

    for ch in prior_chapters:
        for word in ch.get("mandatory_vocabulary", []):
            word_str = str(word).strip()
            if word_str and word_str not in seen_vocab:
                seen_vocab.add(word_str)
                accumulated_vocab.append(word_str)

    return accumulated_vocab


def build_context(state: ContentState) -> dict:
    """LangGraph node — loads the curriculum and computes dynamic pedagogical constraints."""
    chapter_id = state["curriculum_chapter_id"]
    logger.info("Building pedagogical context for chapter %s", chapter_id)

    root_dir = Path(__file__).parent.parent.parent
    curriculum = load_curriculum(root_dir)

    target_book, target_chapter, prior_chapters = _find_target_and_prior_chapters(curriculum, chapter_id)

    accumulated_grammar = _accumulate_grammar_headlines(prior_chapters)
    accumulated_vocab = _accumulate_vocabulary(prior_chapters)
    cefr_level: str = target_book.get("level", "A1") if target_book else "A1"

    logger.info(
        "Context built: cefr=%s, prior_grammar_headlines=%d, prior_vocab=%d",
        cefr_level,
        0 if accumulated_grammar == "None" else len(accumulated_grammar.splitlines()),
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
