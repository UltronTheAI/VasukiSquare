"""Integration tests for database persistence and entity relationships."""

from unittest.mock import MagicMock
from vasukisquare.book.models import Book, Page, Cover
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme
from vasukisquare.database.repository import BookRepository, PageRepository, CoverRepository


def test_book_page_cover_relationships():
    # In-memory dictionary store simulating Mongo collections
    mock_db = MagicMock()
    collections = {}

    def get_collection(name):
        if name not in collections:
            coll = MagicMock()
            store = {}

            def insert_one(doc):
                store[doc["_id"]] = dict(doc)
                res = MagicMock()
                res.inserted_id = doc["_id"]
                return res

            def find_one(query):
                if "_id" in query:
                    return store.get(query["_id"])
                if "book_id" in query:
                    for doc in store.values():
                        if doc.get("book_id") == query["book_id"]:
                            return doc
                return None

            def find(query):
                cursor = MagicMock()
                results = [doc for doc in store.values() if doc.get("book_id") == query.get("book_id")]
                cursor.sort.return_value = results
                return cursor

            def update_one(filter_dict, update_dict):
                target_id = filter_dict.get("_id")
                if target_id in store and "$set" in update_dict:
                    store[target_id].update(update_dict["$set"])
                res = MagicMock()
                res.modified_count = 1
                return res

            coll.insert_one.side_effect = insert_one
            coll.find_one.side_effect = find_one
            coll.find.side_effect = find
            coll.update_one.side_effect = update_one
            collections[name] = coll
        return collections[name]

    mock_db.__getitem__.side_effect = get_collection

    book_repo = BookRepository(mock_db)
    page_repo = PageRepository(mock_db)
    cover_repo = CoverRepository(mock_db)

    # 1. Create Book
    book = Book(
        id="book-alpha",
        title="Modern Microservices",
        topic="Software Engineering",
    )
    book_repo.create(book)

    # 2. Create Linked Pages
    page1 = Page(
        id="page-alpha-1",
        book_id=book.id,
        page_number=1,
        layout_type=LayoutType.COVER,
        theme=Theme.LIGHT,
    )
    page2 = Page(
        id="page-alpha-2",
        book_id=book.id,
        page_number=2,
        chapter_number=1,
        chapter_title="Service Decomposition",
        layout_type=LayoutType.CHAPTER_OPENER,
        theme=Theme.DARK,
        icon_name="sparkles",
        previous_page_id="page-alpha-1",
    )
    page1.next_page_id = "page-alpha-2"

    page_repo.create(page1)
    page_repo.create(page2)

    # 3. Update Book starting_page_id
    book_repo.update_starting_page(book.id, page1.id)

    # 4. Create Cover
    cover = Cover(
        id="cover-alpha",
        book_id=book.id,
        title=book.title,
    )
    cover_repo.create(cover)

    # Verify relationships per TESTS.md:
    # book.starting_page_id -> correct first page
    retrieved_book = book_repo.get_by_id(book.id)
    assert retrieved_book is not None
    assert retrieved_book.starting_page_id == page1.id

    # page.book_id -> correct book
    retrieved_p1 = page_repo.get_by_id(page1.id)
    retrieved_p2 = page_repo.get_by_id(page2.id)
    assert retrieved_p1 is not None and retrieved_p2 is not None
    assert retrieved_p1.book_id == book.id
    assert retrieved_p2.book_id == book.id

    # page.previous_page_id -> previous page
    assert retrieved_p2.previous_page_id == page1.id

    # page.next_page_id -> next page
    assert retrieved_p1.next_page_id == page2.id

    # cover.book_id -> correct book
    retrieved_cover = cover_repo.get_by_book_id(book.id)
    assert retrieved_cover is not None
    assert retrieved_cover.book_id == book.id

