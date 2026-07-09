"""
LangGraph pipeline for Practice Set generation.

Topology:
  START → generate_practice → generate_practice_media → package_practice_output → END

Checkpointing (IMP-CC-01): uses the same SQLite-checkpointer mechanism as the
main content graph (see graph.py) so a failure partway through can be resumed
from the last completed node on the next identical `daskalo generate-practice`
invocation.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nodes.generate_practice import generate_practice
from nodes.generate_practice_media import generate_practice_media
from nodes.package_practice_output import package_practice_output
from practice_state import PracticeState

# Shared with graph.py's checkpoint directory; files are namespaced by thread_id
# so chapter-generation and practice-generation runs never collide.
_CHECKPOINT_DIR = Path(__file__).parent / ".checkpoints"


def build_practice_graph(thread_id: str = "default") -> CompiledStateGraph:
    """Construct and compile the practice-set generation state machine.

    `thread_id` selects the SQLite checkpoint database at
    `.checkpoints/{thread_id}.sqlite` (see graph.py's build_graph for the
    rationale behind using a plain sqlite3.Connection here).
    """
    builder = StateGraph(PracticeState)

    builder.add_node("generate_practice", generate_practice)
    builder.add_node("generate_practice_media", generate_practice_media)
    builder.add_node("package_practice_output", package_practice_output)

    builder.add_edge(START, "generate_practice")
    builder.add_edge("generate_practice", "generate_practice_media")
    builder.add_edge("generate_practice_media", "package_practice_output")
    builder.add_edge("package_practice_output", END)

    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    db_path = _CHECKPOINT_DIR / f"{thread_id}.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return builder.compile(checkpointer=checkpointer)
