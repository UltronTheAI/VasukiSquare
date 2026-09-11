"""Structured technical content component models for technical ebooks."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class CodeBlock(BaseModel):
    """Structured code snippet block with syntax highlighting metadata."""

    type: Literal["code"] = "code"
    language: str = Field(default="python", description="Programming language identifier")
    filename: Optional[str] = Field(default=None, description="Source file name or path")
    code: str = Field(description="Raw source code content")
    caption: Optional[str] = Field(default=None, description="Descriptive caption or explanation")
    line_numbers: bool = Field(default=False, description="Whether to display line numbers")


class TerminalBlock(BaseModel):
    """Dedicated terminal/console window block."""

    type: Literal["terminal"] = "terminal"
    title: str = Field(default="Terminal", description="Window title bar label")
    shell: str = Field(default="bash", description="Shell type: bash, zsh, sh, powershell")
    lines: List[str] = Field(default_factory=list, description="Ordered terminal output lines")


class TableBlock(BaseModel):
    """Structured comparison or data table block with strict A4 bounds."""

    type: Literal["table"] = "table"
    caption: Optional[str] = Field(default=None, description="Table title or caption")
    columns: List[str] = Field(description="Column header titles")
    rows: List[List[str]] = Field(description="Grid data rows")
    alignment: Optional[List[str]] = Field(default=None, description="Column alignment: left, center, right")


class SourceBlock(BaseModel):
    """Structured source citation or reference card with clickable URL."""

    type: Literal["source"] = "source"
    title: str = Field(description="Source title or article headline")
    publisher: Optional[str] = Field(default=None, description="Publisher or domain name")
    url: str = Field(description="Canonical source URL")
    accessed_at: Optional[str] = Field(default=None, description="Retrieval date/time")
    mode: Literal["card", "inline"] = Field(default="card", description="Visual display mode")


class CalloutBlock(BaseModel):
    """Structured editorial callout box with icon and semantic styling."""

    type: Literal["callout"] = "callout"
    variant: Literal["note", "important", "warning", "tip", "definition"] = Field(
        default="note", description="Semantic callout type"
    )
    title: str = Field(default="Note", description="Callout header title")
    content: str = Field(description="Callout explanation text")
    icon: Optional[str] = Field(default=None, description="Lucide icon override")


class ChartSeries(BaseModel):
    """Single data series in a chart."""

    name: str = Field(description="Series label")
    values: List[float] = Field(description="Numeric data points")
    color: Optional[str] = Field(default=None, description="Design token color override")


class ChartBlock(BaseModel):
    """Structured technical/benchmark chart block."""

    type: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie", "donut"] = Field(default="bar")
    title: str = Field(description="Chart title")
    labels: List[str] = Field(description="X-axis or category labels")
    series: List[Dict[str, Any]] = Field(description="Data series definitions")
    x_label: Optional[str] = Field(default=None, description="X-axis label")
    y_label: Optional[str] = Field(default=None, description="Y-axis label")
    source_ids: List[str] = Field(default_factory=list, description="Referenced source citations")


class DiagramBlock(BaseModel):
    """Technical architecture or flowchart diagram block."""

    type: Literal["diagram"] = "diagram"
    diagram_type: Literal["mermaid", "flowchart", "sequence", "architecture"] = Field(default="mermaid")
    code: str = Field(description="Mermaid or diagram definition code")
    caption: Optional[str] = Field(default=None, description="Diagram caption")
    direction: Optional[str] = Field(default="TD", description="Flow direction: TD, LR, TB")


class QuoteBlock(BaseModel):
    """Editorial quote block with attribution."""

    type: Literal["quote"] = "quote"
    quote: str = Field(description="Quotation text")
    author: Optional[str] = Field(default=None, description="Attributed person or author")
    affiliation: Optional[str] = Field(default=None, description="Role or organization")


class StatisticBlock(BaseModel):
    """Prominent metric or large-number callout."""

    type: Literal["statistic"] = "statistic"
    value: str = Field(description="Display number or stat, e.g. '1.2M+'")
    label: str = Field(description="Metric label")
    description: Optional[str] = Field(default=None, description="Contextual explanation")


class TextBlock(BaseModel):
    """Standard technical prose block."""

    type: Literal["text"] = "text"
    text: str = Field(description="Main body text")
    paragraphs: List[str] = Field(default_factory=list, description="Optional split paragraphs")


class HeadingBlock(BaseModel):
    """Section or subsection heading block."""

    type: Literal["heading"] = "heading"
    level: int = Field(default=2, ge=1, le=5, description="Heading level h1-h5")
    text: str = Field(description="Heading text")


# Union type for all content blocks
ContentBlock = Union[
    CodeBlock,
    TerminalBlock,
    TableBlock,
    SourceBlock,
    CalloutBlock,
    ChartBlock,
    DiagramBlock,
    QuoteBlock,
    StatisticBlock,
    TextBlock,
    HeadingBlock,
]

