from enum import Enum
from typing import Any, Dict, List, Optional
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
    CHECKLIST = "checklist"
    EXERCISE = "exercise"


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


class PageComplexity(str, Enum):
    """Classification of page visual and informational density."""

    SIMPLE = "simple"          # Concept explanation, single definition, short summary
    STANDARD = "standard"      # Paragraphs, list, single callout
    COMPLEX = "complex"        # Multiple sections, comparison cards, steps, code, callouts
    VISUAL = "visual"          # Chart, diagram, architecture flow, timeline
    CODE_HEAVY = "code_heavy"  # Terminal command, code snippet, output block, explanations


class LayoutType(str, Enum):
    """Controlled page layout vocabulary supported by the VasukiSquare design system."""

    # 16 Canonical Reusable Page Layout Families
    EDITORIAL_STANDARD = "editorial_standard"
    EDITORIAL_SPLIT = "editorial_split"
    LARGE_INTRO = "large_intro"
    CODE_FOCUS = "code_focus"
    TERMINAL_FOCUS = "terminal_focus"
    DIAGRAM_FOCUS = "diagram_focus"
    COMPARISON_FOCUS = "comparison_focus"
    STEPS_FOCUS = "steps_focus"
    CARDS_FOCUS = "cards_focus"
    QUOTE_OR_DEFINITION = "quote_or_definition"
    ARCHITECTURE_FOCUS = "architecture_focus"
    VISUAL_BOTTOM = "visual_bottom"
    VISUAL_SIDE = "visual_side"
    DENSE_REFERENCE = "dense_reference"
    MINIMAL_SUMMARY = "minimal_summary"
    EXERCISE_FOCUS = "exercise_focus"

    # Backward-compatible Editorial Page Layouts
    EDITORIAL = "editorial"
    SPLIT_EXPLAINER = "split_explainer"
    LARGE_NUMBER = "large_number"
    QUOTE = "quote"
    TIMELINE = "timeline"
    COMPARISON = "comparison"
    CONCEPT_GRID = "concept_grid"
    RESEARCH_HIGHLIGHT = "research_highlight"
    DEFINITION = "definition"
    CASE_STUDY = "case_study"
    FULL_BLEED_STATEMENT = "full_bleed_statement"
    SUMMARY = "summary"

    # Technical Page Layout Aliases
    CONCEPT = "editorial_standard"
    INSTALLATION = "terminal_focus"
    CONFIGURATION = "code_focus"
    TERMINAL_TUTORIAL = "terminal_focus"
    CODE_TUTORIAL = "code_focus"
    API_REFERENCE = "dense_reference"
    CRUD_EXAMPLE = "code_focus"
    ARCHITECTURE = "architecture_focus"
    DEBUGGING = "terminal_focus"
    EXERCISE = "exercise_focus"
    MINI_PROJECT = "code_focus"
    DEPLOYMENT = "terminal_focus"
    BENCHMARK = "comparison_focus"

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
    TEXT_HEAVY = "editorial_standard"
    CODE = "code_focus"


def classify_page_complexity(page_content: Any) -> PageComplexity:
    """Classify the structural and visual complexity of a page based on its content blocks."""
    if not page_content:
        return PageComplexity.SIMPLE

    blocks = getattr(page_content, "blocks", [])
    if not blocks:
        body = getattr(page_content, "body", "") or ""
        return PageComplexity.SIMPLE if len(body.split()) < 150 else PageComplexity.STANDARD

    block_types = [getattr(b, "type", "") for b in blocks]

    has_code = "code" in block_types
    has_terminal = "terminal" in block_types
    has_diagram = "diagram" in block_types
    has_chart = "chart" in block_types
    has_table = "table" in block_types
    has_step = "step" in block_types
    has_comparison = "comparison" in block_types
    has_exercise = "exercise" in block_types

    # Code heavy
    if (has_code and has_terminal) or (has_code and len(block_types) >= 3):
        return PageComplexity.CODE_HEAVY
    if has_code or has_terminal:
        return PageComplexity.CODE_HEAVY

    # Visual
    if has_diagram or has_chart or ("timeline" in block_types):
        return PageComplexity.VISUAL

    # Complex
    if (has_comparison or has_step or has_exercise or has_table) and len(block_types) >= 3:
        return PageComplexity.COMPLEX

    # Standard vs Simple
    if len(block_types) >= 2 or has_table or has_step or has_comparison:
        return PageComplexity.STANDARD

    return PageComplexity.SIMPLE


def select_page_layout(
    complexity: PageComplexity,
    components: Optional[List[str]] = None,
    recent_layouts: Optional[List[str]] = None,
) -> str:
    """Select appropriate layout family matching page complexity and components while avoiding consecutive repetition."""
    comps = set(components or [])
    recent = recent_layouts or []

    # Map candidate layouts by component presence and complexity
    candidates: List[str] = []

    if "exercise" in comps or complexity == PageComplexity.COMPLEX and "step" in comps:
        candidates.extend([LayoutType.EXERCISE_FOCUS.value, LayoutType.STEPS_FOCUS.value])
    elif "diagram" in comps or "chart" in comps:
        candidates.extend([LayoutType.DIAGRAM_FOCUS.value, LayoutType.ARCHITECTURE_FOCUS.value, LayoutType.VISUAL_BOTTOM.value])
    elif "code" in comps and "terminal" in comps:
        candidates.extend([LayoutType.CODE_FOCUS.value, LayoutType.TERMINAL_FOCUS.value])
    elif "code" in comps:
        candidates.extend([LayoutType.CODE_FOCUS.value, LayoutType.EDITORIAL_SPLIT.value])
    elif "terminal" in comps:
        candidates.extend([LayoutType.TERMINAL_FOCUS.value, LayoutType.EDITORIAL_STANDARD.value])
    elif "comparison" in comps or "table" in comps:
        candidates.extend([LayoutType.COMPARISON_FOCUS.value, LayoutType.CARDS_FOCUS.value, LayoutType.DENSE_REFERENCE.value])
    elif "step" in comps:
        candidates.extend([LayoutType.STEPS_FOCUS.value, LayoutType.EDITORIAL_STANDARD.value])
    elif complexity == PageComplexity.VISUAL:
        candidates.extend([LayoutType.DIAGRAM_FOCUS.value, LayoutType.ARCHITECTURE_FOCUS.value, LayoutType.VISUAL_SIDE.value])
    elif complexity == PageComplexity.CODE_HEAVY:
        candidates.extend([LayoutType.CODE_FOCUS.value, LayoutType.TERMINAL_FOCUS.value])
    elif complexity == PageComplexity.COMPLEX:
        candidates.extend([LayoutType.EDITORIAL_SPLIT.value, LayoutType.CARDS_FOCUS.value, LayoutType.DENSE_REFERENCE.value])
    elif complexity == PageComplexity.SIMPLE:
        candidates.extend([LayoutType.LARGE_INTRO.value, LayoutType.QUOTE_OR_DEFINITION.value, LayoutType.MINIMAL_SUMMARY.value, LayoutType.EDITORIAL_STANDARD.value])
    else:
        candidates.extend([LayoutType.EDITORIAL_STANDARD.value, LayoutType.EDITORIAL_SPLIT.value, LayoutType.VISUAL_BOTTOM.value])

    # Fallback pool
    if not candidates:
        candidates = [LayoutType.EDITORIAL_STANDARD.value, LayoutType.EDITORIAL_SPLIT.value]

    # Anti-repetition check: Avoid picking same layout if used > 2 times consecutively or if last layout matches and alternative exists
    last_layout = recent[-1] if recent else None
    second_last = recent[-2] if len(recent) >= 2 else None

    # Filter out layout if it appeared in the last 2 slots consecutively
    for candidate in candidates:
        if last_layout == candidate and second_last == candidate:
            continue
        if len(candidates) > 1 and last_layout == candidate:
            continue
        return candidate

    return candidates[0]
