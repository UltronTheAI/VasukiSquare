"""Unit tests for Book, Page, and Cover models and page linking contracts."""

import pytest
from vasukisquare.book.models import Book, Page, Cover, ChapterPlan, EditorialPlan
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme


def test_book_instantiation():
    book = Book(title="Quantum Computing", topic="Physics")
    assert book.id is not None
    assert book.title == "Quantum Computing"
    assert book.target_pages == 60


def test_page_chapter_opener_validation():
    # Valid chapter opener
    page = Page(
        book_id="b1",
        page_number=2,
        chapter_number=1,
        chapter_title="Introduction",
        layout_type=LayoutType.CHAPTER_OPENER,
        icon_name="book-open",
    )
    assert page.theme == Theme.DARK

    # Missing chapter title on chapter opener should fail
    with pytest.raises(ValueError):
        Page(
            book_id="b1",
            page_number=2,
            chapter_number=1,
            chapter_title=None,
            layout_type=LayoutType.CHAPTER_OPENER,
            icon_name="book-open",
        )

    # Missing icon on chapter opener should fail
    with pytest.raises(ValueError):
        Page(
            book_id="b1",
            page_number=2,
            chapter_number=1,
            chapter_title="Introduction",
            layout_type=LayoutType.CHAPTER_OPENER,
            icon_name=None,
        )


def test_page_linking_integrity(sample_pages):
    p1, p2, p3 = sample_pages
    assert p1.next_page_id == p2.id
    assert p2.previous_page_id == p1.id
    assert p2.next_page_id == p3.id
    assert p3.previous_page_id == p2.id


def test_cover_model():
    cover = Cover(
        book_id="b1",
        title="Deep Learning Systems",
    )
    assert cover.width == 1600
    assert cover.height == 2560
    assert cover.book_id == "b1"

