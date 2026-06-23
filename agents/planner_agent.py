import json
import logging

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """
You are a research planning expert. Given a user's research query,
decompose it into 3-5 specific, focused sub-questions that together
cover the topic comprehensively. Return ONLY a JSON array of strings.
Example: ["What is X?", "How does Y work?", "Compare X vs Z"]
"""


class PlannerAgent(BaseAgent):
    """Decomposes a high-level research query into focused sub-tasks.

    Output:
        state['sub_tasks']: List[str] — 3-5 research sub-questions.
    """

    def __init__(self):
        super().__init__("PlannerAgent", PLANNER_PROMPT)

    def run(self, state: dict) -> dict:
        """Decompose query into sub-tasks and store in state.

        Args:
            state: Shared ResearchState; must contain 'query'.

        Returns:
            Updated state with 'sub_tasks' populated.
        """
        query = state["query"]
        logger.info(f"PlannerAgent processing: {query}")

        raw = self._call_llm(f"Research query: {query}")

        # Primary parse: expect a JSON array
        try:
            sub_tasks: list[str] = json.loads(raw)
            if not isinstance(sub_tasks, list):
                raise ValueError("Expected a JSON array")
        except (json.JSONDecodeError, ValueError):
            # Fallback: split by newline and strip numbering/bullets
            logger.warning("PlannerAgent: JSON parse failed, falling back to newline split.")
            sub_tasks = [
                line.lstrip("0123456789.-) ").strip()
                for line in raw.split("\n")
                if line.strip()
            ]

        state["sub_tasks"] = sub_tasks
        state["logs"].append(f"Planner: created {len(sub_tasks)} sub-tasks")
        logger.info(f"PlannerAgent: {len(sub_tasks)} sub-tasks created")
        return state
