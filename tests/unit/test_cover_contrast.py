"""Comprehensive regression and unit tests for cover text contrast and color selection."""

import pytest
from vasukisquare.book.models import BookIntent, CoverDesignPlan
from vasukisquare.cover.contrast import (
    calculate_contrast_ratio,
    get_contrasting_text_palette,
    is_light_color,
    relative_luminance,
    validate_cover_contrast,
    auto_correct_cover_html,
)
from vasukisquare.cover.planner import CoverPlannerAgent
from vasukisquare.cover.renderer import CoverRenderer
from vasukisquare.cover.styles import ALL_COVER_STYLES
from vasukisquare.cover.validator import CoverValidator


def test_contrast_calculation_math():
    """Verify WCAG relative luminance and contrast ratio calculations."""
    # Pure black vs pure white is exactly 21:1
    assert calculate_contrast_ratio("#000000", "#ffffff") == 21.0
    assert calculate_contrast_ratio("#ffffff", "#ffffff") == 1.0

    # Cream vs near-black #111827
    cream = "#faf8f5"
    ratio = calculate_contrast_ratio(cream, "#111827")
    assert ratio >= 15.0  # Outstanding contrast, far exceeds 7:1

    # Cream vs pure white is extremely low contrast
    white_ratio = calculate_contrast_ratio(cream, "#ffffff")
    assert white_ratio < 1.1  # Fails completely


def test_regression_1_near_white_bg_with_white_title():
    """1. Near-white/cream background + white title: must fail validation and be auto-corrected to dark title."""
    near_white_bg = "#fefbf6"
    white_title = "#ffffff"

    # Validation must detect failure
    report = validate_cover_contrast(
        background_color=near_white_bg,
        title_color=white_title,
        auto_correct=True,
    )
    assert report.valid is False
    assert len(report.errors) > 0
    assert "Title" in report.errors[0]
    assert report.corrections_applied.get("title") == "#111827"

    # Auto-corrected HTML must have dark high-contrast title
    raw_html = f'<div style="background-color: {near_white_bg};"><h1 style="color: #ffffff;">Good Habits</h1></div>'
    fixed_html = auto_correct_cover_html(raw_html, near_white_bg)
    assert 'color: #111827' in fixed_html
    assert 'color: #ffffff' not in fixed_html


def test_regression_2_dark_bg_with_dark_title():
    """2. Dark background + dark title: must fail validation and be auto-corrected to light title."""
    dark_bg = "#001e2b"  # Deep teal
    dark_title = "#111827"

    # Validation must detect failure
    report = validate_cover_contrast(
        background_color=dark_bg,
        title_color=dark_title,
        auto_correct=True,
    )
    assert report.valid is False
    assert len(report.errors) > 0
    assert "Title" in report.errors[0]
    assert report.corrections_applied.get("title") == "#ffffff"

    # Auto-corrected HTML must have light high-contrast title
    raw_html = f'<div style="background-color: {dark_bg};"><h1 style="color: #111827;">System Internals</h1></div>'
    fixed_html = auto_correct_cover_html(raw_html, dark_bg)
    assert 'color: #ffffff' in fixed_html
    assert 'color: #111827' not in fixed_html


def test_regression_3_medium_background_chooses_higher_contrast():
    """3. Medium background: choose whichever semantic text palette provides sufficient contrast."""
    # Mid-gray / slate backgrounds
    medium_bgs = ["#64748b", "#78909c", "#94a3b8", "#e2e8f0", "#1e293b", "#cbd5e1"]
    for bg in medium_bgs:
        palette = get_contrasting_text_palette(bg)
        assert palette.title_contrast >= 4.5, f"Title contrast on medium bg {bg} must be >= 4.5, got {palette.title_contrast}"
        # Validate that whichever title color was chosen has higher contrast than the alternative
        alt_title = "#ffffff" if palette.cover_title == "#111827" else "#111827"
        chosen_contrast = calculate_contrast_ratio(bg, palette.cover_title)
        alt_contrast = calculate_contrast_ratio(bg, alt_title)
        assert chosen_contrast >= alt_contrast


def test_regression_4_all_ten_cover_families_pass_contrast():
    """4. Every one of the 10 cover families: render test cover, verify all essential text passes contrast validation."""
    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    for style_name in ALL_COVER_STYLES:
        plan = planner.plan_cover(
            title="Building High-Impact Habits",
            subtitle="The Definitive Guide to Behavioral Systems and Long-Term Success",
            category="Personal Development",
            seed=42195,
            style_override=style_name,
            author="Vasuki Editorial Team",
        )

        # 1. 1600x2560 Source Artwork
        artwork_html = renderer.render_source_artwork(plan)
        report_artwork = CoverValidator.validate_cover(plan, artwork_html)
        assert report_artwork.valid is True, f"Style '{style_name}' source artwork failed validation: {report_artwork.errors}"

        # 2. A4 Printable Page
        a4_page = renderer.render_a4_cover_page(plan, book_id="habits-test")
        report_a4 = CoverValidator.validate_cover(plan, a4_page.html)
        assert report_a4.valid is True, f"Style '{style_name}' A4 page failed validation: {report_a4.errors}"

        # 3. Check individual elements contrast ratio
        bg = plan.background_color or "#ffffff"
        palette = get_contrasting_text_palette(bg)
        assert palette.title_contrast >= 7.0, f"Style '{style_name}' title contrast {palette.title_contrast} < 7.0"
        assert palette.subtitle_contrast >= 4.5, f"Style '{style_name}' subtitle contrast {palette.subtitle_contrast} < 4.5"
        assert palette.metadata_contrast >= 4.5, f"Style '{style_name}' metadata contrast {palette.metadata_contrast} < 4.5"


def test_failing_cream_cover_example_good_habits():
    """Test specifically the user-reported failing cream cover scenario ('Good Habits')."""
    cream_backgrounds = ["#fff8e0", "#f9fbfa", "#f4f7f6", "#eceff1", "#ffffff"]

    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    for cream_bg in cream_backgrounds:
        plan = CoverDesignPlan(
            title="Good Habits",
            subtitle="Transform Your Daily Life with Tiny Positive Changes",
            category="Personal Development",
            author="Vasuki",
            background_color=cream_bg,
            cover_style="editorial_minimal",
            cover_seed=123456,
        )

        html = renderer.render_source_artwork(plan)

        # Ensure title is dark (near-black / charcoal) and NOT white
        assert '<h1 style="font-size: 88px; font-weight: 800; line-height: 1.08; color: #111827;' in html or 'color: #111827' in html
        assert '<h1 style="font-size: 88px; font-weight: 800; line-height: 1.08; color: #ffffff;' not in html
        assert '<h1 style="color: #ffffff;' not in html

        # Ensure subtitle is dark Slate (#374151)
        assert 'color: #374151' in html

        # Ensure metadata / edition is readable (#4b5563)
        assert 'color: #4b5563' in html

        # Validate with CoverValidator
        report = CoverValidator.validate_cover(plan, html)
        assert report.valid is True
        assert len(report.errors) == 0


def test_independent_elements_validation():
    """Verify validate_cover_contrast checks title, subtitle, author, edition, category, and header independently."""
    bg = "#ffffff"
    # Fails only edition
    report = validate_cover_contrast(
        background_color=bg,
        title_color="#111827",
        subtitle_color="#374151",
        author_color="#111827",
        edition_color="#e5e7eb",  # Light gray on white - FAILS
        category_color="#374151",
        auto_correct=True,
    )
    assert report.valid is False
    assert len(report.errors) == 1
    assert "Edition" in report.errors[0]
    assert report.corrections_applied.get("edition") == "#4b5563"
