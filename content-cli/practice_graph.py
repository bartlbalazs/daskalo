"""
LangGraph pipeline for Practice Set generation.

Topology:
  START → generate_practice → generate_practice_media → package_practice_output → END
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nodes.generate_practice import generate_practice
from nodes.generate_practice_media import generate_practice_media
from nodes.package_practice_output import package_practice_output
from practice_state import PracticeState


def build_practice_graph() -> CompiledStateGraph:
    """Construct and compile the practice-set generation state machine."""
    builder = StateGraph(PracticeState)

    builder.add_node("generate_practice", generate_practice)
    builder.add_node("generate_practice_media", generate_practice_media)
    builder.add_node("package_practice_output", package_practice_output)

    builder.add_edge(START, "generate_practice")
    builder.add_edge("generate_practice", "generate_practice_media")
    builder.add_edge("generate_practice_media", "package_practice_output")
    builder.add_edge("package_practice_output", END)

    return builder.compile()
