"""Integration tests for HTML rendering and template generation."""

from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.book.models import Page
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme


def test_html_renderer_chapter_opener():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="book-100",
        page_number=1,
        chapter_number=1,
        chapter_name="Getting Started with VasukiSquare",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="sparkles",
    )

    html = renderer.render_page(page, book_title="VasukiSquare Guide", book_topic="Engineering")

    assert "<!DOCTYPE html>" in html
    assert "theme-dark" in html
    assert "layout-chapter_opener" in html
    assert "Getting Started with VasukiSquare" in html
    assert "Chapter 1" in html
    assert "lucide-sparkles" in html
    assert "210mm" in html  # Verify A4 styling presence in embedded CSS
    assert "297mm" in html


def test_html_renderer_content_page():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="book-100",
        page_number=2,
        chapter_number=2,
        chapter_name="Core Architecture",
        page_type=LayoutType.EDITORIAL.value,
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.LIGHT,
        html="<p>VasukiSquare generates deterministic documents.</p>",
    )

    html = renderer.render_page(page, book_title="VasukiSquare Guide", book_topic="Engineering")

    assert "theme-light" in html
    assert "layout-editorial" in html
    assert "VasukiSquare generates deterministic documents." in html
    assert "Chapter 2: Core Architecture" in html
    assert "2" in html  # page number in footer
