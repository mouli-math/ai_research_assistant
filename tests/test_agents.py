"""Unit tests for the agent layer.

All OpenAI API calls are mocked — no real network calls are made.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.orchestrator import ResearchState
from agents.planner_agent import PlannerAgent


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_state(query: str = "Test query about AI trends") -> ResearchState:
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


def _mock_openai_with(content: str):
    """Return a mock OpenAI client whose completions.create returns *content*."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = content
    return mock_client


# ── PlannerAgent tests ────────────────────────────────────────────────────────


@patch("agents.base_agent.OpenAI")
def test_planner_decomposes_query_json(mock_openai_cls):
    """PlannerAgent correctly parses a JSON array from the LLM."""
    mock_openai_cls.return_value = _mock_openai_with(
        json.dumps(["What is AI?", "How does ML work?", "AI applications in 2025"])
    )
    agent = PlannerAgent()
    state = make_state()
    result = agent.run(state)

    assert len(result["sub_tasks"]) == 3
    assert "What is AI?" in result["sub_tasks"]
    assert len(result["logs"]) == 1
    assert "3 sub-tasks" in result["logs"][0]


@patch("agents.base_agent.OpenAI")
def test_planner_handles_invalid_json_fallback(mock_openai_cls):
    """PlannerAgent falls back to newline splitting when JSON parse fails."""
    mock_openai_cls.return_value = _mock_openai_with(
        "1. Question one\n2. Question two\n3. Question three"
    )
    agent = PlannerAgent()
    result = agent.run(make_state())

    # Fallback must produce at least 1 sub-task
    assert len(result["sub_tasks"]) >= 1


@patch("agents.base_agent.OpenAI")
def test_planner_logs_event(mock_openai_cls):
    """PlannerAgent always appends exactly one log event."""
    mock_openai_cls.return_value = _mock_openai_with(
        json.dumps(["Q1", "Q2"])
    )
    agent = PlannerAgent()
    state = make_state()
    result = agent.run(state)
    assert len(result["logs"]) == 1


@patch("agents.base_agent.OpenAI")
def test_planner_preserves_existing_state_fields(mock_openai_cls):
    """PlannerAgent must not overwrite unrelated state fields."""
    mock_openai_cls.return_value = _mock_openai_with(json.dumps(["Q1"]))
    agent = PlannerAgent()
    state = make_state()
    state["raw_data"] = [{"task": "existing", "summary": "data"}]
    result = agent.run(state)

    assert result["raw_data"] == [{"task": "existing", "summary": "data"}]


# ── ResearchState tests ───────────────────────────────────────────────────────


def test_research_state_defaults():
    """ResearchState initialises with correct empty defaults."""
    state = make_state("hello")
    assert state["query"] == "hello"
    assert state["sub_tasks"] == []
    assert state["raw_data"] == []
    assert state["analysis"] is None
    assert state["report"] is None
    assert state["pdf_path"] is None
    assert state["error"] is None
    assert state["logs"] == []
