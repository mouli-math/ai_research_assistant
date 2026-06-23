"""LangGraph orchestrator for the Multi-Agent Research Assistant.

Wires PlannerAgent → ResearchAgent → AnalystAgent → WriterAgent into a
directed StateGraph. Includes Guardrails validation at entry and exit,
conditional early-exit on error, and MemorySaver checkpointing.
"""

import logging
from typing import List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.analyst_agent import AnalystAgent
from agents.planner_agent import PlannerAgent
from agents.research_agent import ResearchAgent
from agents.writer_agent import WriterAgent
from guardrails.input_guards import validate_input
from guardrails.output_guards import validate_output

logger = logging.getLogger(__name__)


# ── Shared state schema ─────────────────────────────────────────────────────


class ResearchState(TypedDict):
    """Typed state dictionary shared across all agent nodes.

    LangGraph requires a typed state schema to track partial updates
    and support checkpointing.
    """

    query: str                  # original user query
    sub_tasks: List[str]        # Planner output: focused sub-questions
    raw_data: List[dict]        # Researcher output: search result summaries
    analysis: Optional[str]     # Analyst output: stats + chart paths
    report: Optional[str]       # Writer output: full Markdown report
    pdf_path: Optional[str]     # Writer output: path to generated PDF
    error: Optional[str]        # Error message if any agent fails
    logs: List[str]             # Structured log events for SSE streaming


# ── Agent singletons (module-level, initialised once) ───────────────────────

_planner = PlannerAgent()
_researcher = ResearchAgent()
_analyst = AnalystAgent()
_writer = WriterAgent()


# ── Helper ──────────────────────────────────────────────────────────────────


def init_state(query: str) -> ResearchState:
    """Create a fresh ResearchState for a new research job.

    Args:
        query: The raw user research question.

    Returns:
        Initialised ResearchState with empty collections.
    """
    return ResearchState(
        query=query,
        sub_tasks=[],
        raw_data=[],
        analysis=None,
        report=None,
        pdf_path=None,
        error=None,
        logs=[],
    )


# ── Graph node functions ─────────────────────────────────────────────────────


def planner_node(state: ResearchState) -> ResearchState:
    """Validate input then run PlannerAgent."""
    try:
        state["query"] = validate_input(state["query"])
    except ValueError as exc:
        state["error"] = f"Input validation failed: {exc}"
        logger.error(state["error"])
        return state
    return _planner.run(state)


def researcher_node(state: ResearchState) -> ResearchState:
    """Run ResearchAgent."""
    try:
        return _researcher.run(state)
    except Exception as exc:
        state["error"] = f"ResearchAgent failed: {exc}"
        logger.error(state["error"])
        return state


def analyst_node(state: ResearchState) -> ResearchState:
    """Run AnalystAgent."""
    try:
        return _analyst.run(state)
    except Exception as exc:
        state["error"] = f"AnalystAgent failed: {exc}"
        logger.error(state["error"])
        return state


def writer_node(state: ResearchState) -> ResearchState:
    """Run WriterAgent then validate output."""
    try:
        state = _writer.run(state)
        if state.get("report"):
            state["report"] = validate_output(state["report"])
    except Exception as exc:
        state["error"] = f"WriterAgent/output validation failed: {exc}"
        logger.error(state["error"])
    return state


# ── Conditional router ───────────────────────────────────────────────────────


def should_continue(state: ResearchState) -> str:
    """Route to 'researcher' on success, or END immediately on error.

    This prevents wasted downstream API calls when an early agent fails.
    """
    return END if state.get("error") else "researcher"


# ── Build the StateGraph ─────────────────────────────────────────────────────

_graph = StateGraph(ResearchState)

_graph.add_node("planner", planner_node)
_graph.add_node("researcher", researcher_node)
_graph.add_node("analyst", analyst_node)
_graph.add_node("writer", writer_node)

_graph.set_entry_point("planner")

_graph.add_conditional_edges(
    "planner",
    should_continue,
    {"researcher": "researcher", END: END},
)
_graph.add_edge("researcher", "analyst")
_graph.add_edge("analyst", "writer")
_graph.add_edge("writer", END)

_memory = MemorySaver()
workflow = _graph.compile(checkpointer=_memory)


# ── Public API ────────────────────────────────────────────────────────────────


def run_research(query: str, thread_id: str = "default") -> ResearchState:
    """Execute the full multi-agent research pipeline synchronously.

    Args:
        query:     The user's research question.
        thread_id: LangGraph thread identifier for checkpointing.
                   Use a unique ID (e.g. job UUID) per request.

    Returns:
        Final ResearchState after all agents have run (or after error).
    """
    cfg = {"configurable": {"thread_id": thread_id}}
    logger.info(f"Starting research pipeline: thread_id={thread_id}, query={query!r}")
    result: ResearchState = workflow.invoke(init_state(query), config=cfg)
    logger.info(f"Research pipeline complete: thread_id={thread_id}")
    return result
