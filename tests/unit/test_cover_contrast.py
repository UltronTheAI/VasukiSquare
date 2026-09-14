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

    # Solid dark container (#001e2b) vs pure white title
    container_bg = "#001e2b"
    title_ratio = calculate_contrast_ratio(container_bg, "#ffffff")
    assert title_ratio >= 15.0  # Far exceeds 7:1 AAA target

    # Solid dark container (#001e2b) vs light neutral subtitle (#cbd5e1)
    sub_ratio = calculate_contrast_ratio(container_bg, "#cbd5e1")
    assert sub_ratio >= 9.0  # Far exceeds 4.5:1 AA target


def test_regression_1_solid_container_with_dark_title_corrected_to_white():
    """1. Dark title inside solid dark container fails contrast and is corrected to white."""
    container_bg = "#001e2b"
    dark_title = "#111827"

    # Validation must detect failure against container
    report = validate_cover_contrast(
        background_color="#ffffff",
        title_color=dark_title,
        container_bg=container_bg,
        auto_correct=True,
    )
    assert report.valid is False
    assert len(report.errors) > 0
    assert "Title" in report.errors[0]
    assert report.corrections_applied.get("title") == "#ffffff"

    # Auto-corrected HTML must have white high-contrast title
    raw_html = f'<div class="cover-title-container" style="background-color: {container_bg};"><h1 style="color: #111827;">Good Habits</h1></div>'
    fixed_html = auto_correct_cover_html(raw_html, "#ffffff", container_bg=container_bg)
    assert 'color: #ffffff' in fixed_html
    assert 'color: #111827' not in fixed_html


def test_regression_2_solid_container_layering_and_opacity():
    """2. Solid container has opaque background and renders in front of vector artwork."""
    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    plan = CoverDesignPlan(
        title="Good Habits",
        subtitle="A Practical, Step-by-Step Guide to Lasting Change",
        category="Personal Development",
        author="Vasuki",
        background_color="#f9fbfa",
        cover_style="editorial_minimal",
        cover_seed=123456,
    )

    html = renderer.render_source_artwork(plan)

    # 1. Vector scenery has z-index: 1
    assert 'class="vector-scenery-layer"' in html
    assert 'z-index: 1' in html

    # 2. Solid dark title container has background #001e2b, z-index: 10
    assert 'class="cover-title-container"' in html
    assert 'background-color: #001e2b' in html
    assert 'z-index: 10' in html
    assert 'transparent' not in html.split('cover-title-container')[1].split('>')[0]

    # 3. Typography inside container
    assert 'color: #ffffff' in html
    assert 'color: #cbd5e1' in html
    assert 'Newsreader' in html or 'serif' in html


def test_regression_3_all_ten_cover_families_pass_contrast_and_validation():
    """3. Every one of the 10 cover families: render test cover, verify all essential text passes contrast validation."""
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
        assert 'class="cover-title-container"' in artwork_html

        # 2. A4 Printable Page
        a4_page = renderer.render_a4_cover_page(plan, book_id="habits-test")
        report_a4 = CoverValidator.validate_cover(plan, a4_page.html)
        assert report_a4.valid is True, f"Style '{style_name}' A4 page failed validation: {report_a4.errors}"
        assert 'class="cover-title-container"' in a4_page.html

        # 3. Check individual elements contrast ratio
        bg = plan.background_color or "#ffffff"
        palette = get_contrasting_text_palette(bg)
        assert palette.title_contrast >= 7.0, f"Style '{style_name}' title contrast {palette.title_contrast} < 7.0"
        assert palette.subtitle_contrast >= 4.5, f"Style '{style_name}' subtitle contrast {palette.subtitle_contrast} < 4.5"
        assert palette.metadata_contrast >= 4.5, f"Style '{style_name}' metadata contrast {palette.metadata_contrast} < 4.5"


def test_failing_cream_cover_example_good_habits():
    """Test specifically the user-reported scenario ('Good Habits' on cream background with artwork)."""
    cream_backgrounds = ["#fff8e0", "#f9fbfa", "#f4f7f6", "#eceff1", "#ffffff"]

    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    for cream_bg in cream_backgrounds:
        plan = CoverDesignPlan(
            title="Good Habits",
            subtitle="A Practical, Step-by-Step Guide to Lasting Change",
            category="Personal Development",
            author="Vasuki",
            background_color=cream_bg,
            cover_style="editorial_minimal",
            cover_seed=123456,
        )

        html = renderer.render_source_artwork(plan)

        # Ensure title container is present with solid dark background
        assert 'class="cover-title-container"' in html
        assert 'background-color: #001e2b' in html

        # Ensure title is white (#ffffff) and uses editorial serif
        assert 'color: #ffffff' in html
        assert 'Newsreader' in html or 'serif' in html

        # Ensure subtitle is light neutral (#cbd5e1)
        assert 'color: #cbd5e1' in html

        # Ensure author and metadata are properly contrasted against cream_bg
        assert 'Vasuki' in html
        assert 'FIRST EDITION' in html

        # Validate with CoverValidator
        report = CoverValidator.validate_cover(plan, html)
        assert report.valid is True
        assert len(report.errors) == 0


def test_independent_elements_validation():
    """Verify validate_cover_contrast checks title, subtitle, author, edition, category, and header independently."""
    bg = "#ffffff"
    # Fails only edition (dark color #111827 on dark footer strip #001e2b)
    report = validate_cover_contrast(
        background_color=bg,
        title_color="#ffffff",
        subtitle_color="#cbd5e1",
        author_color="#ffffff",
        edition_color="#111827",  # Dark charcoal on dark footer #001e2b - FAILS
        category_color="#374151",
        container_bg="#001e2b",
        footer_bg="#001e2b",
        auto_correct=True,
    )
    assert report.valid is False
    assert len(report.errors) == 1
    assert "Edition" in report.errors[0]
    assert report.corrections_applied.get("edition") == "#cbd5e1"


def test_cover_footer_strip_invariants_and_preflight():
    """Verify footer strip exists, is 100% width, touches bottom, contains metadata, and passes contrast across all 10 styles."""
    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    for style_name in ALL_COVER_STYLES:
        plan = CoverDesignPlan(
            title="Systems Architecture & High-Scale Design",
            subtitle="Distributed Consensus, Storage Engines, and Query Optimization",
            category="Engineering",
            author="Vasuki AI",
            background_color="#f9fbfa",
            cover_style=style_name,
            cover_seed=777888,
        )

        # 1. 1600x2560 Source Artwork
        html_source = renderer.render_source_artwork(plan)
        assert '<footer class="cover-footer-strip"' in html_source
        assert 'width: 100%' in html_source
        assert 'bottom: 0' in html_source
        assert 'background-color: #001e2b' in html_source
        assert 'Vasuki AI' in html_source
        assert 'FIRST EDITION' in html_source

        # 2. A4 Page representation
        page_a4 = renderer.render_a4_cover_page(plan, book_id="test-footer-strip")
        assert '<footer class="cover-footer-strip"' in page_a4.html
        assert 'width: 100%' in page_a4.html
        assert 'bottom: 0' in page_a4.html
        assert 'background-color: #001e2b' in page_a4.html
        assert 'Vasuki AI' in page_a4.html
        assert 'FIRST EDITION' in page_a4.html

        # 3. Preflight Report flags
        report_source = CoverValidator.validate_cover(plan, html_source)
        assert report_source.valid is True
        assert report_source.footer_strip_exists is True
        assert report_source.footer_strip_full_width is True
        assert report_source.footer_strip_touches_bottom is True
        assert report_source.footer_metadata_inside_strip is True
        assert report_source.author_contrast_pass is True
        assert report_source.edition_contrast_pass is True
        assert report_source.no_metadata_over_artwork is True


def test_cover_footer_strip_preflight_catches_violations():
    """Verify CoverValidator catches missing footer strip, transparent background, or misplaced metadata."""
    plan = CoverDesignPlan(
        title="Testing Violations",
        author="Vasuki",
        background_color="#ffffff",
        cover_style="editorial_minimal",
    )

    # 1. Missing footer strip
    html_no_footer = '<div class="cover-canvas"><div class="cover-title-container"><h1 style="color:#fff;">Testing Violations</h1></div><div>Vasuki FIRST EDITION</div></div>'
    rep1 = CoverValidator.validate_cover(plan, html_no_footer)
    assert rep1.valid is False
    assert rep1.footer_strip_exists is False

    # 2. Transparent footer strip
    html_transparent = '<div class="cover-canvas"><div class="cover-title-container"><h1 style="color:#fff;">Testing Violations</h1></div><footer class="cover-footer-strip" style="width: 100%; bottom: 0; background-color: transparent;"><span style="color:#fff;">Vasuki</span><span style="color:#fff;">FIRST EDITION</span></footer></div>'
    rep2 = CoverValidator.validate_cover(plan, html_transparent)
    assert rep2.valid is False
    assert rep2.no_metadata_over_artwork is False

    # 3. Metadata outside strip
    html_misplaced_meta = '<div class="cover-canvas"><div class="cover-title-container"><h1 style="color:#fff;">Testing Violations</h1></div><span>Vasuki</span><footer class="cover-footer-strip" style="width: 100%; bottom: 0; background-color: #001e2b;"><span>Empty Footer</span></footer></div>'
    rep3 = CoverValidator.validate_cover(plan, html_misplaced_meta)
    assert rep3.valid is False
    assert rep3.footer_metadata_inside_strip is False


