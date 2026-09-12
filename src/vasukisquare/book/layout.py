from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class VisualAnchorType(str, Enum):
    """Visual layout anchor or focal element for a section or page."""

    CODE = "code"
    TABLE = "table"
    DIAGRAM = "diagram"
    TIMELINE = "timeline"
    QUOTE = "quote"
    COMPARISON = "comparison"
    STATISTIC = "statistic"
    TEXT = "text"


class TechnicalPageType(str, Enum):
    """Deterministic technical page archetypes for pedagogical rigor."""

    CONCEPT = "concept"
    INSTALLATION = "installation"
    CONFIGURATION = "configuration"
    TERMINAL_TUTORIAL = "terminal_tutorial"
    CODE_TUTORIAL = "code_tutorial"
    API_REFERENCE = "api_reference"
    CRUD_EXAMPLE = "crud_example"
    COMPARISON = "comparison"
    ARCHITECTURE = "architecture"
    DEBUGGING = "debugging"
    EXERCISE = "exercise"
    MINI_PROJECT = "mini_project"
    DEPLOYMENT = "deployment"
    BENCHMARK = "benchmark"
    SUMMARY = "summary"


class TechnicalPageSpec(BaseModel):
    """Deterministic contract defining required components and constraints for a technical page type."""

    page_type: TechnicalPageType = TechnicalPageType.CONCEPT
    required_components: List[str] = Field(default_factory=lambda: ["heading", "text", "callout"])
    target_word_count_min: int = Field(default=120)
    target_word_count_max: int = Field(default=350)
    requires_code: bool = Field(default=False)
    requires_terminal: bool = Field(default=False)
    requires_table: bool = Field(default=False)
    requires_facts: bool = Field(default=True)
    suggested_layout: str = Field(default="editorial")


PAGE_TYPE_SPECS: Dict[TechnicalPageType, TechnicalPageSpec] = {
    TechnicalPageType.CONCEPT: TechnicalPageSpec(
        page_type=TechnicalPageType.CONCEPT,
        required_components=["heading", "text", "callout"],
        suggested_layout="split_explainer",
    ),
    TechnicalPageType.INSTALLATION: TechnicalPageSpec(
        page_type=TechnicalPageType.INSTALLATION,
        required_components=["heading", "text", "terminal", "callout"],
        requires_terminal=True,
        suggested_layout="editorial",
    ),
    TechnicalPageType.CONFIGURATION: TechnicalPageSpec(
        page_type=TechnicalPageType.CONFIGURATION,
        required_components=["heading", "text", "code", "callout"],
        requires_code=True,
        suggested_layout="code_focus",
    ),
    TechnicalPageType.TERMINAL_TUTORIAL: TechnicalPageSpec(
        page_type=TechnicalPageType.TERMINAL_TUTORIAL,
        required_components=["heading", "text", "terminal", "callout"],
        requires_terminal=True,
        suggested_layout="editorial",
    ),
    TechnicalPageType.CODE_TUTORIAL: TechnicalPageSpec(
        page_type=TechnicalPageType.CODE_TUTORIAL,
        required_components=["heading", "text", "code", "callout"],
        requires_code=True,
        suggested_layout="code_focus",
    ),
    TechnicalPageType.API_REFERENCE: TechnicalPageSpec(
        page_type=TechnicalPageType.API_REFERENCE,
        required_components=["heading", "text", "table", "code"],
        requires_code=True,
        requires_table=True,
        suggested_layout="comparison",
    ),
    TechnicalPageType.CRUD_EXAMPLE: TechnicalPageSpec(
        page_type=TechnicalPageType.CRUD_EXAMPLE,
        required_components=["heading", "text", "code", "callout"],
        requires_code=True,
        suggested_layout="code_focus",
    ),
    TechnicalPageType.COMPARISON: TechnicalPageSpec(
        page_type=TechnicalPageType.COMPARISON,
        required_components=["heading", "text", "table", "callout"],
        requires_table=True,
        suggested_layout="comparison",
    ),
    TechnicalPageType.ARCHITECTURE: TechnicalPageSpec(
        page_type=TechnicalPageType.ARCHITECTURE,
        required_components=["heading", "text", "diagram", "callout"],
        suggested_layout="diagram_focus",
    ),
    TechnicalPageType.DEBUGGING: TechnicalPageSpec(
        page_type=TechnicalPageType.DEBUGGING,
        required_components=["heading", "text", "terminal", "callout"],
        requires_terminal=True,
        suggested_layout="editorial",
    ),
    TechnicalPageType.EXERCISE: TechnicalPageSpec(
        page_type=TechnicalPageType.EXERCISE,
        required_components=["heading", "text", "step", "callout"],
        suggested_layout="editorial",
    ),
    TechnicalPageType.MINI_PROJECT: TechnicalPageSpec(
        page_type=TechnicalPageType.MINI_PROJECT,
        required_components=["heading", "text", "code", "callout"],
        requires_code=True,
        suggested_layout="code_focus",
    ),
    TechnicalPageType.DEPLOYMENT: TechnicalPageSpec(
        page_type=TechnicalPageType.DEPLOYMENT,
        required_components=["heading", "text", "terminal", "callout"],
        requires_terminal=True,
        suggested_layout="editorial",
    ),
    TechnicalPageType.BENCHMARK: TechnicalPageSpec(
        page_type=TechnicalPageType.BENCHMARK,
        required_components=["heading", "text", "table", "callout"],
        requires_table=True,
        suggested_layout="comparison",
    ),
    TechnicalPageType.SUMMARY: TechnicalPageSpec(
        page_type=TechnicalPageType.SUMMARY,
        required_components=["heading", "text", "callout"],
        suggested_layout="summary",
    ),
}


class LayoutType(str, Enum):
    """Controlled page layout vocabulary supported by the VasukiSquare design system."""

    # 14 Editorial Page Layouts
    EDITORIAL = "editorial"
    SPLIT_EXPLAINER = "split_explainer"
    LARGE_NUMBER = "large_number"
    QUOTE = "quote"
    TIMELINE = "timeline"
    COMPARISON = "comparison"
    DIAGRAM_FOCUS = "diagram_focus"
    CODE_FOCUS = "code_focus"
    CONCEPT_GRID = "concept_grid"
    RESEARCH_HIGHLIGHT = "research_highlight"
    DEFINITION = "definition"
    CASE_STUDY = "case_study"
    FULL_BLEED_STATEMENT = "full_bleed_statement"
    SUMMARY = "summary"

    # Technical Page Layouts
    CONCEPT = "concept"
    INSTALLATION = "installation"
    CONFIGURATION = "configuration"
    TERMINAL_TUTORIAL = "terminal_tutorial"
    CODE_TUTORIAL = "code_tutorial"
    API_REFERENCE = "api_reference"
    CRUD_EXAMPLE = "crud_example"
    ARCHITECTURE = "architecture"
    DEBUGGING = "debugging"
    EXERCISE = "exercise"
    MINI_PROJECT = "mini_project"
    DEPLOYMENT = "deployment"
    BENCHMARK = "benchmark"

    # Structural Frontmatter / Backmatter Layouts
    COVER = "cover"
    IMPRINT = "imprint"
    COPYRIGHT = "copyright"
    TOC = "toc"
    CHAPTER_OPENER = "chapter_opener"
    REFERENCES = "references"
    ACKNOWLEDGEMENT = "acknowledgement"
    THANK_YOU = "thank_you"

    # Compatibility Aliases
    TEXT_HEAVY = "editorial"
    CODE = "code_focus"
