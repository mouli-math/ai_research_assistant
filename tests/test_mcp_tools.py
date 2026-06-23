"""Unit tests for MCP tool implementations.

The Tavily client is mocked so no real API calls are made.
The PDF writer creates a temporary file and verifies output.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from mcp_server.tools.code_run import execute_python
from mcp_server.tools.report import write_pdf_report


# ── code_run tests ────────────────────────────────────────────────────────────


def test_code_execution_basic_print():
    output = execute_python("print('hello world')")
    assert "hello world" in output


def test_code_execution_math():
    output = execute_python("x = 2 + 2\nprint(x)")
    assert "4" in output


def test_code_execution_no_output():
    output = execute_python("x = 42")
    assert "no output" in output.lower()


def test_code_execution_blocks_os_import():
    result = execute_python("import os\nprint(os.getcwd())")
    assert "ERROR" in result
    assert "os" in result


def test_code_execution_blocks_subprocess():
    result = execute_python("import subprocess\nsubprocess.run(['ls'])")
    assert "ERROR" in result


def test_code_execution_blocks_socket():
    result = execute_python("import socket")
    assert "ERROR" in result


def test_code_execution_syntax_error():
    result = execute_python("def broken(:\n    pass")
    assert "EXECUTION ERROR" in result or "ERROR" in result


def test_code_execution_runtime_error():
    result = execute_python("x = 1 / 0")
    assert "EXECUTION ERROR" in result


# ── report / PDF writer tests ─────────────────────────────────────────────────


def test_write_pdf_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "test.pdf")
        result = write_pdf_report(
            content="# Report\n## Section\nSome content here.",
            title="Test Report",
            output_path=out,
        )
        assert result == out
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 0


def test_write_pdf_creates_parent_dirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "nested", "deep", "report.pdf")
        write_pdf_report("# Hello\nWorld", "Title", out)
        assert os.path.isfile(out)


def test_write_pdf_handles_bullets():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "bullet.pdf")
        write_pdf_report(
            "# Title\n- bullet one\n* bullet two\nPlain paragraph.",
            "Bullet Test",
            out,
        )
        assert os.path.isfile(out)


# ── Tavily search tests ───────────────────────────────────────────────────────


@patch("mcp_server.tools.search._client")
def test_search_returns_structured_result(mock_client):
    mock_client.search.return_value = {
        "answer": "AI stands for Artificial Intelligence",
        "results": [
            {"title": "AI Overview", "url": "https://example.com", "content": "A" * 600}
        ],
    }
    from mcp_server.tools.search import perform_search

    result = perform_search("What is AI?", max_results=1)
    assert result["query"] == "What is AI?"
    assert result["answer"] == "AI stands for Artificial Intelligence"
    assert len(result["results"]) == 1
    # Content should be truncated to 500 chars
    assert len(result["results"][0]["content"]) <= 500


@patch("mcp_server.tools.search._client")
def test_search_handles_api_error(mock_client):
    mock_client.search.side_effect = Exception("API rate limit exceeded")
    from mcp_server.tools.search import perform_search

    result = perform_search("broken query")
    assert "error" in result
    assert result["results"] == []
