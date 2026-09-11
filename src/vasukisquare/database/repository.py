"""MongoDB repositories for Books, Pages, and Covers."""

from typing import List, Optional
from pymongo.collection import Collection
from pymongo.database import Database
from vasukisquare.book.models import Book, Page, Cover


class BookRepository:
    """Repository for Book persistence and retrieval."""

    def __init__(self, db: Database):
        self.collection: Collection = db["books"]

    def create(self, book: Book) -> Book:
        """Insert a new book document."""
        data = book.model_dump()
        data["_id"] = data["id"]
        self.collection.insert_one(data)
        return book

    def get_by_id(self, book_id: str) -> Optional[Book]:
        """Find a book by its ID."""
        doc = self.collection.find_one({"_id": book_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Book(**doc)

    def update_starting_page(self, book_id: str, starting_page_id: str) -> bool:
        """Update the starting page reference for a book."""
        res = self.collection.update_one(
            {"_id": book_id},
            {"$set": {"starting_page_id": starting_page_id}}
        )
        return res.modified_count > 0


class PageRepository:
    """Repository for Page persistence and linked list navigation."""

    def __init__(self, db: Database):
        self.collection: Collection = db["pages"]

    def create(self, page: Page) -> Page:
        """Insert a page document."""
        data = page.model_dump()
        data["_id"] = data["id"]
        self.collection.insert_one(data)
        return page

    def get_by_id(self, page_id: str) -> Optional[Page]:
        """Find a page by its ID."""
        doc = self.collection.find_one({"_id": page_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Page(**doc)

    def get_by_book(self, book_id: str) -> List[Page]:
        """Find all pages for a given book ordered by page number."""
        docs = self.collection.find({"book_id": book_id}).sort("page_number", 1)
        pages = []
        for doc in docs:
            doc.pop("_id", None)
            pages.append(Page(**doc))
        return pages

    def link_pages(self, prev_page_id: str, next_page_id: str) -> None:
        """Update previous and next page links between two adjacent pages."""
        self.collection.update_one(
            {"_id": prev_page_id},
            {"$set": {"next_page_id": next_page_id}}
        )
        self.collection.update_one(
            {"_id": next_page_id},
            {"$set": {"previous_page_id": prev_page_id}}
        )


class CoverRepository:
    """Repository for Cover persistence and retrieval."""

    def __init__(self, db: Database):
        self.collection: Collection = db["covers"]

    def create(self, cover: Cover) -> Cover:
        """Insert a cover document."""
        data = cover.model_dump()
        data["_id"] = data["id"]
        self.collection.insert_one(data)
        return cover

    def get_by_book_id(self, book_id: str) -> Optional[Cover]:
        """Find cover by book ID."""
        doc = self.collection.find_one({"book_id": book_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Cover(**doc)

