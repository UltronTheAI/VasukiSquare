"""Page layout types and controlled vocabulary definitions."""

from enum import Enum


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
