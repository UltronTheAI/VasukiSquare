import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator, field_validator
from vasukisquare.book.layout import (
    LayoutType,
    VisualAnchorType,
    TechnicalPageType,
    TechnicalPageSpec,
    PAGE_TYPE_SPECS,
    ContentBudget,
    ContentDensity,
    PublicationProfile,
    ContentCapacity,
)
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
    cover_style: str = Field(
        default="editorial_minimal",
        description="Cover style family: editorial_minimal, mountain_landscape, ocean_horizon, sky_clouds, abstract_geometric, typographic_poster, botanical_organic, terrain_journey, symbolic_object, cinematic_landscape",
    )
    visual_subject: str = Field(
        default="",
        description="Specific visual subject description for the cover artwork",
    )
    mood: str = Field(
        default="editorial",
        description="Mood: calm, optimistic, precise, dramatic, reflective, modern",
    )
    composition_style: str = Field(
        default="asymmetric_left",
        description="Composition family: asymmetric_left, centered_editorial, bottom_weighted, top_heavy_minimal, large_typography, vertical_split, framed_technical, geometric_grid, diagonal_accent, icon_led, typography_only, split_panel, sparse_luxury, dense_blueprint, numeric_motif, abstract_lines",
    )
    background_style: str = Field(
        default="solid_light",
        description="Background style: solid_light, subtle_grid, layered_mesh, radial_glow, geometric_matrix, minimal_slate, split_tone",
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
        default_factory=lambda: ["horizontal_rule"],
        description="Accent decorations: vertical_accent_bar, horizontal_rule, corner_brackets, tag_pill, subtle_badge, dot_grid, none",
    )
    icon_strategy: str = Field(
        default="none",
        description="Icon placement strategy: hero_top, integrated_badge, watermarked_background, bottom_corner, inline_prefix, none",
    )
    hero_icon: Optional[str] = Field(
        default=None,
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
    density: str = Field(
        default="minimal",
        description="Density alias: minimal, moderate, dense",
    )
    contrast_mode: str = Field(
        default="high_contrast_light",
        description="Contrast mode: high_contrast_light, high_contrast_dark, deep_teal_minimal, dark_slate_accent",
    )
    decorative_geometry: str = Field(
        default="none",
        description="Geometric motif: database_nodes, circuit_grid, structural_rings, abstract_matrix, angular_lines, code_terminal_frame, none",
    )
    category_badge: Optional[str] = Field(
        default=None,
        description="Optional category badge text derived from BookIntent, e.g. 'PRACTICAL GUIDE', 'TECHNICAL HANDBOOK'",
    )
    rationale: str = Field(
        default="Art-directed composition aligned with technical depth and audience.",
        description="Design rationale for this composition",
    )
    palette_theme: str = Field(
        default="editorial_calm",
        description="Theme palette: editorial_calm, deep_teal, accent_purple, accent_orange, accent_blue",
    )
    accent_color: str = Field(default=ColorToken.BRAND_TEAL.value)
    background_color: str = Field(default=ColorToken.CANVAS.value)
    title: str = ""
    subtitle: Optional[str] = None
    category: str = Field(default="General", description="Domain classification")
    tone: str = Field(default="authoritative", description="Editorial tone")
    audience: str = Field(default="General Practitioners and Professionals", description="Target readership")
    author: Optional[str] = None
    edition: Optional[str] = None
    cover_seed: int = Field(default=42)

    @property
    def layout_style(self) -> str:
        """Backward compatibility alias for layout_style."""
        return self.composition_style or self.cover_style

    @property
    def geometry_seed(self) -> int:
        """Backward compatibility alias for geometry_seed."""
        return self.cover_seed

    @model_validator(mode="after")
    def validate_token_colors_and_branding(self) -> "CoverDesignPlan":
        validate_color_token(self.accent_color)
        validate_color_token(self.background_color)
        if not self.author:
            from vasukisquare.config import get_app_config
            self.author = get_app_config().branding.author_name
        if not self.edition:
            from vasukisquare.config import get_app_config
            self.edition = get_app_config().edition.name
        return self


# Backward-compatible alias
CoverPlan = CoverDesignPlan


def validate_book_title(title: Optional[str]) -> bool:
    """Validate that a book title meets strict publishing constraints: non-empty, clean, and <= 50 chars."""
    if not title or not isinstance(title, str):
        return False
    clean = title.strip().strip('"\'`')
    if not clean:
        return False
    if len(clean) > 50:
        return False
    if "\n" in clean or "\r" in clean:
        return False
    # Reject obvious LLM chatter or malformed commentary
    lower = clean.lower()
    if lower.startswith("here is") or lower.startswith("title:") or lower.startswith("book title:"):
        return False
    if clean.startswith("{") or clean.startswith("["):
        return False
    return True


class BookIntent(BaseModel):
    """Inferred user intent, technical scope, and editorial parameters."""

    topic: str = Field(default="", description="The core subject of the book")
    title: Optional[str] = Field(default=None, description="Explicit or resolved book title (<= 50 chars)")
    subtitle: Optional[str] = Field(default=None, description="Optional book subtitle (<= 90 chars)")
    original_prompt: Optional[str] = Field(default=None, description="Original user editorial brief/prompt")
    book_type: str = Field(
        default="practical_guide",
        description="Type of book: practical_guide, technical_deep_dive, handbook, tutorial_manual, beginner_guide, executive_briefing",
    )
    target_audience: str = Field(
        default="General Practitioners and Professionals",
        description="Target readership",
    )
    purpose: str = Field(
        default="Provide an actionable, comprehensive guide to the subject.",
        description="Primary educational or practical objective of the book",
    )
    tone: str = Field(
        default="practical",
        description="Editorial tone: practical, authoritative, clear, encouraging, analytical",
    )
    technical_depth: str = Field(
        default="intermediate",
        description="Technical depth: introductory, intermediate, advanced, expert",
    )
    approximate_length: str = Field(
        default="standard",
        description="Length: short (20-40 pages), standard (40-70 pages), comprehensive (70-120 pages)",
    )
    required_topics: List[str] = Field(
        default_factory=list,
        description="Specific topics or subjects that MUST be covered in the book",
    )
    avoid_topics: List[str] = Field(
        default_factory=list,
        description="Topics, cliches, or filler to explicitly avoid",
    )
    desired_elements: List[str] = Field(
        default_factory=list,
        description="Specific structural elements wanted: exercises, checklists, 30-day plan, code examples, case studies",
    )
    special_instructions: List[str] = Field(
        default_factory=list,
        description="Any custom constraints or editorial instructions",
    )
    target_pages: Optional[int] = Field(default=None, ge=1)
    is_technical: bool = Field(default=False, description="Whether the book is a software/engineering technical manual")
    publication_profile: PublicationProfile = Field(
        default=PublicationProfile.GENERAL_NONFICTION,
        description="Genre publication profile: technical, general_nonfiction, educational, fiction, poetry, magazine, news, report",
    )
    chapter_count: Optional[int] = Field(default=None, description="Explicit chapter count constraint if specified")
    research_intensity: str = Field(default="standard", description="standard, deep, academic")
    code_requirements: bool = Field(default=False)
    diagram_requirements: bool = Field(default=True)
    primary_programming_language: Optional[str] = Field(
        default=None,
        description="Primary programming language (e.g. python, rust, go, typescript) if applicable",
    )
    domain_topic: Optional[str] = Field(
        default=None,
        description="Main subject domain (e.g. habits, productivity, distributed_systems)",
    )


class PageCompletenessScore(BaseModel):
    """Semantic content completeness and information density evaluation."""

    score: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall semantic completeness score (0.0 to 1.0)")
    core_topic_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    explanation_depth: float = Field(default=1.0, ge=0.0, le=1.0)
    example_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    practical_value: float = Field(default=1.0, ge=0.0, le=1.0)
    component_diversity: float = Field(default=1.0, ge=0.0, le=1.0)
    novelty: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    filler_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    repetition_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    genre_mismatch_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    passes_threshold: bool = Field(default=True)
    detected_issues: List[str] = Field(default_factory=list)

    @property
    def total_score(self) -> float:
        """Score expressed as a percentage 0.0 to 100.0."""
        return self.score * 100.0


# Alias PageContentBudget to ContentBudget
PageContentBudget = ContentBudget


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

    @field_validator("theme", mode="before")
    @classmethod
    def _validate_theme(cls, v: Any) -> Theme:
        if isinstance(v, str):
            try:
                return Theme(v.lower())
            except ValueError:
                return Theme.LIGHT
        return v

    @model_validator(mode="after")
    def set_theme_from_chapter_num(self) -> "PlannedChapter":
        self.theme = get_chapter_theme(self.chapter_number)
        return self

    @property
    def target_pages(self) -> int:
        """Backward-compatible alias for page_budget."""
        return self.page_budget


class PagePurpose(BaseModel):
    """Explicit purpose, pedagogical contract, and content budget for an individual content page."""

    page_type: str = Field(default="concept", description="Archetype: concept, history, features, code_tutorial, terminal_tutorial, exercise, debugging, comparison, mini_project")
    learning_goal: str = Field(default="", description="Specific outcome or takeaway for the reader")
    concepts: List[str] = Field(default_factory=list, description="Core concepts taught on this page")
    required_components: List[str] = Field(default_factory=list, description="Eligible block components (e.g. ['explanation', 'code', 'output', 'exercise'])")
    forbidden_components: List[str] = Field(default_factory=list, description="Explicitly forbidden blocks (e.g. ['step'] on concept pages)")
    is_hands_on: bool = Field(default=False, description="Whether this page requires runnable code/commands")
    content_depth: str = Field(default="normal", description="Content depth level: introductory, normal, deep")
    minimum_content_units: int = Field(default=4, ge=1, description="Minimum distinct educational components required")
    estimated_content_capacity: str = Field(default="high", description="Estimated capacity: low, medium, high, very_high")
    publication_profile: Optional[PublicationProfile] = None
    content_budget: Optional[ContentBudget] = Field(default=None, description="Detailed content and density allocation budget")


class RequirementCoverageItem(BaseModel):
    """Individual item in the requirement coverage matrix."""

    requirement: str
    planned: bool = True
    chapter_number: Optional[int] = None
    page_numbers: List[int] = Field(default_factory=list)


class RequirementCoverageMatrix(BaseModel):
    """Validates that all user-requested topics and elements are planned prior to generation."""

    items: List[RequirementCoverageItem] = Field(default_factory=list)
    is_complete: bool = True
    missing_requirements: List[str] = Field(default_factory=list)


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
    page_purpose: Optional[PagePurpose] = None

    @field_validator("theme", mode="before")
    @classmethod
    def _validate_theme(cls, v: Any) -> Theme:
        if isinstance(v, str):
            try:
                return Theme(v.lower())
            except ValueError:
                return Theme.LIGHT
        return v


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

    @property
    def all_pages(self) -> List[PlannedPage]:
        """Backward-compatible alias for all_planned_pages."""
        return self.all_planned_pages

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

    @field_validator("theme", mode="before")
    @classmethod
    def _validate_theme(cls, v: Any) -> Theme:
        if isinstance(v, str):
            try:
                return Theme(v.lower())
            except ValueError:
                return Theme.LIGHT
        return v


class ChapterMetadata(BaseModel):
    """Metadata for a chapter within a book."""

    chapter_number: int = Field(ge=1)
    title: str
    summary: Optional[str] = None
    icon: Optional[str] = None
    page_count: int = Field(default=0, ge=0)
    theme: Theme = Theme.LIGHT

    @field_validator("theme", mode="before")
    @classmethod
    def _validate_theme(cls, v: Any) -> Theme:
        if isinstance(v, str):
            try:
                return Theme(v.lower())
            except ValueError:
                return Theme.LIGHT
        return v

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

    @field_validator("theme", mode="before")
    @classmethod
    def _validate_theme(cls, v: Any) -> Theme:
        if isinstance(v, str):
            try:
                return Theme(v.lower())
            except ValueError:
                return Theme.LIGHT
        return v

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
    author: Optional[str] = None
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
        if not self.author:
            from vasukisquare.config import get_app_config
            self.author = get_app_config().branding.author_name
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
