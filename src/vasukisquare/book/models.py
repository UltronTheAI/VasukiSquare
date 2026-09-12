"""Domain schemas and models for Books, Pages, Covers, Intent, Editorial Plans, and Cover Plans."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator
from vasukisquare.book.layout import LayoutType, VisualAnchorType
from vasukisquare.design.theme import Theme, get_chapter_theme
from vasukisquare.design.tokens import ColorToken, validate_color_token


def generate_id() -> str:
    """Generate a unique string ID."""
    return str(uuid4())


def slugify(text: str) -> str:
    """Convert text to a URL/DB safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", slug)


def normalize_cover_color_token(color: str, default: str) -> str:
    """Ensure color strictly adheres to DESIGN.md tokens, normalizing hex variants."""
    try:
        return validate_color_token(color).value
    except ValueError:
        c_lower = (color or "").strip().lower()
        if any(w in c_lower for w in ["orange", "ff66", "ff7", "fa6", "e65"]):
            return ColorToken.ACCENT_ORANGE.value
        if any(w in c_lower for w in ["purple", "violet", "7b3", "8a2"]):
            return ColorToken.ACCENT_PURPLE.value
        if any(w in c_lower for w in ["pink", "magenta", "f06", "f47"]):
            return ColorToken.ACCENT_PINK.value
        if any(w in c_lower for w in ["blue", "sky", "cyan", "3d4", "028"]):
            return ColorToken.ACCENT_BLUE.value
        if any(w in c_lower for w in ["green", "teal", "00e", "00b", "006"]):
            return ColorToken.BRAND_GREEN.value
        if any(w in c_lower for w in ["fff", "light", "white"]):
            return ColorToken.CANVAS.value
        if any(w in c_lower for w in ["001", "dark", "black", "1c2"]):
            return ColorToken.BRAND_TEAL_DEEP.value
        return default


class CoverDesignPlan(BaseModel):
    """Specification for AI-directed custom cover generation adhering to DESIGN.md tokens."""

    concept_name: str = Field(
        default="Technical Blueprint",
        description="Short descriptive concept name (e.g., 'Cybernetic Blueprint', 'Minimalist Monolith', 'Data Mesh')",
    )
    composition_style: str = Field(
        default="asymmetric_left",
        description="Composition family: centered_editorial, asymmetric_left, bottom_weighted, top_heavy_minimal, large_typography, vertical_split, framed_technical, geometric_grid, diagonal_accent, icon_led, typography_only, split_panel, sparse_luxury, dense_blueprint, numeric_motif, abstract_lines",
    )
    background_style: str = Field(
        default="solid_dark",
        description="Background style: solid_dark, subtle_grid, layered_mesh, radial_glow, geometric_matrix, minimal_slate, split_tone",
    )
    title_alignment: str = Field(
        default="left",
        description="Title text alignment: left, center, right",
    )
    title_position: str = Field(
        default="middle",
        description="Vertical placement of title block: top, upper_third, middle, lower_third, bottom",
    )
    subtitle_position: str = Field(
        default="below_title",
        description="Subtitle placement: below_title, bottom_left, bottom_center, side_column, header_adjacent, none",
    )
    typography_style: str = Field(
        default="modern_technical",
        description="Typography style: bold_sans, modern_technical, editorial_display, compact_heavy, ultra_light_spaced",
    )
    accent_elements: List[str] = Field(
        default_factory=lambda: ["vertical_accent_bar"],
        description="Accent decorations: vertical_accent_bar, horizontal_rule, corner_brackets, tag_pill, subtle_badge, dot_grid, none",
    )
    icon_strategy: str = Field(
        default="hero_top",
        description="Icon placement strategy: hero_top, integrated_badge, watermarked_background, bottom_corner, inline_prefix, none",
    )
    hero_icon: Optional[str] = Field(
        default="sparkles",
        description="Lucide icon identifier if icon_strategy != 'none', e.g. sparkles, database, code, layers, cpu, shield-check, terminal, zap, compass",
    )
    border_strategy: str = Field(
        default="none",
        description="Border strategy: full_frame, left_accent_stripe, top_bottom_rules, technical_corner_brackets, none",
    )
    spacing_strategy: str = Field(
        default="balanced_editorial",
        description="Spacing strategy: expansive_negative_space, compact_technical, balanced_editorial, split_zone",
    )
    visual_density: str = Field(
        default="moderate",
        description="Visual density: sparse, moderate, dense",
    )
    contrast_mode: str = Field(
        default="high_contrast_dark",
        description="Contrast mode: high_contrast_dark, deep_teal_minimal, dark_slate_accent",
    )
    decorative_geometry: str = Field(
        default="database_nodes",
        description="Geometric motif: database_nodes, circuit_grid, structural_rings, abstract_matrix, angular_lines, code_terminal_frame, none",
    )
    rationale: str = Field(
        default="Art-directed composition aligned with technical depth and audience.",
        description="Design rationale for this composition",
    )
    palette_theme: str = Field(
        default="brand_dark",
        description="Theme palette: brand_dark, deep_teal, accent_purple, accent_orange, accent_blue",
    )
    accent_color: str = Field(default=ColorToken.BRAND_GREEN.value)
    background_color: str = Field(default=ColorToken.BRAND_TEAL_DEEP.value)
    title: str = ""
    subtitle: Optional[str] = None
    category: str = Field(default="Software Engineering", description="Domain classification")
    tone: str = Field(default="authoritative", description="Editorial tone")
    audience: str = Field(default="Engineers and Architects", description="Target readership")
    author: str = Field(default="VasukiSquare AI")
    cover_seed: int = Field(default=42)

    @property
    def layout_style(self) -> str:
        """Backward compatibility alias for layout_style."""
        return self.composition_style

    @property
    def geometry_seed(self) -> int:
        """Backward compatibility alias for geometry_seed."""
        return self.cover_seed

    @model_validator(mode="after")
    def validate_token_colors(self) -> "CoverDesignPlan":
        validate_color_token(self.accent_color)
        validate_color_token(self.background_color)
        return self


# Backward-compatible alias
CoverPlan = CoverDesignPlan


class BookIntent(BaseModel):
    """Inferred user intent, technical scope, and editorial parameters."""

    book_type: str = Field(
        default="technical_deep_dive",
        description="Type of book: technical_deep_dive, handbook, architecture_guide, tutorial_manual, executive_briefing",
    )
    target_audience: str = Field(
        default="Software Engineers and Architects",
        description="Target readership",
    )
    technical_depth: str = Field(
        default="advanced",
        description="Technical depth: introductory, intermediate, advanced, expert",
    )
    tone: str = Field(
        default="authoritative",
        description="Editorial tone: authoritative, practical, analytical, educational",
    )
    approximate_length: str = Field(
        default="standard",
        description="Length: short (20-40 pages), standard (40-70 pages), comprehensive (70-120 pages)",
    )
    chapter_count: int = Field(default=6, ge=1, le=16)
    research_intensity: str = Field(default="deep", description="standard, deep, academic")
    code_requirements: bool = Field(default=True)
    diagram_requirements: bool = Field(default=True)
    primary_programming_language: Optional[str] = Field(
        default=None,
        description="Primary programming language (e.g. python, rust, go, typescript) if applicable",
    )
    domain_topic: Optional[str] = Field(
        default=None,
        description="Main subject domain (e.g. python_basics, distributed_systems, machine_learning)",
    )


class SectionPlan(BaseModel):
    """Plan for a sub-section within a chapter."""

    title: str
    key_concepts: List[str] = Field(default_factory=list)
    visual_anchors: List[VisualAnchorType] = Field(default_factory=lambda: [VisualAnchorType.TEXT])
    target_page_count: int = Field(default=1, ge=1)
    description: Optional[str] = None


class PlannedChapter(BaseModel):
    """Plan for an entire chapter including page budget and theme."""

    chapter_number: int = Field(ge=1)
    title: str
    subtitle: Optional[str] = None
    summary: str
    icon: str = "sparkles"
    theme: Theme = Theme.LIGHT
    page_budget: int = Field(default=8, ge=2, description="Total pages including chapter opener")
    sections: List[SectionPlan] = Field(default_factory=list)
    sources_to_cite: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def set_theme_from_chapter_num(self) -> "PlannedChapter":
        self.theme = get_chapter_theme(self.chapter_number)
        return self

    @property
    def target_pages(self) -> int:
        """Backward-compatible alias for page_budget."""
        return self.page_budget


class PlannedPage(BaseModel):
    """Individual pre-allocated page specification in the book plan."""

    page_number: int = Field(ge=1)
    page_type: str
    layout: str
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    theme: Theme = Theme.LIGHT
    icon: Optional[str] = None
    visual_anchor: Optional[VisualAnchorType] = None
    brief: str = ""


class BookPlan(BaseModel):
    """Comprehensive editorial plan structuring the entire book."""

    title: str
    subtitle: str
    running_title: Optional[str] = None
    description: str
    intent: BookIntent
    frontmatter_pages: List[PlannedPage] = Field(default_factory=list)
    chapters: List[PlannedChapter] = Field(default_factory=list)
    backmatter_pages: List[PlannedPage] = Field(default_factory=list)
    all_planned_pages: List[PlannedPage] = Field(default_factory=list)
    total_pages: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def calculate_total_pages_and_running_title(self) -> "BookPlan":
        if self.all_planned_pages:
            self.total_pages = len(self.all_planned_pages)
        if not self.running_title and self.title:
            # Generate short running title if none provided (e.g. text before ':' or first 4-5 words)
            if ":" in self.title:
                self.running_title = self.title.split(":", 1)[0].strip()
            else:
                words = self.title.split()
                self.running_title = " ".join(words[:5]) if len(words) > 5 else self.title
        return self


from vasukisquare.book.components import (
    CalloutBlock,
    ChartBlock,
    CodeBlock,
    ContentBlock,
    DiagramBlock,
    HeadingBlock,
    QuoteBlock,
    SourceBlock,
    StatisticBlock,
    TableBlock,
    TerminalBlock,
    TextBlock,
)


class SourceCitation(BaseModel):
    """Citation metadata referencing external research."""

    url: str
    title: Optional[str] = None
    claim: Optional[str] = None
    quote: Optional[str] = None
    page_number: Optional[int] = None


class PageContent(BaseModel):
    """Structured content payload for a page."""

    headline: Optional[str] = None
    body: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    code_snippets: List[Dict[str, str]] = Field(default_factory=list)
    callouts: List[Dict[str, str]] = Field(default_factory=list)
    blocks: List[ContentBlock] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PageStyle(BaseModel):
    """Visual style overrides and specifications for a page."""

    theme: Theme = Theme.LIGHT
    font_family: str = "Euclid Circular A"
    accent_color: str = "#00ed64"
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    text_muted: Optional[str] = None
    border_color: Optional[str] = None
    opener_template: Optional[str] = None
    layout_variant: Optional[str] = None
    custom_css: Optional[str] = None



class ChapterMetadata(BaseModel):
    """Metadata for a chapter within a book."""

    chapter_number: int = Field(ge=1)
    title: str
    summary: Optional[str] = None
    icon: Optional[str] = None
    page_count: int = Field(default=0, ge=0)
    theme: Theme = Theme.LIGHT

    @model_validator(mode="after")
    def set_theme_from_chapter(self) -> "ChapterMetadata":
        self.theme = get_chapter_theme(self.chapter_number)
        return self


class Page(BaseModel):
    """Represents an individual A4 rendered page stored independently in MongoDB."""

    id: str = Field(default_factory=generate_id)
    book_id: str
    page_number: int = Field(ge=1)
    page_type: str = Field(default=LayoutType.EDITORIAL.value)
    chapter_number: Optional[int] = None
    chapter_name: Optional[str] = None
    theme: Theme = Theme.LIGHT
    layout: str = Field(default=LayoutType.EDITORIAL.value)
    previous_page_id: Optional[str] = None
    next_page_id: Optional[str] = None
    icon: Optional[str] = None
    content: PageContent = Field(default_factory=PageContent)
    style: PageStyle = Field(default_factory=PageStyle)
    sources: List[SourceCitation] = Field(default_factory=list)
    html: str = ""
    validation: Dict[str, Any] = Field(default_factory=dict)

    @property
    def chapter_title(self) -> Optional[str]:
        return self.chapter_name

    @property
    def layout_type(self) -> LayoutType:
        try:
            return LayoutType(self.layout)
        except ValueError:
            return LayoutType.EDITORIAL

    @property
    def icon_name(self) -> Optional[str]:
        return self.icon

    @property
    def html_content(self) -> str:
        return self.html

    @model_validator(mode="after")
    def validate_page_rules(self) -> "Page":
        """Validate chapter opener and theme consistency."""
        if self.chapter_number is not None:
            expected_theme = get_chapter_theme(self.chapter_number)
            self.theme = expected_theme
            self.style.theme = expected_theme

        if self.layout == LayoutType.CHAPTER_OPENER.value or self.page_type == LayoutType.CHAPTER_OPENER.value:
            if self.chapter_number is None or not self.chapter_name:
                raise ValueError("Chapter opener pages must specify chapter_number and chapter_name.")
            if not self.icon:
                raise ValueError("Chapter opener pages must contain exactly one Lucide icon.")
        return self


class Cover(BaseModel):
    """Represents book cover artwork metadata and asset references stored in covers collection."""

    id: str = Field(default_factory=generate_id)
    book_id: str
    width: int = Field(default=1600)
    height: int = Field(default=2560)
    title: str
    design: Dict[str, Any] = Field(default_factory=dict)
    html: str = ""
    image_path: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def subtitle(self) -> Optional[str]:
        return self.design.get("subtitle")


class Book(BaseModel):
    """Represents the complete book entity stored in books collection."""

    id: str = Field(default_factory=generate_id)
    slug: str = ""
    title: str
    subtitle: Optional[str] = None
    running_title: Optional[str] = None
    prompt: str = ""
    description: str = ""
    status: str = "draft"
    chapter_count: int = 0
    page_count: int = 0
    starting_page_id: Optional[str] = None
    cover_id: Optional[str] = None
    chapters: List[ChapterMetadata] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def generate_slug_if_missing(self) -> "Book":
        if not self.slug and self.title:
            self.slug = slugify(self.title)
        if not self.chapter_count and self.chapters:
            self.chapter_count = len(self.chapters)
        if not self.running_title and self.title:
            if ":" in self.title:
                self.running_title = self.title.split(":", 1)[0].strip()
            else:
                words = self.title.split()
                self.running_title = " ".join(words[:5]) if len(words) > 5 else self.title
        return self


class PagePlan(BaseModel):
    """Plan for an individual page."""

    page_number: int
    layout_type: LayoutType
    chapter_number: Optional[int] = None
    title: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    icon_name: Optional[str] = None


class ChapterPlan(BaseModel):
    """Plan for an entire chapter."""

    chapter_number: int = Field(ge=1)
    title: str
    summary: str
    icon_name: str
    pages: List[PagePlan] = Field(default_factory=list)

    @property
    def theme(self) -> Theme:
        """Chapter theme derived from chapter number."""
        return get_chapter_theme(self.chapter_number)


class EditorialPlan(BaseModel):
    """Editorial plan structuring the book's narrative and chapters."""

    book_title: str
    book_subtitle: Optional[str] = None
    target_audience: str
    tone: str
    estimated_pages: int
    chapters: List[ChapterPlan] = Field(default_factory=list)
