"""ResearchAgent — performs web research for each planner sub-task via MCP.

Bugs fixed:
  BUG A — command="python" → sys.executable
  BUG B — relative MCP path → absolute via pathlib
  BUG C — asyncio.run() inside running event loop → thread-based runner
"""

import asyncio
import concurrent.futures
import logging
import pathlib
import sys
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_SERVER_PATH = str(
    pathlib.Path(__file__).parent.parent / "mcp_server" / "server.py"
)

RESEARCH_PROMPT = """
You are a research specialist. For each search result provided, extract
the key facts, statistics, and insights relevant to the question.
Return a concise JSON summary with keys: question, key_facts, sources.
"""


def _run_async_in_thread(coro):
    """Run coroutine in a fresh thread with its own event loop (BUG C fix)."""
    result_holder = {}

    def thread_target():
        result_holder["value"] = asyncio.run(coro)

    t = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = t.submit(thread_target)
    future.result()
    t.shutdown(wait=False)
    return result_holder.get("value", "{}")


class ResearchAgent(BaseAgent):
    """Performs web research for each planner sub-task via the MCP server."""

    def __init__(self):
        super().__init__("ResearchAgent", RESEARCH_PROMPT)

    def run(self, state: dict) -> dict:
        raw_data: list[dict] = []

        for task in state.get("sub_tasks", []):
            logger.info(f"ResearchAgent searching: {task}")
            try:
                results = _run_async_in_thread(self._search_via_mcp(task))
            except Exception as exc:
                logger.warning(f"MCP search failed for '{task}': {exc}. Using empty results.")
                results = "{}"

            summary = self._call_llm(f"Question: {task}\nResults: {results}")
            raw_data.append({"task": task, "summary": summary})

        state["raw_data"] = raw_data
        state["logs"].append(f"Researcher: collected data for {len(raw_data)} tasks")
        logger.info(f"ResearchAgent: finished {len(raw_data)} tasks")
        return state

    async def _search_via_mcp(self, query: str) -> str:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[_SERVER_PATH],
            env=os.environ.copy(),    # ← explicitly inherit full parent environment
            stderr="pipe",
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "search_web", arguments={"query": query, "max_results": 5}
                )
                return str(result.content)
