"""Comprehensive tests for the 10 Cover Style families, gallery QA, deterministic reproduction, and brand label removal."""

import shutil
import tempfile
from pathlib import Path

from vasukisquare.book.models import BookIntent, CoverDesignPlan
from vasukisquare.cover.planner import CoverPlannerAgent
from vasukisquare.cover.primitives import (
    generate_abstract_geometric,
    generate_botanical_foliage,
    generate_cinematic_landscape,
    generate_editorial_minimal,
    generate_mountain_scenery,
    generate_ocean_horizon,
    generate_sky_clouds,
    generate_symbolic_object,
    generate_terrain_journey,
    generate_typographic_poster_accents,
)
from vasukisquare.cover.renderer import CoverRenderer, render_cover_gallery
from vasukisquare.cover.styles import ALL_COVER_STYLES, CoverStyle, get_style_weights_for_topic
from vasukisquare.cover.validator import CoverValidator


def test_ten_cover_styles_enumeration():
    """Verify that all 10 distinct cover style families exist and are enumerated."""
    assert len(ALL_COVER_STYLES) == 10
    expected = [
        "editorial_minimal",
        "mountain_landscape",
        "ocean_horizon",
        "sky_clouds",
        "abstract_geometric",
        "typographic_poster",
        "botanical_organic",
        "terrain_journey",
        "symbolic_object",
        "cinematic_landscape",
    ]
    for s in expected:
        assert s in ALL_COVER_STYLES


def test_topic_compatibility_weighting():
    """Verify topic-compatibility weighting favors suitable styles for lifestyle vs technical books."""
    # Lifestyle/Habit book
    intent_habit = BookIntent(topic="How to Build Better Daily Habits", book_type="practical_guide", is_technical=False)
    weights_habit = get_style_weights_for_topic("How to Build Better Daily Habits", intent_habit)
    assert weights_habit[CoverStyle.TERRAIN_JOURNEY.value] > weights_habit[CoverStyle.ABSTRACT_GEOMETRIC.value]
    assert weights_habit[CoverStyle.EDITORIAL_MINIMAL.value] >= 2.0

    # Technical/Programming book
    intent_tech = BookIntent(topic="Getting Started with Python", book_type="handbook", is_technical=True)
    weights_tech = get_style_weights_for_topic("Getting Started with Python", intent_tech)
    assert weights_tech[CoverStyle.ABSTRACT_GEOMETRIC.value] > weights_tech[CoverStyle.BOTANICAL_ORGANIC.value]
    assert weights_tech[CoverStyle.SYMBOLIC_OBJECT.value] >= 2.5


def test_all_ten_vector_primitives_render_valid_svg():
    """Verify each of the 10 procedural vector scenery generators produces valid non-empty SVG markup."""
    import random
    rng = random.Random(42)
    canvas = (1600, 2560)
    colors = {"bg": "#faf8f5"}

    svg_funcs = [
        generate_editorial_minimal,
        generate_mountain_scenery,
        generate_ocean_horizon,
        generate_sky_clouds,
        generate_abstract_geometric,
        generate_typographic_poster_accents,
        generate_botanical_foliage,
        generate_terrain_journey,
        lambda r, c, col: generate_symbolic_object(r, "habit_loop", c, col),
        generate_cinematic_landscape,
    ]

    for fn in svg_funcs:
        svg = fn(rng, canvas, colors)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert len(svg) > 100


def test_render_all_ten_styles_source_and_a4():
    """Verify CoverRenderer renders both 1600x2560 standalone HTML and A4 Page for all 10 families."""
    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    for style_name in ALL_COVER_STYLES:
        plan = planner.plan_cover(
            title="How to Build Better Daily Habits",
            subtitle="A Practical Guide to Lasting Change",
            category="Personal Development",
            seed=12345,
            style_override=style_name,
            author="Vasuki",
        )
        assert plan.author == "Vasuki"
        assert plan.cover_style == style_name

        # 1. 1600x2560 standalone artwork HTML
        artwork_html = renderer.render_source_artwork(plan)
        assert len(artwork_html) > 500
        assert "How to Build Better Daily Habits" in artwork_html
        assert "Vasuki" in artwork_html
        # Verify generic VASUKISQUARE top-left label is removed
        assert '<span class="cover-brand-label">VASUKISQUARE</span>' not in artwork_html

        # 2. A4 printable page
        a4_page = renderer.render_a4_cover_page(plan, book_id="habits-book")
        assert a4_page.page_number == 1
        assert a4_page.page_type == "cover"
        assert "How to Build Better Daily Habits" in a4_page.html
        assert "Vasuki" in a4_page.html
        assert '<span class="cover-brand-label">VASUKISQUARE</span>' not in a4_page.html

        # 3. Preflight Validator
        report = CoverValidator.validate_cover(plan, artwork_html)
        assert report.valid is True
        assert len(report.errors) == 0


def test_seeded_determinism_reproduction():
    """Verify that using the same cover seed produces 100% identical vector & HTML artwork."""
    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    plan1 = planner.plan_cover(
        title="Mastering Rust Concurrency",
        subtitle="Thread Safety, Channels, and Async Runtimes",
        category="Software Engineering",
        seed=884920,
    )
    html1 = renderer.render_source_artwork(plan1)

    plan2 = planner.plan_cover(
        title="Mastering Rust Concurrency",
        subtitle="Thread Safety, Channels, and Async Runtimes",
        category="Software Engineering",
        seed=884920,
    )
    html2 = renderer.render_source_artwork(plan2)

    assert plan1.cover_style == plan2.cover_style
    assert plan1.background_color == plan2.background_color
    assert html1 == html2


def test_cover_gallery_generator():
    """Verify render_cover_gallery creates 10 distinct HTML files in output directory for QA."""
    temp_dir = Path(tempfile.mkdtemp(prefix="cover_gallery_test_"))
    try:
        files = render_cover_gallery(
            topic="How to Build Better Daily Habits",
            output_dir=temp_dir,
        )
        assert len(files) == 10
        for f in files:
            assert f.exists()
            content = f.read_text(encoding="utf-8")
            assert "How to Build Better Daily Habits" in content
            assert "Vasuki" in content
            assert "cover-title-container" in content
            assert "#001e2b" in content
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_title_container_supports_short_and_long_multiline_titles():
    """Verify title container automatically handles short, long, multiline titles and subtitles."""
    planner = CoverPlannerAgent()
    renderer = CoverRenderer()

    test_cases = [
        # Short title
        ("Focus", "The Art of Doing One Thing", "editorial_minimal", "center"),
        # Standard title (Good Habits)
        ("Good Habits", "A Practical, Step-by-Step Guide to Lasting Change", "symbolic_object", "left"),
        # Long multiline title
        ("Architecting High-Throughput Distributed Streaming Systems", "An Advanced Guide to Storage Engines, Compaction, Replicated Logs, and Low-Latency Query Execution", "abstract_geometric", "left"),
        # Multiline title with short subtitle
        ("Modern\nData Architecture", "Practical Guide", "mountain_landscape", "center"),
    ]

    for title, subtitle, style, align in test_cases:
        plan = CoverDesignPlan(
            title=title,
            subtitle=subtitle,
            category="Engineering",
            author="Vasuki AI",
            background_color="#f9fbfa",
            cover_style=style,
            title_alignment=align,
            cover_seed=999,
        )

        artwork_html = renderer.render_source_artwork(plan)
        assert "cover-title-container" in artwork_html
        assert "background-color: #001e2b" in artwork_html
        assert "z-index: 10" in artwork_html
        assert "color: #ffffff" in artwork_html

        a4_page = renderer.render_a4_cover_page(plan, book_id="test-scaling")
        assert "cover-title-container" in a4_page.html
        assert "background-color: #001e2b" in a4_page.html
        assert "color: #ffffff" in a4_page.html

        report = CoverValidator.validate_cover(plan, artwork_html)
        assert report.valid is True
        assert len(report.errors) == 0


