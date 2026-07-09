"""
LangGraph pipeline definition for Daskalo content generation.
See docs/CONTENT_PIPELINE.md for the full node/edge description.

Topology:
  START → build_context → draft_lesson_core
          → extract_vocabulary         ┐  (fan-out, parallel)
          → extract_grammar_outlines   ┘
          → generate_grammar_notes  ┐  (fan-out, parallel)
          → generate_exercises      ┘
          → generate_grammar_summary   (after generate_grammar_notes + extract_vocabulary)
          → review_content             (after generate_grammar_summary + generate_exercises)
          → (conditional) → generate_media → package_output → END

Checkpointing (IMP-CC-01): the compiled graph is backed by a SQLite checkpointer
so a failure late in the pipeline (e.g. an exhausted LLM retry after several
expensive Gemini Pro calls) can be resumed from the last completed node instead
of discarding all prior work. See main.py for how `thread_id` is computed and
how a resume vs. a fresh run is chosen before invoking the graph.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nodes.build_context import build_context
from nodes.draft_lesson_core import draft_lesson_core
from nodes.extract_grammar_outlines import extract_grammar_outlines
from nodes.extract_vocabulary import extract_vocabulary
from nodes.generate_exercises import generate_exercises
from nodes.generate_grammar_notes import generate_grammar_notes
from nodes.generate_grammar_summary import generate_grammar_summary
from nodes.generate_media import generate_media
from nodes.package_output import package_output
from nodes.review_content import review_content, should_regenerate
from state import ContentState

# One SQLite checkpoint file per thread_id, so a checkpoint database never
# grows unbounded and each generation run's history is independently
# inspectable/removable. Re-running the exact same `daskalo generate` command
# recomputes the same thread_id (see main.py), so it always finds this file.
_CHECKPOINT_DIR = Path(__file__).parent / ".checkpoints"


def build_graph(thread_id: str = "default") -> CompiledStateGraph:
    """Construct and compile the content generation state machine.

    `thread_id` selects the SQLite checkpoint database at
    `.checkpoints/{thread_id}.sqlite`. Callers that don't care about
    resumability (e.g. a smoke-test import) can omit it and get the
    "default" checkpoint file.
    """
    builder = StateGraph(ContentState)

    # --- Nodes ---
    builder.add_node("build_context", build_context)
    builder.add_node("draft_lesson_core", draft_lesson_core)
    builder.add_node("extract_vocabulary", extract_vocabulary)
    builder.add_node("extract_grammar_outlines", extract_grammar_outlines)
    builder.add_node("generate_grammar_notes", generate_grammar_notes)
    builder.add_node("generate_exercises", generate_exercises)
    builder.add_node("generate_grammar_summary", generate_grammar_summary)
    builder.add_node("review_content", review_content)
    builder.add_node("generate_media", generate_media)
    builder.add_node("package_output", package_output)

    # --- Linear edges ---
    builder.add_edge(START, "build_context")
    builder.add_edge("build_context", "draft_lesson_core")

    # Fan-out: after draft_lesson_core, run vocab extraction and grammar outline extraction in parallel
    builder.add_edge("draft_lesson_core", "extract_vocabulary")
    builder.add_edge("draft_lesson_core", "extract_grammar_outlines")

    # Fan-in barrier: both extraction nodes must finish before grammar notes / exercises start.
    # Fan-out again: grammar notes and exercises generation run in parallel.
    builder.add_edge("extract_vocabulary", "generate_exercises")
    builder.add_edge("extract_grammar_outlines", "generate_exercises")
    builder.add_edge("extract_grammar_outlines", "generate_grammar_notes")
    # extract_vocabulary also gates generate_grammar_notes (needs vocab in state for context)
    builder.add_edge("extract_vocabulary", "generate_grammar_notes")

    # generate_grammar_summary runs after generate_grammar_notes (needs expanded notes)
    # and after extract_vocabulary (needs vocab). This is a second fan-in on those two.
    builder.add_edge("generate_grammar_notes", "generate_grammar_summary")
    builder.add_edge("extract_vocabulary", "generate_grammar_summary")

    # Fan-in barrier: both generate_grammar_summary and generate_exercises must finish
    # before review_content runs.
    builder.add_edge("generate_grammar_summary", "review_content")
    builder.add_edge("generate_exercises", "review_content")

    # Conditional edge: retry generation or proceed to media
    builder.add_conditional_edges(
        "review_content",
        should_regenerate,
        {
            "regenerate": "draft_lesson_core",  # Route back to draft_lesson_core on rejection
            "generate_media": "generate_media",
        },
    )

    builder.add_edge("generate_media", "package_output")
    builder.add_edge("package_output", END)

    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    db_path = _CHECKPOINT_DIR / f"{thread_id}.sqlite"
    # A plain sqlite3.Connection (rather than the `SqliteSaver.from_conn_string`
    # context manager) is used deliberately: this CLI is a short-lived process
    # that invokes the graph once and exits, so there's no `with`-block to hold
    # open around the invoke() call — the connection is simply reclaimed at
    # process exit. `check_same_thread=False` is safe here because SqliteSaver
    # guards all access with an internal `threading.Lock()`.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return builder.compile(checkpointer=checkpointer)
