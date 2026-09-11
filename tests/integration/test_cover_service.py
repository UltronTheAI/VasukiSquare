"""Integration tests for cover rendering, MongoDB persistence, and Book linking."""

import asyncio
from unittest.mock import MagicMock
import pytest
from vasukisquare.book.models import Book, Cover, CoverPlan
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.tokens import ColorToken
from vasukisquare.database.repository import BookRepository, CoverRepository
from vasukisquare.renderer.cover import CoverRenderer, CoverService


def test_cover_renderer_source_artwork_and_a4_page():
    renderer = CoverRenderer()
    plan = CoverPlan(
        title="Distributed Consensus and Raft",
        subtitle="Leader Election and Log Replication",
        category="Distributed Systems",
        layout_style="orbital_rings",
        hero_icon="sparkles",
        accent_color=ColorToken.BRAND_GREEN.value,
        background_color=ColorToken.BRAND_TEAL_DEEP.value,
    )

    # 1. 1600x2560 Source Artwork
    artwork_html = renderer.render_source_artwork(plan)
    assert "1600px" in artwork_html
    assert "2560px" in artwork_html
    assert "safe-content-area" in artwork_html
    assert "Distributed Consensus and Raft" in artwork_html
    assert "lucide-sparkles" in artwork_html
    assert "#00ed64" in artwork_html

    # 2. A4 Adapted Page
    a4_page = renderer.render_a4_cover_page(plan, book_id="book-test-123")
    assert a4_page.page_number == 1
    assert a4_page.layout_type == LayoutType.COVER
    assert "Distributed Consensus and Raft" in a4_page.html
    assert "VASUKISQUARE" in a4_page.html


def test_cover_service_persistence_and_book_linking():
    # Setup mock database
    mock_db = MagicMock()
    store_books = {}
    store_covers = {}

    def book_insert(doc):
        store_books[doc["_id"]] = dict(doc)
        return MagicMock()

    def book_find(query):
        return store_books.get(query.get("_id"))

    def book_update(filter_dict, update_dict):
        bid = filter_dict.get("_id")
        if bid in store_books and "$set" in update_dict:
            store_books[bid].update(update_dict["$set"])
        return MagicMock(modified_count=1)

    def cover_insert(doc):
        store_covers[doc["_id"]] = dict(doc)
        return MagicMock()

    def cover_find(query):
        if "_id" in query:
            return store_covers.get(query["_id"])
        if "book_id" in query:
            for c in store_covers.values():
                if c.get("book_id") == query["book_id"]:
                    return c
        return None

    mock_books_coll = MagicMock()
    mock_books_coll.insert_one.side_effect = book_insert
    mock_books_coll.find_one.side_effect = book_find
    mock_books_coll.update_one.side_effect = book_update

    mock_covers_coll = MagicMock()
    mock_covers_coll.insert_one.side_effect = cover_insert
    mock_covers_coll.find_one.side_effect = cover_find

    mock_db.__getitem__.side_effect = lambda name: mock_books_coll if name == "books" else mock_covers_coll

    book_repo = BookRepository(mock_db)
    cover_repo = CoverRepository(mock_db)

    # 1. Create a Book
    book = Book(
        id="book-ai-systems",
        title="Scalable AI Systems",
        subtitle="Designing Production Pipelines",
    )
    book_repo.create(book)

    # 2. Plan and persist Cover
    plan = CoverPlan(
        title=book.title,
        subtitle=book.subtitle,
        category="Artificial Intelligence",
        layout_style="abstract_mesh",
        hero_icon="cpu",
    )

    service = CoverService(
        cover_repo=cover_repo,
        book_repo=book_repo,
    )

    async def _test():
        persisted_cover = await service.generate_and_persist_cover(
            book_id=book.id,
            plan=plan,
            save_raster_image=False,
        )

        assert persisted_cover.book_id == book.id
        assert persisted_cover.width == 1600
        assert persisted_cover.height == 2560
        assert persisted_cover.title == "Scalable AI Systems"

        # Verify Cover exists in MongoDB
        retrieved_cover = cover_repo.get_by_book_id(book.id)
        assert retrieved_cover is not None
        assert retrieved_cover.id == persisted_cover.id

        # Verify Book.cover_id is updated in MongoDB
        updated_book = book_repo.get_by_id(book.id)
        assert updated_book is not None
        assert updated_book.cover_id == persisted_cover.id

    asyncio.run(_test())

