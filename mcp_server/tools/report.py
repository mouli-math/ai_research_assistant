"""ReportLab PDF writer tool for the MCP server.

Bugs fixed vs original:
  BUG 3 (crash) — ReportLab's Paragraph() is an XML/HTML parser internally.
      Any unclosed or malformed HTML-like tag in LLM output (e.g. "<b>text"
      without </b>, or stray angle brackets from code snippets) raises:
          ValueError: paragraph text '...' caused exception Parse error:
                      saw </para> instead of expected </b>
      This exception propagates up through the MCP tool → WriterAgent catches
      it → pdf_path="" → "PDF saved to (none)".
      Fix: html.escape() all text segments BEFORE passing to Paragraph().
      ReportLab still renders its own <b>/<i> tags correctly because we only
      escape the raw text content, not the style wrapper tags.

  BUG 4 (silent data loss) — ### and #### headings (levels 3 & 4) were not
      handled; they fell through to the Normal paragraph branch and rendered
      as plain text with the leading '#' characters visible.
      Fix: added elif branches for ### and ####.
"""

import html
import logging
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

logger = logging.getLogger(__name__)


def _safe_para(text: str, style) -> Paragraph:
    """Escape *text* for ReportLab's XML parser, then wrap in Paragraph.

    ReportLab treats Paragraph content as XML.  Raw LLM output often contains
    characters that are valid in prose but illegal in XML without escaping:
      - Unclosed tags:  <b>bold text  (no </b>)
      - Bare ampersands: GPT-4 & GPT-3.5
      - Angle brackets in non-tag context: score > 90%, version < 3.11

    html.escape() converts & → &amp;  < → &lt;  > → &gt;  which ReportLab
    then renders as the literal characters in the PDF — correct behaviour.
    """
    return Paragraph(html.escape(text), style)


def write_pdf_report(
    content: str,
    title: str,
    output_path: str = "reports/report.pdf",
) -> str:
    """Convert Markdown-like content into a formatted PDF using ReportLab.

    Supported Markdown elements:
        #### Heading 4  (new)
        ### Heading 3   (new)
        ## Heading 2
        # Heading 1
        - or * bullet points
        blank lines → vertical spacer
        all other lines → Normal paragraph

    Args:
        content:     Report text in Markdown-like format.
        title:       Document title displayed at the top.
        output_path: Destination file path for the PDF.

    Returns:
        The output_path string on success.

    Raises:
        Exception: Propagates ReportLab errors to the caller.
    """
    parent = os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if parent:
        os.makedirs(parent, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        # Title is also escaped — LLM query text can contain & or < characters
        _safe_para(title, styles["Title"]),
        Spacer(1, 0.5 * cm),
    ]

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 0.3 * cm))
        elif stripped.startswith("#### "):
            # BUG 4 FIX: level-4 headings now handled (rendered as Heading3)
            story.append(_safe_para(stripped[5:], styles["Heading3"]))
        elif stripped.startswith("### "):
            # BUG 4 FIX: level-3 headings now handled
            story.append(_safe_para(stripped[4:], styles["Heading3"]))
        elif stripped.startswith("## "):
            story.append(_safe_para(stripped[3:], styles["Heading2"]))
        elif stripped.startswith("# "):
            story.append(_safe_para(stripped[2:], styles["Heading1"]))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            story.append(_safe_para(f"\u2022 {stripped[2:]}", styles["Normal"]))
        else:
            # BUG 3 FIX: _safe_para escapes any XML-unsafe chars from LLM text
            story.append(_safe_para(stripped, styles["Normal"]))

    doc.build(story)
    logger.info(f"PDF written to {output_path}")
    return output_path
