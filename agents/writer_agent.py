"""WriterAgent — assembles Markdown report and exports to PDF via MCP.

Bugs fixed:
  BUG A — command="python" hardcoded → sys.executable
  BUG B — relative MCP server path → absolute via pathlib
  BUG C (critical) — asyncio.run() called inside FastAPI's running event loop.
      FastAPI/uvicorn already runs an event loop.  asyncio.run() tries to
      create a SECOND loop in the same thread → RuntimeError which anyio wraps
      in ExceptionGroup → McpError: Connection closed → pdf_path = "".
      Fix: use asyncio.get_event_loop().run_until_complete() when a loop is
      already running, otherwise fall back to asyncio.run().  The cleanest
      cross-platform approach is the nest_asyncio pattern or running the
      coroutine in a fresh thread that has no event loop.
      We use the thread approach (no extra dependency, always works).
"""

import asyncio
import concurrent.futures
import json
import logging
import pathlib
import sys
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Absolute path to the MCP server — resolved once at import time.
_SERVER_PATH = str(
    pathlib.Path(__file__).parent.parent / "mcp_server" / "server.py"
)


WRITER_PROMPT = """
You are a technical report writer. Given research data and analysis,
write a well-structured research report in Markdown format.
Include: Executive Summary, Key Findings (with bullet points),
Data Analysis, Conclusions, and Sources.
"""


def _run_async_in_thread(coro):
    """Run an async coroutine in a brand-new thread with its own event loop.

    This is the safest way to call async MCP code from synchronous agent
    methods that are themselves running inside FastAPI's async event loop
    (via run_in_executor).  Creating a new thread guarantees there is no
    existing event loop, so asyncio.run() works without conflict.
    """
    result_holder = {}

    def thread_target():
        result_holder["value"] = asyncio.run(coro)

    t = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = t.submit(thread_target)
    future.result()  # blocks until done, propagates exceptions
    t.shutdown(wait=False)
    return result_holder.get("value", "")


class WriterAgent(BaseAgent):
    """Assembles a Markdown report and exports it to PDF via the MCP server."""

    def __init__(self):
        super().__init__("WriterAgent", WRITER_PROMPT)

    def run(self, state: dict) -> dict:
        context = json.dumps(
            {"data": state.get("raw_data"), "analysis": state.get("analysis")},
            ensure_ascii=False,
        )
        logger.info("WriterAgent: composing report …")

        report_md = self._call_llm(f"Query: {state['query']}\nContext: {context}")
        state["report"] = report_md

        try:
            # BUG C FIX: run in a fresh thread to avoid nested event loop error
            pdf_path = _run_async_in_thread(
                self._write_pdf_via_mcp(report_md, state["query"])
            )
        except Exception as exc:
            logger.error(f"PDF generation failed: {exc}", exc_info=True)
            pdf_path = ""

        state["pdf_path"] = pdf_path
        state["logs"].append(
            f"Writer: report generated, PDF saved to {pdf_path or '(none)'}"
        )
        logger.info(f"WriterAgent: PDF at {pdf_path!r}")
        return state

    async def _write_pdf_via_mcp(self, markdown: str, title: str) -> str:
        """Call the MCP write_pdf tool to convert Markdown to PDF."""
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
                    "write_pdf",
                    arguments={
                        "content": markdown,
                        "title": title,
                        "output_path": "reports/research_report.pdf",
                    },
                )
                print("MCP raw result:", repr(result), flush=True)
                if result.content and isinstance(result.content, list):
                    first = result.content[0]
                    print("First content item:", repr(first), flush=True)
                    return getattr(first, "text", str(first))
                return str(result.content)
