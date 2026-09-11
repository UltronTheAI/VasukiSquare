"""Rendering contract and regression fixture verification tests specified in TESTS.md."""

from pathlib import Path
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.renderer.overflow import OverflowDetector, PageRepairEngine, MAX_PAGE_CHARACTERS
from vasukisquare.book.models import Page, PageContent
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme
from tests.rendering.fixtures.snapshot_pages import (
    get_regression_fixture_pages,
    get_technical_component_fixture_pages,
)


def test_rendering_contract_a4_dimensions_and_css():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=1,
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.LIGHT,
        html="<p>Standard text page.</p>",
    )
    html = renderer.render_page(page)
    # Check page size A4 in CSS (210mm x 297mm) and @page rule
    assert "size: A4;" in html
    assert "margin: 0;" in html
    assert "210mm" in html
    assert "297mm" in html
    assert "class=\"page" in html
    assert "page-safe-content" in html


def test_rendering_semantic_text_contrast_tokens():
    renderer = HtmlPageRenderer()
    page_light = Page(
        book_id="b-render",
        page_number=2,
        chapter_number=2,
        chapter_name="Light Chapter",
        theme=Theme.LIGHT,
        html="<p>Light content</p>",
    )
    html_light = renderer.render_page(page_light)
    # Light theme contrast tokens
    assert "--text-primary: #001e2b;" in html_light
    assert "--text-secondary: #3d4f5b;" in html_light
    assert "--text-muted: #5c6c7a;" in html_light
    assert "--text-subtle: #7c8c9a;" in html_light

    page_dark = Page(
        book_id="b-render",
        page_number=1,
        chapter_number=1,
        chapter_name="Dark Chapter",
        theme=Theme.DARK,
        html="<p>Dark content</p>",
    )
    html_dark = renderer.render_page(page_dark)
    # Dark theme contrast tokens
    assert "--text-primary-dark: #ffffff;" in html_dark
    assert "--text-secondary-dark: #e1e5e8;" in html_dark
    assert "--text-muted-dark: #c1ccd6;" in html_dark
    assert "--text-subtle-dark: #a8b3bc;" in html_dark


def test_rendering_all_10_regression_fixtures():
    renderer = HtmlPageRenderer()
    fixtures = get_regression_fixture_pages()
    assert len(fixtures) == 10

    # Test full book assembly containing all 10 fixtures
    book_html = renderer.render_book(
        pages=fixtures,
        book_title="High Scalability Architecture",
        book_topic="Distributed Systems",
    )

    assert "<!DOCTYPE html>" in book_html
    assert "class=\"book-document\"" in book_html

    # Verify each fixture has rendered correctly inside book_html
    assert "layout-cover" in book_html
    assert "layout-copyright" in book_html
    assert "VasukiSquare AI" in book_html
    assert "layout-toc" in book_html
    assert "Table of Contents" in book_html
    assert "theme-dark layout-chapter_opener" in book_html
    assert "Deep Distributed Protocols" in book_html
    assert "theme-light layout-chapter_opener" in book_html
    assert "Modern Vector Indices" in book_html
    assert "Consensus State Machines" in book_html
    assert "append_entries" in book_html
    assert "HNSW" in book_html
    assert "layout-references" in book_html
    assert "Ongaro, D." in book_html or "understandable" in book_html.lower()
    assert "layout-thank_you" in book_html
    assert "Thank You for Reading" in book_html


def test_rendering_chapter_opener_centered_and_minimal():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=4,
        chapter_number=1,
        chapter_name="Neural Foundations and Core Concepts",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="cpu",
    )
    html = renderer.render_page(page)

    assert "Chapter 1" in html
    assert "Neural Foundations" in html
    assert "lucide-cpu" in html
    assert "chapter-opener-block" in html
    # Opener must be centered without body text
    assert "<p>" not in html


def test_rendering_all_14_technical_components():
    renderer = HtmlPageRenderer()
    components = get_technical_component_fixture_pages()
    assert len(components) == 14

    # 1. Light Editorial Page
    html_1 = renderer.render_page(components["light_editorial"])
    assert "theme-light" in html_1
    assert "Storage Engine Concurrency" in html_1
    assert "component-callout callout-note" in html_1

    # 2. Dark Editorial Page
    html_2 = renderer.render_page(components["dark_editorial"])
    assert "theme-dark" in html_2
    assert "Log Replication Protocol" in html_2
    assert "component-callout callout-important" in html_2

    # 3. Dark Opener
    html_3 = renderer.render_page(components["dark_chapter_opener"])
    assert "Chapter 1" in html_3
    assert "lucide-sparkles" in html_3

    # 4. Light Opener
    html_4 = renderer.render_page(components["light_chapter_opener"])
    assert "Chapter 2" in html_4
    assert "lucide-database" in html_4

    # 5. Python Code Block
    html_5 = renderer.render_page(components["python_code"])
    assert "component-code-block" in html_5
    assert "PYTHON" in html_5
    assert "consensus/rpc.py" in html_5
    assert "class" in html_5

    # 6. Rust Code Block
    html_6 = renderer.render_page(components["rust_code"])
    assert "component-code-block" in html_6
    assert "RUST" in html_6
    assert "storage/wal.rs" in html_6
    assert "WalRecord" in html_6

    # 7. Terminal Block
    html_7 = renderer.render_page(components["terminal"])
    assert "component-terminal-window" in html_7
    assert "terminal-prompt" in html_7
    assert "vasuki --start" in html_7

    # 8. Table Block
    html_8 = renderer.render_page(components["table"])
    assert "component-table" in html_8
    assert "Engine" in html_8
    assert "B-Tree" in html_8

    # 9. Source Links
    html_9 = renderer.render_page(components["source"])
    assert "component-source-card" in html_9
    assert "PostgreSQL WAL Architecture" in html_9
    assert "https://postgresql.org/docs/wal" in html_9

    # 10. Callout
    html_10 = renderer.render_page(components["callout"])
    assert "component-callout callout-important" in html_10
    assert "Safety Guarantee" in html_10

    # 11. Bar Chart
    html_11 = renderer.render_page(components["bar_chart"])
    assert "component-chart-container" in html_11
    assert "chart-svg" in html_11
    assert "Batch Size vs Ops/Sec" in html_11

    # 12. Line Chart
    html_12 = renderer.render_page(components["line_chart"])
    assert "component-chart-container" in html_12
    assert "chart-svg" in html_12
    assert "p99 Latency under Load" in html_12

    # 13. Mermaid Diagram
    html_13 = renderer.render_page(components["diagram"])
    assert "component-diagram-figure" in html_13
    assert "mermaid" in html_13
    assert "Write Path Architecture" in html_13

    # 14. Multi-Component Page
    html_14 = renderer.render_page(components["multi_component"])
    assert "component-code-block" in html_14
    assert "component-callout" in html_14
    assert "component-source-card" in html_14


def test_theme_alternation_contract():
    renderer = HtmlPageRenderer()
    p_odd = Page(
        book_id="b-render",
        page_number=10,
        chapter_number=1,
        chapter_name="Dark Chapter",
        layout=LayoutType.EDITORIAL.value,
    )
    assert p_odd.theme == Theme.DARK
    html_odd = renderer.render_page(p_odd)
    assert "theme-dark" in html_odd

    p_even = Page(
        book_id="b-render",
        page_number=20,
        chapter_number=2,
        chapter_name="Light Chapter",
        layout=LayoutType.EDITORIAL.value,
    )
    assert p_even.theme == Theme.LIGHT
    html_even = renderer.render_page(p_even)
    assert "theme-light" in html_even


def test_overflow_detection_and_repair():
    detector = OverflowDetector()
    repair_engine = PageRepairEngine(detector=detector)

    # Normal page: not overflowing
    normal_page = Page(
        book_id="b1",
        page_number=1,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(body="Short manageable paragraph that fits cleanly within A4 limits."),
    )
    assert detector.is_overflowing(normal_page) is False

    # Massive overflowing page (> MAX_PAGE_CHARACTERS)
    huge_text = "This is an extensive technical dissertation on asynchronous IO event loops and kernel epoll implementations. " * 40
    overflow_page = Page(
        book_id="b1",
        page_number=2,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(headline="Async Internals", body=huge_text),
    )
    assert detector.is_overflowing(overflow_page) is True

    # Run controlled repair
    repaired = repair_engine.repair_pages([normal_page, overflow_page])

    # Should have split into 3 pages (Page 1 normal, Page 2 first part, Page 3 continuation)
    assert len(repaired) == 3
    assert repaired[0].page_number == 1
    assert repaired[1].page_number == 2
    assert repaired[2].page_number == 3
    assert repaired[1].next_page_id == repaired[2].id
    assert repaired[2].previous_page_id == repaired[1].id
    assert "Cont." in repaired[2].content.headline


def test_lucide_svg_loaded_in_html():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b1",
        page_number=1,
        chapter_number=1,
        chapter_name="Introduction",
        layout=LayoutType.CHAPTER_OPENER.value,
        icon="sparkles",
    )
    html = renderer.render_page(page)
    assert "<svg xmlns=\"http://www.w3.org/2000/svg\"" in html
    assert "lucide-sparkles" in html
    assert "stroke=\"#00ed64\"" in html  # Brand green token in dark chapter
