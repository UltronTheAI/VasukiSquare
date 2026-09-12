from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from vasukisquare.book.richtext import RichSpan


class TerminalLine(BaseModel):
    """Structured line in a terminal window."""

    kind: Literal["command", "stdout", "output", "success", "warning", "error", "comment"] = "stdout"
    text: str = Field(description="Line content text")
    prompt: Optional[str] = Field(default=None, description="Custom prompt e.g. '$ ', '# '")


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
    lines: List[Union[str, TerminalLine]] = Field(default_factory=list, description="Ordered terminal output lines")


class TableBlock(BaseModel):
    """Structured comparison or data table block with strict A4 bounds."""

    type: Literal["table"] = "table"
    caption: Optional[str] = Field(default=None, description="Table title or caption")
    columns: List[str] = Field(default_factory=list, description="Column header titles")
    headers: Optional[List[str]] = Field(default=None, description="Alias for columns")
    header_icons: Optional[List[Optional[str]]] = Field(default=None, description="Icons for column headers")
    rows: List[List[str]] = Field(default_factory=list, description="Grid data rows (may contain inline markdown bold/code)")
    alignment: Optional[List[str]] = Field(default=None, description="Column alignment: left, center, right")
    icons: Optional[List[List[Optional[str]]]] = Field(default=None, description="Lucide icon names per cell")
    highlight_first_column: bool = Field(default=True, description="Bold the first column for reference rows")
    source_note: Optional[str] = Field(default=None, description="Small source attribution note")

    def model_post_init(self, __context: Any) -> None:
        if not self.columns and self.headers:
            self.columns = self.headers
        elif not self.headers and self.columns:
            self.headers = self.columns


class SourceBlock(BaseModel):
    """Structured source citation or reference card with clickable URL."""

    type: Literal["source"] = "source"
    title: str = Field(description="Source title or article headline")
    publisher: Optional[str] = Field(default=None, description="Publisher or domain name")
    url: str = Field(description="Canonical source URL")
    accessed_at: Optional[str] = Field(default=None, description="Retrieval date/time")
    mode: Literal["card", "inline"] = Field(default="card", description="Visual display mode")
    source_number: Optional[int] = Field(default=None, description="Sequential citation index e.g. [1]")


class CalloutBlock(BaseModel):
    """Structured editorial callout box with icon and semantic styling."""

    type: Literal["callout"] = "callout"
    variant: Literal["note", "tip", "important", "warning", "insight"] = "note"
    title: Optional[str] = Field(default=None, description="Callout title header")
    icon: Optional[str] = Field(default=None, description="Lucide icon name (e.g. info, zap, alert-triangle)")
    content: str = Field(description="Callout main text content")


class IconTextItem(BaseModel):
    """Single item in an icon text list with Lucide icon."""

    icon: str = Field(default="check-circle", description="Lucide icon identifier")
    title: Optional[str] = Field(default=None, description="Optional item heading")
    text: str = Field(description="Item body text")


class IconTextBlock(BaseModel):
    """Multi-item list where every item has an associated Lucide icon."""

    type: Literal["icon_text"] = "icon_text"
    title: Optional[str] = Field(default=None, description="Block title")
    items: List[IconTextItem] = Field(default_factory=list, description="Ordered icon list items")


class ChartBlock(BaseModel):
    """Basic data chart component rendered as pure inline SVG."""

    type: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "comparison"] = "bar"
    title: str = Field(description="Chart title label")
    subtitle: Optional[str] = Field(default=None, description="Chart subtitle")
    categories: List[str] = Field(default_factory=list, description="X-axis category labels")
    labels: Optional[List[str]] = Field(default=None, description="Alias for categories")
    series_names: List[str] = Field(default_factory=lambda: ["Series 1"], description="Legend names")
    values: List[List[float]] = Field(default_factory=list, description="Data values matrix: [series_idx][category_idx]")
    series: Optional[List[Dict[str, Any]]] = Field(default=None, description="Backwards-compatible series dicts")
    x_label: Optional[str] = Field(default=None, description="X-axis label")
    y_label: Optional[str] = Field(default=None, description="Y-axis label")
    source_note: Optional[str] = Field(default=None, description="Source note")
    source_ids: List[str] = Field(default_factory=list, description="Source reference IDs")
    unit: str = Field(default="", description="Value unit suffix (e.g., ms, ops/sec, %)")

    def model_post_init(self, __context: Any) -> None:
        if not self.categories and self.labels:
            self.categories = self.labels
        if not self.values and self.series:
            self.values = [s.get("values", []) for s in self.series]
            self.series_names = [s.get("name", f"Series {i+1}") for i, s in enumerate(self.series)]



class DiagramBlock(BaseModel):
    """Mermaid diagram component."""

    type: Literal["diagram"] = "diagram"
    title: Optional[str] = Field(default=None, description="Diagram caption/title")
    caption: Optional[str] = Field(default=None, description="Alias for title")
    mermaid_code: Optional[str] = Field(default=None, description="Raw Mermaid DSL code")
    code: Optional[str] = Field(default=None, description="Alias for mermaid_code")
    aspect_ratio: str = Field(default="auto", description="Aspect ratio hint")

    def model_post_init(self, __context: Any) -> None:
        if not self.title and self.caption:
            self.title = self.caption
        elif not self.caption and self.title:
            self.caption = self.title
        if not self.mermaid_code and self.code:
            self.mermaid_code = self.code
        elif not self.code and self.mermaid_code:
            self.code = self.mermaid_code


class QuoteBlock(BaseModel):
    """Featured pull quote with attribution."""

    type: Literal["quote"] = "quote"
    quote: str = Field(description="Quote text")
    attribution: Optional[str] = Field(default=None, description="Speaker or source name")
    author: Optional[str] = Field(default=None, description="Alias for attribution")
    role: Optional[str] = Field(default=None, description="Title/Organization of the speaker")
    affiliation: Optional[str] = Field(default=None, description="Alias for role")

    def model_post_init(self, __context: Any) -> None:
        if not self.attribution and self.author:
            self.attribution = self.author
        elif not self.author and self.attribution:
            self.author = self.attribution
        if not self.role and self.affiliation:
            self.role = self.affiliation


class StatisticBlock(BaseModel):
    """Large stat callout with number and narrative description."""

    type: Literal["statistic"] = "statistic"
    stat: Optional[str] = Field(default=None, description="Prominent number or metric (e.g. '99.99%', '4.2x')")
    value: Optional[str] = Field(default=None, description="Alias for stat")
    label: str = Field(description="Short description under the statistic")
    context: Optional[str] = Field(default=None, description="Longer narrative elaboration")
    description: Optional[str] = Field(default=None, description="Alias for context")
    icon: Optional[str] = Field(default=None, description="Lucide icon marker")

    def model_post_init(self, __context: Any) -> None:
        if not self.stat and self.value:
            self.stat = self.value
        elif not self.value and self.stat:
            self.value = self.stat
        if not self.context and self.description:
            self.context = self.description
        elif not self.description and self.context:
            self.description = self.context



class ImageBlock(BaseModel):
    """Structured image or figure block."""

    type: Literal["image"] = "image"
    src: str = Field(description="Image URL or data URI")
    caption: Optional[str] = Field(default=None, description="Figure caption")
    alt: Optional[str] = Field(default=None, description="Accessibility alt text")
    aspect_ratio: Optional[str] = Field(default="16/9", description="Aspect ratio hint")


class TextBlock(BaseModel):
    """Paragraph of text with optional rich formatting spans and semantic typography."""

    type: Literal["text"] = "text"
    text: str = Field(description="Paragraph plain or markdown-like formatted text")
    typography_role: Optional[str] = Field(default=None, description="DESIGN.md semantic typography role")
    spans: Optional[List[RichSpan]] = Field(default=None, description="Structured pre-parsed rich spans")
    rich_spans: Optional[List[RichSpan]] = Field(default=None, description="Alias for spans")
    paragraphs: Optional[List[str]] = Field(default=None, description="Optional multi-paragraph list")

    def model_post_init(self, __context: Any) -> None:
        if not self.spans and self.rich_spans:
            self.spans = self.rich_spans
        elif not self.rich_spans and self.spans:
            self.rich_spans = self.spans



class HeadingBlock(BaseModel):
    """Section heading with optional Lucide icon, eyebrow tag, and typography role."""

    type: Literal["heading"] = "heading"
    level: int = Field(default=2, ge=1, le=5, description="Heading level 1 to 5")
    text: str = Field(description="Heading text content")
    icon: Optional[str] = Field(default=None, description="Optional Lucide icon name")
    eyebrow: Optional[str] = Field(default=None, description="Small micro-uppercase eyebrow tag above heading")
    typography_role: Optional[str] = Field(default=None, description="DESIGN.md semantic typography role")


class AcknowledgementBlock(BaseModel):
    """Dedicated full-page acknowledgement editorial block."""

    type: Literal["acknowledgement"] = "acknowledgement"
    title: str = Field(default="Acknowledgements")
    lead: Optional[str] = Field(default=None)
    body: str = Field(default="")
    paragraphs: Optional[List[str]] = Field(default=None)
    contributors: Optional[List[str]] = Field(default=None)
    signature: Optional[str] = Field(default=None)
    affiliation: Optional[str] = Field(default=None)
    icon: Optional[str] = Field(default="sparkles")


class CopyrightBlock(BaseModel):
    """Dedicated full-page copyright, publication rights, and distribution notice block."""

    type: Literal["copyright"] = "copyright"
    title: str = Field(default="Copyright & Publishing Notice")
    book_title: str = Field(default="")
    book_subtitle: Optional[str] = Field(default=None)
    author: Optional[str] = Field(default=None)
    rights_holder: str = Field(default="VasukiSquare Publishing")
    year: Union[int, str] = Field(default=2026)
    edition: str = Field(default="First Edition")
    isbn: Optional[str] = Field(default=None)
    publisher: str = Field(default="VasukiSquare Technical Publishing Engine")
    website: Optional[str] = Field(default="https://vasukisquare.ai")
    rights_notice: Optional[str] = Field(default=None)
    distribution_restrictions: Optional[str] = Field(default=None)
    license_notes: Optional[str] = Field(default=None)
    disclaimer: Optional[str] = Field(default=None)
    ordering_info: Optional[str] = Field(default=None)


class TocEntry(BaseModel):
    """Entry in the dynamic Table of Contents."""

    chapter_number: Optional[int] = Field(default=None, description="Chapter number if chapter opener")
    title: str = Field(description="Chapter title or section title")
    page_number: int = Field(description="Starting physical page number")
    icon: Optional[str] = Field(default=None, description="Lucide icon identifier")


class TocBlock(BaseModel):
    """Structured dynamic Table of Contents component."""

    type: Literal["toc"] = "toc"
    title: str = Field(default="Table of Contents", description="TOC title")
    subtitle: Optional[str] = Field(default="Overview of Chapters & Structural Blueprint", description="TOC subtitle")
    entries: List[TocEntry] = Field(default_factory=list, description="Resolved chapter and section entries")



class ComparisonBlock(BaseModel):
    """Side-by-side comparison block (e.g. Pros vs Cons, Do vs Don't)."""

    type: Literal["comparison"] = "comparison"
    title: Optional[str] = Field(default=None, description="Comparison block title")
    left_title: str = Field(default="Do / Advantage", description="Left column heading")
    left_items: List[str] = Field(default_factory=list, description="Left column items")
    right_title: str = Field(default="Don't / Pitfall", description="Right column heading")
    right_items: List[str] = Field(default_factory=list, description="Right column items")
    left_icon: str = Field(default="check", description="Lucide icon for left items")
    right_icon: str = Field(default="x", description="Lucide icon for right items")


class TimelineItem(BaseModel):
    """Single milestone or step in a timeline."""

    time: Optional[str] = Field(default=None, description="Time or phase identifier")
    step: Optional[str] = Field(default=None, description="Step number or label")
    title: str = Field(description="Milestone title")
    description: str = Field(description="Milestone explanation")


class TimelineBlock(BaseModel):
    """Vertical timeline sequence block."""

    type: Literal["timeline"] = "timeline"
    title: Optional[str] = Field(default=None, description="Timeline title")
    items: List[Union[Dict[str, str], TimelineItem]] = Field(default_factory=list, description="Ordered timeline items")


class ChecklistItem(BaseModel):
    """Single item in a checklist."""

    text: str = Field(description="Checklist label text")
    checked: bool = Field(default=True, description="Whether item is marked complete")


class ChecklistBlock(BaseModel):
    """Checklist or key takeaways block."""

    type: Literal["checklist"] = "checklist"
    title: Optional[str] = Field(default=None, description="Checklist title")
    items: List[Union[Dict[str, Any], ChecklistItem, str]] = Field(default_factory=list, description="Checklist items")


class StepItem(BaseModel):
    """Single step in a procedural tutorial block."""

    step_number: Optional[int] = Field(default=None, description="Step sequence number")
    title: str = Field(description="Step title")
    description: str = Field(description="Step description")
    code: Optional[str] = Field(default=None, description="Optional command or code snippet")
    language: Optional[str] = Field(default="bash", description="Code language")


class StepBlock(BaseModel):
    """Step-by-step procedural tutorial block."""

    type: Literal["step"] = "step"
    title: Optional[str] = Field(default=None, description="Step block title")
    steps: List[Union[Dict[str, Any], StepItem]] = Field(default_factory=list, description="Ordered tutorial steps")


class DefinitionBlock(BaseModel):
    """Technical glossary or term definition card."""

    type: Literal["definition"] = "definition"
    term: str = Field(description="Term or keyword being defined")
    definition: str = Field(description="Precise technical definition")
    pronunciation: Optional[str] = Field(default=None, description="Phonetic pronunciation")
    part_of_speech: Optional[str] = Field(default=None, description="Part of speech, e.g. noun, verb")
    example: Optional[str] = Field(default=None, description="Usage example or code snippet")


class ExerciseBlock(BaseModel):
    """Practical hands-on exercise / challenge block."""

    type: Literal["exercise"] = "exercise"
    title: str = Field(description="Exercise title")
    objective: str = Field(description="Goal or learning outcome")
    instructions: List[str] = Field(default_factory=list, description="Step-by-step instructions")
    difficulty: str = Field(default="Intermediate", description="Difficulty: Beginner, Intermediate, Advanced")
    starter_code: Optional[str] = Field(default=None, description="Starter template code")
    solution: Optional[str] = Field(default=None, description="Optional solution reference")
    hints: Optional[List[str]] = Field(default=None, description="Helpful hints")


# Aliases for unified card models
IconCard = CalloutBlock
InfoCard = CalloutBlock
WarningCard = CalloutBlock
TipCard = CalloutBlock
StatisticCard = StatisticBlock
QuoteCard = QuoteBlock


# Union type for all content blocks
ContentBlock = Union[
    CodeBlock,
    TerminalBlock,
    TableBlock,
    SourceBlock,
    CalloutBlock,
    IconTextBlock,
    ChartBlock,
    DiagramBlock,
    QuoteBlock,
    StatisticBlock,
    ImageBlock,
    TextBlock,
    HeadingBlock,
    AcknowledgementBlock,
    CopyrightBlock,
    TocBlock,
    ComparisonBlock,
    TimelineBlock,
    ChecklistBlock,
    StepBlock,
    DefinitionBlock,
    ExerciseBlock,
]

