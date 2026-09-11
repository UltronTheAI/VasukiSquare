"""Rendering contract verification tests specified in TESTS.md."""

from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.book.models import Page
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme


def test_rendering_contract_a4_dimensions():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=1,
        layout=LayoutType.TEXT_HEAVY.value,
        theme=Theme.LIGHT,
        html="<p>Standard text page.</p>",
    )
    html = renderer.render_page(page)
    # Check page size A4 in CSS (210mm x 297mm)
    assert "210mm" in html
    assert "297mm" in html


def test_rendering_contract_chapter_opener():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=5,
        chapter_number=1,
        chapter_name="Neural Foundations",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="cpu",
    )
    html = renderer.render_page(page)

    # Must contain chapter number, title, and Lucide SVG
    assert "Chapter 1" in html
    assert "Neural Foundations" in html
    assert "lucide-cpu" in html
    # Chapter opener should not have arbitrary header/body paragraph text
    assert "<p>" not in html


def test_rendering_contract_theme_alternation():
    renderer = HtmlPageRenderer()
    # Chapter 1 (odd) -> dark
    p_odd = Page(
        book_id="b-render",
        page_number=10,
        chapter_number=1,
        chapter_name="Dark Chapter",
        layout=LayoutType.TEXT_HEAVY.value,
    )
    assert p_odd.theme == Theme.DARK
    html_odd = renderer.render_page(p_odd)
    assert "theme-dark" in html_odd

    # Chapter 2 (even) -> light
    p_even = Page(
        book_id="b-render",
        page_number=20,
        chapter_number=2,
        chapter_name="Light Chapter",
        layout=LayoutType.TEXT_HEAVY.value,
    )
    assert p_even.theme == Theme.LIGHT
    html_even = renderer.render_page(p_even)
    assert "theme-light" in html_even


def test_rendering_contract_page_number_and_chapter_identification():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=42,
        chapter_number=3,
        chapter_name="Distributed Systems",
        layout=LayoutType.TEXT_HEAVY.value,
        html="<p>Consensus protocols guarantee safety.</p>",
    )
    html = renderer.render_page(page, book_title="High Scalability")

    # Header must identify chapter
    assert "Chapter 3: Distributed Systems" in html
    # Footer must contain page number
    assert '<span class="footer-page-num">42</span>' in html
