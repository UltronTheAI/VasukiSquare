"""Verification tests for cover placement, full-bleed A4 dimensions, and frontmatter ordering."""

import pytest
from vasukisquare.config import Settings
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import (
    CoverPlan,
    Page,
    PageContent,
    generate_id,
)
from vasukisquare.design.theme import Theme
from vasukisquare.renderer.cover import CoverRenderer
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.pipeline.orchestrator import EbookGenerationPipeline


@pytest.fixture
def sample_cover_plan() -> CoverPlan:
    return CoverPlan(
        title="LioranDB for Noobs",
        subtitle="From Zero Knowledge to Building Real Apps with LioranDB",
        category="Database Architecture",
        tone="authoritative",
        audience="Software Engineers",
        accent_color="#00ed64",
        background_color="#001e2b",
        layout_style="geometric",
        hero_icon="database",
        author="VasukiSquare AI Systems",
    )


@pytest.fixture
def sample_book_pages(sample_cover_plan) -> list[Page]:
    renderer = CoverRenderer()
    book_id = "test-liorandb"
    cover_page = renderer.render_a4_cover_page(sample_cover_plan, book_id=book_id)

    title_page = Page(
        id=generate_id(),
        book_id=book_id,
        page_number=2,
        page_type="imprint",
        layout="imprint",
        theme=Theme.LIGHT,
        content=PageContent(
            headline="LioranDB for Noobs",
            body="From Zero Knowledge to Building Real Apps with LioranDB",
        ),
    )

    copyright_page = Page(
        id=generate_id(),
        book_id=book_id,
        page_number=3,
        page_type=LayoutType.COPYRIGHT.value,
        layout=LayoutType.COPYRIGHT.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Copyright & Publishing Notice",
            body="Copyright © 2026 VasukiSquare. All rights reserved.",
        ),
    )

    toc_page = Page(
        id=generate_id(),
        book_id=book_id,
        page_number=4,
        page_type=LayoutType.TOC.value,
        layout=LayoutType.TOC.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Table of Contents",
            key_points=["Chapter 1: Foundations", "Chapter 2: Query Engine"],
        ),
    )

    ch1_opener = Page(
        id=generate_id(),
        book_id=book_id,
        page_number=5,
        chapter_number=1,
        chapter_name="Foundations and Storage Primitives",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="cpu",
    )

    return [cover_page, title_page, copyright_page, toc_page, ch1_opener]


def test_cover_is_first_physical_page_and_correct_order(sample_book_pages):
    renderer = HtmlPageRenderer()
    book_html = renderer.render_book(
        pages=sample_book_pages,
        book_title="LioranDB for Noobs",
    )

    # 1. Cover is first physical page
    assert sample_book_pages[0].page_type == LayoutType.COVER.value
    assert sample_book_pages[0].layout == LayoutType.COVER.value

    # 2. Sequence check in rendered HTML body
    body_html = book_html.split("<body", 1)[1] if "<body" in book_html else book_html

    cover_idx = body_html.find("layout-cover")
    imprint_idx = body_html.find("layout-imprint")
    copyright_idx = body_html.find("layout-copyright")
    toc_idx = body_html.find("layout-toc")
    opener_idx = body_html.find("layout-chapter_opener")

    assert cover_idx != -1, "Cover must be present in HTML body"
    assert imprint_idx != -1, "Title/Imprint page must be present in HTML body"
    assert copyright_idx != -1, "Copyright page must be present in HTML body"
    assert toc_idx != -1, "TOC page must be present in HTML body"
    assert opener_idx != -1, "Chapter opener must be present in HTML body"

    # Verify strict monotonic ordering: Cover -> Title -> Copyright -> TOC -> Chapters
    assert cover_idx < imprint_idx < copyright_idx < toc_idx < opener_idx


def test_cover_has_no_running_header_footer_or_page_number(sample_cover_plan):
    renderer = CoverRenderer()
    html_renderer = HtmlPageRenderer()
    cover_page = renderer.render_a4_cover_page(sample_cover_plan, book_id="b1")
    single_html = html_renderer.render_page(cover_page, book_title="LioranDB for Noobs")

    # Cover must not have visible running header or footer chrome
    assert "<header class=\"page-header\"" not in single_html
    assert "<footer class=\"page-footer\"" not in single_html
    assert "class=\"footer-page-num\"" not in single_html


def test_cover_full_bleed_a4_css(sample_cover_plan):
    renderer = CoverRenderer()
    cover_page = renderer.render_a4_cover_page(sample_cover_plan, book_id="b1")
    assert "cover-hero" in cover_page.html
    assert "cover-hero-solid" in cover_page.html
    assert "297mm" in cover_page.html or "100%" in cover_page.html

    html_renderer = HtmlPageRenderer()
    rendered_css = html_renderer._get_css()
    assert ".page.layout-cover" in rendered_css
    assert "padding: 0 !important;" in rendered_css
    assert "margin: 0 !important;" in rendered_css


def test_cover_is_not_rendered_twice(sample_book_pages):
    renderer = HtmlPageRenderer()
    book_html = renderer.render_book(
        pages=sample_book_pages,
        book_title="LioranDB for Noobs",
    )
    # Count occurrences of layout-cover container in the HTML body
    body_html = book_html.split("<body", 1)[1] if "<body" in book_html else book_html
    cover_count = body_html.count("layout-cover")
    assert cover_count == 1, f"Expected exactly 1 cover page in body, found {cover_count}"



def test_title_page_exists_separately_after_cover(sample_book_pages):
    assert len(sample_book_pages) >= 2
    p1 = sample_book_pages[0]
    p2 = sample_book_pages[1]

    assert p1.layout == LayoutType.COVER.value
    assert p2.layout in ("imprint", "title", LayoutType.TEXT_HEAVY.value, LayoutType.EDITORIAL.value)
    assert p2.page_number == 2


@pytest.mark.asyncio
async def test_missing_cover_fails_clearly():
    # Attempting to plan or run pipeline without valid cover raises RuntimeError
    class BrokenCoverAgent:
        async def plan_cover(self, *args, **kwargs):
            return None

    settings = Settings(_env_file=None, vasukisquare_mock_mode=True)
    pipeline = EbookGenerationPipeline(settings=settings, cover_agent=BrokenCoverAgent())
    with pytest.raises(RuntimeError, match="Book cover is missing or failed to render."):
        await pipeline.run("LioranDB for Noobs", target_pages=10, persist_db=False, generate_pdf=False)


def test_final_page_count_includes_cover(sample_book_pages):
    renderer = HtmlPageRenderer()
    book_html = renderer.render_book(
        pages=sample_book_pages,
        book_title="LioranDB for Noobs",
    )
    # Number of .page elements should match exactly len(sample_book_pages)
    page_container_count = book_html.count("class=\"page ")
    assert page_container_count == len(sample_book_pages)
    assert page_container_count == 5


def test_all_composition_styles_render_cleanly():
    """3. Verify CoverRenderer supports and renders all composition families cleanly."""
    renderer = CoverRenderer()
    styles = [
        "asymmetric_left",
        "centered_editorial",
        "framed_technical",
        "dense_blueprint",
        "large_typography",
        "bottom_weighted",
        "vertical_split",
        "typography_only",
        "icon_led",
        "abstract_lines",
        "diagonal_accent",
        "geometric_grid",
    ]

    for s in styles:
        plan = CoverPlan(
            title="Modern Key-Value Storage Architecture",
            subtitle="Storage Engines, Compaction, and Query Execution",
            category="Database Systems",
            composition_style=s,
            accent_color="#00ed64",
            background_color="#001e2b",
            hero_icon="database" if s != "typography_only" else None,
            icon_strategy="none" if s == "typography_only" else "hero_top",
            decorative_geometry="database_nodes",
        )
        page = renderer.render_a4_cover_page(plan, book_id="test-book")
        assert page.page_number == 1
        assert page.page_type == LayoutType.COVER.value
        assert len(page.html) > 100
        assert "cover-hero" in page.html
        assert "Modern Key-Value Storage Architecture" in page.html


def test_long_title_dynamic_typography_scaling():
    """4. Verify long titles dynamically scale font size to avoid overflow."""
    renderer = CoverRenderer()
    long_title = "LioranDB for Noobs: From Zero Knowledge to Building Real Production Cloud Applications with LioranDB and Modern Microservices"
    plan = CoverPlan(
        title=long_title,
        subtitle="A Comprehensive Guide",
        category="Distributed Systems",
        composition_style="asymmetric_left",
        accent_color="#00ed64",
        background_color="#001e2b",
    )
    page = renderer.render_a4_cover_page(plan, book_id="test-book")
    assert "font-size: 26px" in page.html or "font-size: 30px" in page.html
    assert "font-size:" in page.html
    assert "word-break: break-word" in page.html

