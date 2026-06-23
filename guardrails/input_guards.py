"""Input validation guards applied before the Planner agent runs."""

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that indicate a prompt injection attempt
_INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"you are now",
    r"disregard all prior",
    r"act as if you have no restrictions",
    r"forget everything above",
    r"new persona",
    r"system prompt",
    r"reveal your instructions",
]

_MIN_LENGTH = 5
_MAX_LENGTH = 2000


def validate_input(query: str) -> str:
    """Validate and sanitise user input before passing it to agents.

    Checks performed (in order):
    1. Minimum length (5 characters).
    2. Maximum length (2 000 characters).
    3. Prompt-injection pattern detection.

    Args:
        query: Raw user input string.

    Returns:
        Stripped, validated query string.

    Raises:
        ValueError: If any validation check fails.
    """
    stripped = query.strip()

    # 1. Length checks
    if len(stripped) < _MIN_LENGTH:
        raise ValueError(
            f"Query too short — minimum {_MIN_LENGTH} characters required."
        )
    if len(stripped) > _MAX_LENGTH:
        raise ValueError(
            f"Query too long — maximum {_MAX_LENGTH} characters allowed "
            f"(received {len(stripped)})."
        )

    # 2. Prompt injection detection
    lower_q = stripped.lower()
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, lower_q):
            logger.warning(f"Potential prompt injection detected: {pattern!r}")
            raise ValueError(
                f"Input rejected: potential prompt injection detected ({pattern!r})."
            )

    logger.info(f"Input validation passed for query of length {len(stripped)}")
    return stripped
