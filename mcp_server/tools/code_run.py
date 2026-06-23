"""Sandboxed Python REPL tool for the MCP server."""

import contextlib
import io
import logging
import traceback

logger = logging.getLogger(__name__)

# Modules blocked in the sandbox to prevent filesystem / network access
BLOCKED_MODULES = {"os", "subprocess", "socket", "shutil", "pathlib", "sys"}


def execute_python(code: str, timeout: int = 10) -> str:
    """Execute Python code safely and return stdout as a string.

    Security measures:
    - Blocks imports of dangerous standard-library modules.
    - Redirects stdout to capture output.
    - Isolates execution in a fresh local namespace.
    - Does NOT use a subprocess — not fully sandboxed for production;
      consider RestrictedPython or a Docker REPL for stronger isolation.

    Args:
        code:    The Python source code to execute.
        timeout: Reserved for future subprocess-based implementation;
                 not enforced in this in-process version.

    Returns:
        Captured stdout, or an error string on failure.
    """
    # 1. Blocked-import check
    for module in BLOCKED_MODULES:
        if f"import {module}" in code or f"from {module}" in code:
            logger.warning(f"Sandbox blocked import of '{module}'")
            return f"ERROR: import of '{module}' is not allowed in sandbox"

    # 2. Execute in isolated namespace with stdout capture
    stdout_capture = io.StringIO()
    local_ns: dict = {}

    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, {"__builtins__": __builtins__}, local_ns)  # noqa: S102

        output = stdout_capture.getvalue()
        logger.info("Code executed successfully")
        return output or "Code executed (no output)"

    except Exception:
        tb = traceback.format_exc()
        logger.warning(f"Code execution error:\n{tb}")
        return f"EXECUTION ERROR:\n{tb}"
