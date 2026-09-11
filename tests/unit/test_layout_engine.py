"""Unit tests for layout vocabulary, anti-repetition constraints, and icon color resolution."""

import pytest
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import VisualAnchorType
from vasukisquare.design.layout_engine import LayoutConstraintEngine
from vasukisquare.design.icons import IconColorResolver, LucideIcon, render_lucide_icon
from vasukisquare.design.tokens import ColorToken
from vasukisquare.design.theme import Theme


def test_14_editorial_layouts_present():
    expected_layouts = [
        "editorial",
        "split_explainer",
        "large_number",
        "quote",
        "timeline",
        "comparison",
        "diagram_focus",
        "code_focus",
        "concept_grid",
        "research_highlight",
        "definition",
        "case_study",
        "full_bleed_statement",
        "summary",
    ]
    all_layout_values = {layout.value for layout in LayoutType}
    for expected in expected_layouts:
        assert expected in all_layout_values, f"Layout '{expected}' missing from LayoutType vocabulary."


def test_anti_repetition_layout_selection():
    engine = LayoutConstraintEngine()

    # Selecting layout for CODE after CODE_FOCUS should switch to SPLIT_EXPLAINER or alternate
    first_choice = engine.select_layout(VisualAnchorType.CODE, previous_layout=None)
    assert first_choice == LayoutType.CODE_FOCUS

    second_choice = engine.select_layout(VisualAnchorType.CODE, previous_layout=LayoutType.CODE_FOCUS)
    assert second_choice != LayoutType.CODE_FOCUS
    assert second_choice in [LayoutType.SPLIT_EXPLAINER, LayoutType.CASE_STUDY, LayoutType.EDITORIAL]


def test_layout_sequence_validation():
    engine = LayoutConstraintEngine()

    # Valid sequence with variety
    valid_sequence = [
        LayoutType.EDITORIAL,
        LayoutType.CODE_FOCUS,
        LayoutType.COMPARISON,
        LayoutType.LARGE_NUMBER,
        LayoutType.QUOTE,
    ]
    assert engine.validate_layout_sequence(valid_sequence) is True

    # Invalid sequence with consecutive duplicates
    invalid_sequence = [
        LayoutType.EDITORIAL,
        LayoutType.CODE_FOCUS,
        LayoutType.CODE_FOCUS,  # Duplicate consecutive layout
        LayoutType.COMPARISON,
    ]
    assert engine.validate_layout_sequence(invalid_sequence) is False


def test_icon_color_resolution_dark_and_light():
    # Dark chapter: Primary icon should be bright brand green
    dark_primary = IconColorResolver.resolve_color(Theme.DARK, role="primary")
    assert dark_primary == ColorToken.BRAND_GREEN

    # Light chapter: Primary icon should be dark brand green
    light_primary = IconColorResolver.resolve_color(Theme.LIGHT, role="primary")
    assert light_primary == ColorToken.BRAND_GREEN_DARK

    # Dark chapter: Muted icon
    dark_muted = IconColorResolver.resolve_color(Theme.DARK, role="muted")
    assert dark_muted == ColorToken.ON_DARK_MUTED

    # Light chapter: Muted icon
    light_muted = IconColorResolver.resolve_color(Theme.LIGHT, role="muted")
    assert light_muted == ColorToken.MUTED

