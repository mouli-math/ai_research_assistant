"""FastMCP server — exposes three tools to agents via stdio transport.

Tools:
  search_web  — Tavily web search
  run_code    — Sandboxed Python REPL
  write_pdf   — ReportLab PDF writer

Run directly:  python mcp_server/server.py
Agents connect via StdioServerParameters.
"""

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.code_run import execute_python
from mcp_server.tools.report import write_pdf_report
from mcp_server.tools.search import perform_search
import os
import uvicorn

# Instantiate the FastMCP server
mcp = FastMCP(
    "ResearchTools",
    host=os.environ.get("FASTMCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("FASTMCP_PORT", "8000")),
)


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> dict:
    """Search the web using Tavily API.

    Args:
        query:       The search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        Dict with keys 'query', 'answer', and 'results' (list of dicts
        with 'title', 'url', 'content').
    """
    return perform_search(query, max_results)


@mcp.tool()
def run_code(code: str) -> str:
    """Execute Python code in a sandboxed REPL.

    Dangerous imports (os, subprocess, socket, shutil, pathlib) are
    blocked. Stdout is captured and returned.

    Args:
        code: Python source code to execute.

    Returns:
        Captured stdout, or an error string prefixed with 'ERROR:' or
        'EXECUTION ERROR:'.
    """
    return execute_python(code)


@mcp.tool()
def write_pdf(content: str, title: str, output_path: str = "reports/report.pdf") -> str:
    """Convert Markdown content into a formatted PDF using ReportLab.

    Handles headings (# / ##), bullet points (- / *), and plain
    paragraphs. Creates the output directory if it does not exist.

    Args:
        content:     Markdown-formatted report text.
        title:       Document title rendered at the top of the PDF.
        output_path: File system path for the output PDF.

    Returns:
        The output_path where the PDF was written.
    """
    return write_pdf_report(content, title, output_path)




#if __name__ == "__main__":
 #   transport = os.environ.get("MCP_TRANSPORT", "stdio")
  #  if transport == "sse":
   #     # Docker / Cloud Run — agents connect via HTTP SSE on port 8001
    #    mcp.run(transport="sse")
    #else:
     #   # Local development — agents connect via subprocess stdio
      #  mcp.run(transport="stdio")

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)