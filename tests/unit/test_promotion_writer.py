"""Unit tests for PromotionWriter AI article generation."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from vasukisquare.book.models import Book, ChapterMetadata, DiscoveryInfo
from vasukisquare.config import Settings
from vasukisquare.llm.client import LLMClient
from vasukisquare.promotion.models import GeneratedArticleContent, PromotionStatus
from vasukisquare.promotion.writer import PromotionWriter


@pytest.fixture
def sample_book():
    return Book(
        id="book-99",
        slug="advanced-postgresql-internals",
        title="Advanced PostgreSQL Internals",
        subtitle="MVCC, WAL, and Query Optimization",
        category="Databases",
        target_audience="Database Administrators & Backend Engineers",
        technical_depth="Advanced",
        description="A deep exploration of storage engines, page layout, and write-ahead logging.",
        chapters=[
            ChapterMetadata(chapter_number=1, title="Storage Engine & Slotted Pages", summary="Page layouts on disk"),
            ChapterMetadata(chapter_number=2, title="MVCC and Vacuuming", summary="Multi-version concurrency control"),
        ],
        discovery=DiscoveryInfo(keywords=["postgresql", "database", "internals", "sql"]),
    )


@pytest.mark.asyncio
async def test_writer_canonical_url_construction():
    settings = Settings(publication_base_url="https://vasukisquare.cc")
    writer = PromotionWriter(settings=settings)
    assert writer.build_canonical_url("my-slug") == "https://vasukisquare.cc/book/my-slug"
    assert writer.build_canonical_url("/my-slug/") == "https://vasukisquare.cc/book/my-slug/"


@pytest.mark.asyncio
async def test_writer_generate_article_success(sample_book):
    settings = Settings(publication_base_url="https://vasukisquare.cc")
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.active_model = "llama-3.3-70b-versatile"
    
    mock_content = GeneratedArticleContent(
        title="How PostgreSQL Implements MVCC and Heap Tuples",
        body_markdown="# PostgreSQL MVCC\n\nIn PostgreSQL, tuples are appended rather than mutated in-place.\n\n[Read the full ebook](https://vasukisquare.cc/book/advanced-postgresql-internals)",
        tags=["#PostgreSQL", "database", "backend", "systems", "extra-tag"],
    )
    mock_llm.invoke_structured = AsyncMock(return_value=mock_content)

    writer = PromotionWriter(settings=settings, llm_client=mock_llm)
    post = await writer.generate_article(
        book=sample_book,
        campaign_run_id="camp_100",
        platform="devto",
    )

    assert post.title == "How PostgreSQL Implements MVCC and Heap Tuples"
    assert "https://vasukisquare.cc/book/advanced-postgresql-internals" in post.body_markdown
    assert post.status == PromotionStatus.GENERATED
    assert post.book_id == "book-99"
    assert post.book_slug == "advanced-postgresql-internals"
    assert len(post.tags) == 4
    assert post.tags[0] == "postgresql"
    assert post.generation_model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_writer_appends_missing_canonical_url(sample_book):
    settings = Settings(publication_base_url="https://vasukisquare.cc")
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.active_model = "gpt-oss-120b"
    
    # LLM omitted the canonical URL
    mock_content = GeneratedArticleContent(
        title="PostgreSQL Storage Layouts",
        body_markdown="# PostgreSQL Storage\n\nPages are 8KB blocks composed of page headers and linp item pointers.",
        tags=["postgres", "sql"],
    )
    mock_llm.invoke_structured = AsyncMock(return_value=mock_content)

    writer = PromotionWriter(settings=settings, llm_client=mock_llm)
    post = await writer.generate_article(
        book=sample_book,
        campaign_run_id="camp_200",
        platform="devto",
    )

    assert post.title == "PostgreSQL Storage Layouts"
    # Canonical link should have been appended automatically
    assert "https://vasukisquare.cc/book/advanced-postgresql-internals" in post.body_markdown
    assert "Further Reading" in post.body_markdown

