"""Integration tests for database persistence, index initialization, and page linking graphs."""

import pytest
from unittest.mock import MagicMock
from pymongo.errors import PyMongoError
from vasukisquare.book.models import (
    Book,
    ChapterMetadata,
    Page,
    PageContent,
    PageStyle,
    Cover,
)
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme
from vasukisquare.database.repository import (
    BookRepository,
    PageRepository,
    CoverRepository,
)


def create_mock_db():
    """Helper to create a high-fidelity mock PyMongo Database."""
    mock_db = MagicMock()
    collections = {}

    def get_collection(name):
        if name not in collections:
            coll = MagicMock()
            store = {}
            indexes = []

            def create_indexes(idx_list):
                indexes.extend(idx_list)
                return [idx.document.get("name", "idx") for idx in idx_list]

            def insert_one(doc):
                store[doc["_id"]] = dict(doc)
                res = MagicMock()
                res.inserted_id = doc["_id"]
                return res

            def insert_many(docs, ordered=True):
                for doc in docs:
                    store[doc["_id"]] = dict(doc)
                res = MagicMock()
                res.inserted_ids = [doc["_id"] for doc in docs]
                return res

            def delete_many(filter_dict):
                target_ids = filter_dict.get("_id", {}).get("$in", [])
                for tid in target_ids:
                    store.pop(tid, None)
                res = MagicMock()
                res.deleted_count = len(target_ids)
                return res

            def find_one(query):
                if "_id" in query:
                    return store.get(query["_id"])
                if "slug" in query:
                    for doc in store.values():
                        if doc.get("slug") == query["slug"]:
                            return doc
                if "book_id" in query:
                    for doc in store.values():
                        if doc.get("book_id") == query["book_id"]:
                            return doc
                return None

            def find(query):
                cursor = MagicMock()
                results = [
                    doc for doc in store.values()
                    if doc.get("book_id") == query.get("book_id")
                ]
                cursor.sort.return_value = sorted(results, key=lambda x: x.get("page_number", 0))
                return cursor

            def update_one(filter_dict, update_dict):
                target_id = filter_dict.get("_id")
                if target_id in store and "$set" in update_dict:
                    store[target_id].update(update_dict["$set"])
                res = MagicMock()
                res.modified_count = 1
                return res

            coll.create_indexes.side_effect = create_indexes
            coll.insert_one.side_effect = insert_one
            coll.insert_many.side_effect = insert_many
            coll.delete_many.side_effect = delete_many
            coll.find_one.side_effect = find_one
            coll.find.side_effect = find
            coll.update_one.side_effect = update_one
            collections[name] = coll
        return collections[name]

    mock_db.__getitem__.side_effect = get_collection
    return mock_db


def test_index_initialization():
    db = create_mock_db()
    book_repo = BookRepository(db)
    page_repo = PageRepository(db)
    cover_repo = CoverRepository(db)

    book_repo.create_indexes()
    page_repo.create_indexes()
    cover_repo.create_indexes()

    assert db["books"].create_indexes.called
    assert db["pages"].create_indexes.called
    assert db["covers"].create_indexes.called


def test_linked_pages_single_page():
    db = create_mock_db()
    book_repo = BookRepository(db)
    page_repo = PageRepository(db)

    book = Book(title="Single Page Book", topic="Demo")
    book_repo.create(book)

    pages = [
        Page(
            book_id=book.id,
            page_number=1,
            page_type=LayoutType.TEXT_HEAVY.value,
            layout=LayoutType.TEXT_HEAVY.value,
        )
    ]
    linked_pages = page_repo.insert_pages_linked(pages)
    book_repo.update_starting_page(book.id, linked_pages[0].id)

    assert linked_pages[0].previous_page_id is None
    assert linked_pages[0].next_page_id is None

    # Traversal
    traversed = page_repo.get_linked_pages(book.starting_page_id or linked_pages[0].id)
    assert len(traversed) == 1
    assert traversed[0].id == linked_pages[0].id
    assert traversed[0].previous_page_id is None
    assert traversed[0].next_page_id is None


def test_linked_pages_two_pages():
    db = create_mock_db()
    book_repo = BookRepository(db)
    page_repo = PageRepository(db)

    book = Book(title="Two Page Book", topic="Demo")
    book_repo.create(book)

    pages = [
        Page(
            book_id=book.id,
            page_number=1,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
        ),
        Page(
            book_id=book.id,
            page_number=2,
            page_type=LayoutType.TEXT_HEAVY.value,
            layout=LayoutType.TEXT_HEAVY.value,
        ),
    ]
    linked_pages = page_repo.insert_pages_linked(pages)
    book_repo.update_starting_page(book.id, linked_pages[0].id)

    # Page 1: previous is None, next is Page 2
    assert linked_pages[0].previous_page_id is None
    assert linked_pages[0].next_page_id == linked_pages[1].id

    # Page 2: previous is Page 1, next is None
    assert linked_pages[1].previous_page_id == linked_pages[0].id
    assert linked_pages[1].next_page_id is None

    # Traversal from root
    traversed = page_repo.get_linked_pages(linked_pages[0].id)
    assert len(traversed) == 2
    assert [p.page_number for p in traversed] == [1, 2]
    assert traversed[0].next_page_id == traversed[1].id
    assert traversed[1].previous_page_id == traversed[0].id


def test_linked_pages_hundred_pages():
    db = create_mock_db()
    book_repo = BookRepository(db)
    page_repo = PageRepository(db)

    book = Book(
        title="Comprehensive Hundred Page Guide",
        topic="Scalable Architecture",
        page_count=100,
        chapter_count=5,
    )
    book_repo.create(book)

    pages = []
    for i in range(1, 101):
        ch_num = (i // 20) + 1
        page = Page(
            book_id=book.id,
            page_number=i,
            page_type=LayoutType.TEXT_HEAVY.value,
            chapter_number=ch_num,
            chapter_name=f"Chapter {ch_num}",
            layout=LayoutType.TEXT_HEAVY.value,
            content=PageContent(headline=f"Page {i} Analysis"),
        )
        pages.append(page)

    linked_pages = page_repo.insert_pages_linked(pages)
    book_repo.update_starting_page(book.id, linked_pages[0].id)

    # 1. Check invariants
    # Page 1 prev is None
    assert linked_pages[0].previous_page_id is None
    assert linked_pages[0].next_page_id == linked_pages[1].id

    # Page 100 next is None
    assert linked_pages[99].next_page_id is None
    assert linked_pages[99].previous_page_id == linked_pages[98].id

    # Check all intermediate 98 pages
    for i in range(1, 99):
        assert linked_pages[i].previous_page_id == linked_pages[i - 1].id
        assert linked_pages[i].next_page_id == linked_pages[i + 1].id

    # 2. Traverse full graph from start
    traversed = page_repo.get_linked_pages(linked_pages[0].id)
    assert len(traversed) == 100
    for idx, page in enumerate(traversed):
        assert page.page_number == idx + 1
        assert page.book_id == book.id


def test_book_cover_linking():
    db = create_mock_db()
    book_repo = BookRepository(db)
    cover_repo = CoverRepository(db)

    book = Book(title="Distributed Systems In Depth")
    book_repo.create(book)

    cover = Cover(
        book_id=book.id,
        title=book.title,
        design={"palette": "brand-green"},
    )
    cover_repo.create(cover)
    book_repo.update_cover_id(book.id, cover.id)

    updated_book = book_repo.get_by_id(book.id)
    assert updated_book is not None
    assert updated_book.cover_id == cover.id

    retrieved_cover = cover_repo.get_by_book_id(book.id)
    assert retrieved_cover is not None
    assert retrieved_cover.book_id == book.id


def test_page_batch_rollback():
    db = create_mock_db()
    page_repo = PageRepository(db)

    # Simulate insert failure
    db["pages"].insert_many.side_effect = Exception("DB Connection Lost")

    pages = [
        Page(book_id="b-err", page_number=1, layout="text_heavy"),
        Page(book_id="b-err", page_number=2, layout="text_heavy"),
    ]

    with pytest.raises(PyMongoError) as exc_info:
        page_repo.insert_pages_linked(pages)

    assert "rolled back" in str(exc_info.value)
    assert db["pages"].delete_many.called
