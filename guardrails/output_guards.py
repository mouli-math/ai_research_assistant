"""Output validation guards applied after the Writer agent runs."""

import logging
import re

from guardrails.schemas import ResearchOutput

logger = logging.getLogger(__name__)

# PII regex patterns — any match is redacted to [REDACTED]
_PII_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",                                       # US SSN
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",         # email
    r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",              # credit card
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",    # US phone
]

_MIN_REPORT_LENGTH = 50


def validate_output(report: str) -> str:
    """Validate and sanitise LLM-generated report output.

    Checks performed:
    1. Minimum length (50 characters).
    2. PII redaction (SSN, email, credit card, phone number).
    3. Structural check — at least one Markdown heading required.

    Args:
        report: Raw Markdown report string from WriterAgent.

    Returns:
        Sanitised report string.

    Raises:
        ValueError: If validation fails.
    """
    if not report or len(report.strip()) < _MIN_REPORT_LENGTH:
        raise ValueError(
            f"Report output too short or empty (minimum {_MIN_REPORT_LENGTH} chars)."
        )

    # Redact PII
    original_len = len(report)
    for pattern in _PII_PATTERNS:
        report = re.sub(pattern, "[REDACTED]", report)

    redacted = original_len - len(report.replace("[REDACTED]", ""))
    if redacted > 0:
        logger.warning(f"PII redacted from output ({redacted} chars replaced)")

    # Structural check — must contain at least one Markdown heading
    if not re.search(r"^#{1,3}\s", report, re.MULTILINE):
        raise ValueError(
            "Output lacks required report structure (no Markdown headings found)."
        )

    logger.info("Output validation passed")
    return report


def validate_with_schema(llm_output: str) -> ResearchOutput:
    """Parse and validate free-form LLM output against the ResearchOutput schema.

    Uses Pydantic for strict field validation. Intended for use when
    the LLM has been instructed to return structured JSON.

    Args:
        llm_output: JSON string from the LLM.

    Returns:
        Validated ResearchOutput instance.

    Raises:
        ValueError: If parsing or schema validation fails.
    """
    import json

    try:
        # Strip markdown fences if present
        clean = llm_output.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-z]*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)
        data = json.loads(clean)
        return ResearchOutput(**data)
    except Exception as exc:
        raise ValueError(f"Output schema validation failed: {exc}") from exc
