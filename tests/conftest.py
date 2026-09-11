"""Pytest fixtures for VasukiSquare unit and integration tests."""

import pytest
from vasukisquare.config import Settings
from vasukisquare.book.models import Book, Page, Cover
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing test configuration."""
    return Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="vasukisquare_test",
        groq_model="llama-3.3-70b-versatile",
    )


@pytest.fixture
def sample_book() -> Book:
    """Fixture providing a sample book."""
    return Book(
        id="book-123",
        title="Introduction to Modern AI",
        subtitle="Architecture and Practical Applications",
        prompt="Explain modern AI architectures",
        description="Artificial Intelligence and Transformers",
        page_count=60,
    )


@pytest.fixture
def sample_pages(sample_book: Book) -> list[Page]:
    """Fixture providing a series of linked pages."""
    p1 = Page(
        id="page-1",
        book_id=sample_book.id,
        page_number=1,
        page_type=LayoutType.COVER.value,
        layout=LayoutType.COVER.value,
        theme=Theme.LIGHT,
    )
    p2 = Page(
        id="page-2",
        book_id=sample_book.id,
        page_number=2,
        page_type=LayoutType.CHAPTER_OPENER.value,
        chapter_number=1,
        chapter_name="The Genesis of Neural Networks",
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="sparkles",
        previous_page_id="page-1",
    )
    p3 = Page(
        id="page-3",
        book_id=sample_book.id,
        page_number=3,
        page_type=LayoutType.TEXT_HEAVY.value,
        chapter_number=1,
        chapter_name="The Genesis of Neural Networks",
        layout=LayoutType.TEXT_HEAVY.value,
        theme=Theme.DARK,
        html="<p>Neural networks were inspired by the human brain...</p>",
        previous_page_id="page-2",
    )
    p1.next_page_id = "page-2"
    p2.next_page_id = "page-3"
    return [p1, p2, p3]


@pytest.fixture
def sample_cover(sample_book: Book) -> Cover:
    """Fixture providing sample cover."""
    return Cover(
        id="cover-123",
        book_id=sample_book.id,
        title=sample_book.title,
        design={"subtitle": sample_book.subtitle},
    )
