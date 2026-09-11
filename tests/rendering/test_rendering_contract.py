"""Rendering contract and regression fixture verification tests specified in TESTS.md."""

import asyncio
from pathlib import Path
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.renderer.overflow import OverflowDetector, PageRepairEngine, MAX_PAGE_CHARACTERS
from vasukisquare.book.models import Page, PageContent
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme
from tests.rendering.fixtures.snapshot_pages import get_regression_fixture_pages


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
    # 1. Cover
    assert "layout-cover" in book_html
    # 2. Copyright
    assert "layout-copyright" in book_html
    assert "VasukiSquare AI" in book_html
    # 3. TOC
    assert "layout-toc" in book_html
    assert "Table of Contents" in book_html
    # 4. Dark Opener (Odd chapter: 1)
    assert "theme-dark layout-chapter_opener" in book_html
    assert "Deep Distributed Protocols" in book_html
    # 5. Light Opener (Even chapter: 2)
    assert "theme-light layout-chapter_opener" in book_html
    assert "Modern Vector Indices" in book_html
    # 6. Text-Heavy
    assert "Consensus State Machines" in book_html
    # 7. Code Page
    assert "append_entries" in book_html
    # 8. Comparison Page
    assert "HNSW vs IVF-PQ" in book_html
    # 9. References Page
    assert "layout-references" in book_html
    assert "Ongaro, D." in book_html
    # 10. Thank You Page
    assert "layout-thank_you" in book_html
    assert "Thank You for Reading" in book_html


def test_rendering_chapter_opener_strict_minimal():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=4,
        chapter_number=1,
        chapter_name="Neural Foundations",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="cpu",
    )
    html = renderer.render_page(page)

    assert "Chapter 1" in html
    assert "Neural Foundations" in html
    assert "lucide-cpu" in html
    # Chapter opener should not have arbitrary body paragraph text
    assert "<p>" not in html


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
