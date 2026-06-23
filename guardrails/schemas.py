"""Pydantic schemas for structured LLM output validation."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SearchSummary(BaseModel):
    """Schema for a single research task summary from ResearchAgent."""

    question: str = Field(description="The research question answered")
    key_facts: List[str] = Field(description="List of key facts extracted from search results")
    sources: List[str] = Field(description="Source URLs used in this summary")


class ResearchOutput(BaseModel):
    """Schema for the final structured research report from WriterAgent.

    Used with Guard.from_pydantic() for strict output validation.
    """

    title: str = Field(description="Report title")
    executive_summary: str = Field(description="2-3 sentence high-level summary")
    key_findings: List[str] = Field(
        description="Bullet-point findings (minimum 3)",
        min_length=3,
    )
    data_analysis: Optional[str] = Field(
        default=None,
        description="Summary of statistical analysis and chart descriptions",
    )
    conclusion: str = Field(description="Concluding remarks and recommendations")
    sources: List[str] = Field(
        default_factory=list,
        description="List of source URLs referenced in the report",
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Model's confidence in the findings, 0.0–1.0",
    )
