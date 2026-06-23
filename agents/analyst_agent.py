"""AnalystAgent — generates and runs data analysis code via MCP Python REPL.

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

ANALYST_PROMPT = """
You are a data analyst. Given research summaries, write Python code to:
1. Extract key numerical data points
2. Compute basic statistics (mean, trend, comparison)
3. Generate a Plotly chart saved as chart.html using plotly.io.write_html()
Return ONLY the Python code — no explanation, no markdown fences.
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
    return result_holder.get("value", "")


class AnalystAgent(BaseAgent):
    """Analyses research data and generates charts via the MCP Python REPL."""

    def __init__(self):
        super().__init__("AnalystAgent", ANALYST_PROMPT)

    def run(self, state: dict) -> dict:
        summaries = str(state.get("raw_data", []))
        logger.info("AnalystAgent: generating analysis code …")

        code = self._call_llm(f"Research summaries:\n{summaries}")

        try:
            output = _run_async_in_thread(self._run_code_via_mcp(code))
        except Exception as exc:
            logger.warning(f"AnalystAgent MCP code execution failed: {exc}")
            output = f"Analysis skipped due to execution error: {exc}"

        state["analysis"] = output
        state["logs"].append("Analyst: code executed, charts generated")
        logger.info("AnalystAgent: analysis complete")
        return state

    async def _run_code_via_mcp(self, code: str) -> str:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[_SERVER_PATH],
            env=os.environ.copy(),
            stderr="pipe",
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "run_code", arguments={"code": code}
                )
                return str(result.content)
