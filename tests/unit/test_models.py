"""Unit tests for Book, ChapterMetadata, Page, PageContent, PageStyle, SourceCitation, and Cover models."""

from vasukisquare.book.models import (
    Book,
    ChapterMetadata,
    Page,
    PageContent,
    PageStyle,
    SourceCitation,
    Cover,
)
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme


def test_book_instantiation_and_slug():
    book = Book(
        title="Quantum Computing Systems",
        prompt="Explain quantum mechanics and algorithms",
        description="A comprehensive introduction.",
    )
    assert book.id is not None
    assert book.slug == "quantum-computing-systems"
    assert book.title == "Quantum Computing Systems"
    assert book.status == "draft"
    assert book.chapter_count == 0
    assert book.page_count == 0


def test_chapter_metadata_theme_assignment():
    c1 = ChapterMetadata(chapter_number=1, title="Introduction to Qubits")
    c2 = ChapterMetadata(chapter_number=2, title="Superposition and Entanglement")
    assert c1.theme == Theme.DARK
    assert c2.theme == Theme.LIGHT


def test_page_full_schema():
    citation = SourceCitation(
        url="https://arxiv.org/abs/quant-ph/9508027",
        title="Polynomial-Time Algorithms for Prime Factorization and Discrete Logarithms on a Quantum Computer",
        claim="Shor algorithm provides exponential speedup.",
        page_number=1,
    )
    content = PageContent(
        headline="Shor's Algorithm Breakdown",
        body="Peter Shor developed a polynomial time algorithm...",
        key_points=["Quantum Fourier Transform", "Period Finding"],
        code_snippets=[{"language": "python", "code": "def qft(): pass"}],
        callouts=[{"title": "Warning", "body": "Requires fault tolerant qubits"}],
    )
    style = PageStyle(
        theme=Theme.DARK,
        font_family="Euclid Circular A",
        accent_color="#00ed64",
    )
    page = Page(
        book_id="b1",
        page_number=2,
        page_type=LayoutType.CHAPTER_OPENER.value,
        chapter_number=1,
        chapter_name="Introduction to Quantum Algorithms",
        layout=LayoutType.CHAPTER_OPENER.value,
        icon="sparkles",
        content=content,
        style=style,
        sources=[citation],
        html="<div>Chapter 1</div>",
        validation={"status": "valid"},
    )

    assert page.book_id == "b1"
    assert page.page_number == 2
    assert page.theme == Theme.DARK
    assert page.icon == "sparkles"
    assert len(page.sources) == 1
    assert page.sources[0].url == "https://arxiv.org/abs/quant-ph/9508027"
    assert len(page.content.key_points) == 2


def test_cover_full_schema():
    cover = Cover(
        book_id="b1",
        width=1600,
        height=2560,
        title="Quantum Computing Systems",
        design={"palette": "brand-dark", "layout": "hero"},
        html="<div>Cover HTML</div>",
        image_path="output/covers/cover-1.png",
    )
    assert cover.book_id == "b1"
    assert cover.width == 1600
    assert cover.height == 2560
    assert cover.title == "Quantum Computing Systems"
    assert cover.image_path == "output/covers/cover-1.png"
