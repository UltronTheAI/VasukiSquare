"""MongoDB repositories for Books, Pages, and Covers."""

from typing import List, Optional
from pymongo import ASCENDING, IndexModel
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError
from vasukisquare.book.models import Book, Page, Cover


class BookRepository:
    """Repository for Book persistence and retrieval in 'books' collection."""

    def __init__(self, db: Database):
        self.collection: Collection = db["books"]

    def create_indexes(self) -> None:
        """Ensure required indexes on books collection."""
        self.collection.create_indexes([
            IndexModel([("slug", ASCENDING)], unique=True, name="books_slug_unique"),
        ])

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

    def get_by_slug(self, slug: str) -> Optional[Book]:
        """Find a book by its unique slug."""
        doc = self.collection.find_one({"slug": slug})
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

    def update_cover_id(self, book_id: str, cover_id: str) -> bool:
        """Update the cover reference for a book."""
        res = self.collection.update_one(
            {"_id": book_id},
            {"$set": {"cover_id": cover_id}}
        )
        return res.modified_count > 0


class PageRepository:
    """Repository for Page persistence and linked list navigation in 'pages' collection."""

    def __init__(self, db: Database):
        self.collection: Collection = db["pages"]

    def create_indexes(self) -> None:
        """Ensure required indexes on pages collection."""
        self.collection.create_indexes([
            IndexModel(
                [("book_id", ASCENDING), ("page_number", ASCENDING)],
                unique=True,
                name="pages_book_page_unique",
            ),
            IndexModel([("book_id", ASCENDING)], name="pages_book_id_idx"),
        ])

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
        docs = self.collection.find({"book_id": book_id}).sort("page_number", ASCENDING)
        pages = []
        for doc in docs:
            doc.pop("_id", None)
            pages.append(Page(**doc))
        return pages

    def get_linked_pages(self, starting_page_id: str) -> List[Page]:
        """Traverse the linked page chain forward from the starting page."""
        chain: List[Page] = []
        current_id: Optional[str] = starting_page_id
        visited: set[str] = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            page = self.get_by_id(current_id)
            if not page:
                break
            chain.append(page)
            current_id = page.next_page_id
        return chain

    def insert_pages_linked(self, pages: List[Page]) -> List[Page]:
        """Link a sequence of pages bidirectionally and insert them with rollback on failure.
        
        Rules:
        - page 1: previous_page_id = None
        - page N: next_page_id = None
        - all intermediate pages: previous_page_id and next_page_id set to adjacent page IDs.
        """
        if not pages:
            return []

        # 1. Establish linked-list pointers
        n = len(pages)
        for i, page in enumerate(pages):
            page.page_number = i + 1
            page.previous_page_id = pages[i - 1].id if i > 0 else None
            page.next_page_id = pages[i + 1].id if i < n - 1 else None

        # 2. Persist with rollback awareness
        inserted_ids: List[str] = []
        try:
            docs = []
            for page in pages:
                data = page.model_dump()
                data["_id"] = data["id"]
                docs.append(data)
                inserted_ids.append(data["_id"])
            if docs:
                self.collection.insert_many(docs, ordered=True)
            return pages
        except Exception as e:
            # Rollback any inserted documents in this batch
            if inserted_ids:
                try:
                    self.collection.delete_many({"_id": {"$in": inserted_ids}})
                except Exception:
                    pass
            raise PyMongoError(f"Failed to insert linked pages batch, rolled back: {e}") from e

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
    """Repository for Cover persistence and retrieval in 'covers' collection."""

    def __init__(self, db: Database):
        self.collection: Collection = db["covers"]

    def create_indexes(self) -> None:
        """Ensure required indexes on covers collection."""
        self.collection.create_indexes([
            IndexModel([("book_id", ASCENDING)], unique=True, name="covers_book_id_unique"),
        ])

    def create(self, cover: Cover) -> Cover:
        """Insert a cover document."""
        data = cover.model_dump()
        data["_id"] = data["id"]
        self.collection.insert_one(data)
        return cover

    def get_by_id(self, cover_id: str) -> Optional[Cover]:
        """Find a cover by its ID."""
        doc = self.collection.find_one({"_id": cover_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Cover(**doc)

    def get_by_book_id(self, book_id: str) -> Optional[Cover]:
        """Find cover by book ID."""
        doc = self.collection.find_one({"book_id": book_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Cover(**doc)
