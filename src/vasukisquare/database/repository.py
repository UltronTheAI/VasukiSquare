"""MongoDB repositories for Books, Pages, Covers, and Advertisements."""

import math
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from vasukisquare.book.models import (
    Book,
    Page,
    Cover,
    Ad,
    PaginatedResult,
    PublicationStatus,
    PublicationVisibility,
    PageContent,
    PageStyle,
    slugify,
)


class BookRepository:
    """Repository for Book persistence, discovery, featured curation, and publishing."""

    def __init__(self, db: Database):
        self.db: Database = db
        self.collection: Collection = db["books"]

    def create_indexes(self) -> None:
        """Ensure required indexes on books collection."""
        self.collection.create_indexes([
            IndexModel([("slug", ASCENDING)], unique=True, name="books_slug_unique"),
            IndexModel(
                [
                    ("publication.status", ASCENDING),
                    ("publication.visibility", ASCENDING),
                    ("updated_at", DESCENDING),
                ],
                name="books_publication_idx",
            ),
            IndexModel(
                [
                    ("featured.pinned", ASCENDING),
                    ("featured.position", ASCENDING),
                ],
                name="books_featured_idx",
            ),
            IndexModel(
                [
                    ("discovery.search_title", "text"),
                    ("title", "text"),
                    ("description", "text"),
                    ("discovery.keywords", "text"),
                ],
                name="books_text_search",
            ),
        ])

    def resolve_unique_slug(self, base_slug: str, exclude_book_id: Optional[str] = None) -> str:
        """Resolve a deterministic, collision-safe slug (e.g. good-habits, good-habits-2)."""
        base = slugify(base_slug) or "book"
        existing = self.collection.find_one({"slug": base})
        if not existing:
            return base
        if exclude_book_id and (existing.get("_id") == exclude_book_id or existing.get("id") == exclude_book_id):
            return base

        # Find all slugs starting with the base pattern
        pattern = f"^{re.escape(base)}(?:-([0-9]+))?$"
        matches = self.collection.find({"slug": {"$regex": pattern}}, {"slug": 1, "_id": 1, "id": 1})
        taken_suffixes = set()
        for doc in matches:
            if exclude_book_id and (doc.get("_id") == exclude_book_id or doc.get("id") == exclude_book_id):
                continue
            s = doc.get("slug", "")
            if s == base:
                taken_suffixes.add(1)
            else:
                m = re.match(pattern, s)
                if m and m.group(1):
                    try:
                        taken_suffixes.add(int(m.group(1)))
                    except ValueError:
                        pass

        # Find the smallest available integer >= 2
        cand = 2
        while cand in taken_suffixes:
            cand += 1
        return f"{base}-{cand}"

    def create(self, book: Book) -> Book:
        """Insert a new book document ensuring slug uniqueness."""
        if not book.slug:
            book.slug = slugify(book.title)
        book.slug = self.resolve_unique_slug(book.slug, exclude_book_id=book.id)
        book.seo.canonical_slug = book.slug

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
        """Find any book by its unique slug."""
        doc = self.collection.find_one({"slug": slug})
        if not doc:
            return None
        doc.pop("_id", None)
        return Book(**doc)

    def get_public_book_by_slug(self, slug: str) -> Optional[Book]:
        """Find a public, published book by its unique slug."""
        doc = self.collection.find_one({
            "slug": slug,
            "publication.status": PublicationStatus.PUBLISHED.value,
            "publication.visibility": PublicationVisibility.PUBLIC.value,
        })
        if not doc:
            return None
        doc.pop("_id", None)
        return Book(**doc)

    def get_public_books(self, page: int = 1, limit: int = 20) -> PaginatedResult[Book]:
        """Retrieve paginated public, published books."""
        page = max(1, page)
        limit = max(1, limit)
        filter_q = {
            "publication.status": PublicationStatus.PUBLISHED.value,
            "publication.visibility": PublicationVisibility.PUBLIC.value,
        }
        total = self.collection.count_documents(filter_q) if hasattr(self.collection, "count_documents") else len(list(self.collection.find(filter_q)))
        skip = (page - 1) * limit
        cursor = self.collection.find(filter_q).sort([
            ("publication.published_at", DESCENDING),
            ("created_at", DESCENDING),
        ]).skip(skip).limit(limit)

        items = []
        for doc in cursor:
            doc.pop("_id", None)
            items.append(Book(**doc))

        total_pages = math.ceil(total / limit) if total > 0 else 1
        return PaginatedResult[Book](
            items=items,
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    def search_books(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
        public_only: bool = True,
    ) -> PaginatedResult[Book]:
        """Search books by title, subtitle, description, keywords, or category."""
        page = max(1, page)
        limit = max(1, limit)
        filter_q: Dict[str, Any] = {}
        if public_only:
            filter_q["publication.status"] = PublicationStatus.PUBLISHED.value
            filter_q["publication.visibility"] = PublicationVisibility.PUBLIC.value

        q_clean = query.strip()
        if q_clean:
            regex_pat = re.compile(re.escape(q_clean), re.IGNORECASE)
            filter_q["$or"] = [
                {"title": {"$regex": regex_pat}},
                {"subtitle": {"$regex": regex_pat}},
                {"description": {"$regex": regex_pat}},
                {"discovery.search_title": {"$regex": regex_pat}},
                {"discovery.keywords": {"$regex": regex_pat}},
                {"category": {"$regex": regex_pat}},
            ]

        total = self.collection.count_documents(filter_q) if hasattr(self.collection, "count_documents") else len(list(self.collection.find(filter_q)))
        skip = (page - 1) * limit
        cursor = self.collection.find(filter_q).sort([
            ("publication.published_at", DESCENDING),
            ("created_at", DESCENDING),
        ]).skip(skip).limit(limit)

        items = []
        for doc in cursor:
            doc.pop("_id", None)
            items.append(Book(**doc))

        total_pages = math.ceil(total / limit) if total > 0 else 1
        return PaginatedResult[Book](
            items=items,
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    def get_sitemap_books(self) -> List[Dict[str, Any]]:
        """Return all public published books with slug and updated_at for sitemap consumption."""
        filter_q = {
            "publication.status": PublicationStatus.PUBLISHED.value,
            "publication.visibility": PublicationVisibility.PUBLIC.value,
        }
        docs = self.collection.find(filter_q, {"slug": 1, "updated_at": 1, "_id": 0}).sort("updated_at", DESCENDING)
        res = []
        for d in docs:
            res.append({
                "slug": d.get("slug"),
                "updated_at": d.get("updated_at"),
            })
        return res

    def pin_book(self, book_id: str, position: int) -> Book:
        """Pin a book to a featured position (1..5). Enforces max 5 pins and unique positions."""
        if position not in (1, 2, 3, 4, 5):
            raise ValueError(f"Position must be between 1 and 5. Got {position}.")

        book = self.get_by_id(book_id)
        if not book:
            raise ValueError(f"Book with id '{book_id}' not found.")

        # Check total pinned books
        pinned_docs = list(self.collection.find({"featured.pinned": True}))
        is_already_pinned = any(d["_id"] == book_id for d in pinned_docs)
        if not is_already_pinned and len(pinned_docs) >= 5:
            raise ValueError("Maximum of 5 pinned books reached.")

        # Check for position collision
        for d in pinned_docs:
            if d["_id"] != book_id and d.get("featured", {}).get("position") == position:
                raise ValueError(f"Position {position} is already occupied by another book.")

        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"_id": book_id},
            {
                "$set": {
                    "featured.pinned": True,
                    "featured.position": position,
                    "updated_at": now,
                }
            },
        )
        return self.get_by_id(book_id)

    def unpin_book(self, book_id: str) -> Book:
        """Unpin a featured book."""
        book = self.get_by_id(book_id)
        if not book:
            raise ValueError(f"Book with id '{book_id}' not found.")

        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"_id": book_id},
            {
                "$set": {
                    "featured.pinned": False,
                    "featured.position": None,
                    "updated_at": now,
                }
            },
        )
        return self.get_by_id(book_id)

    def reorder_pin(self, book_id: str, position: int) -> Book:
        """Safely change or swap the pin position of a pinned book."""
        if position not in (1, 2, 3, 4, 5):
            raise ValueError(f"Position must be between 1 and 5. Got {position}.")

        book = self.get_by_id(book_id)
        if not book:
            raise ValueError(f"Book with id '{book_id}' not found.")
        if not book.featured.pinned:
            raise ValueError(f"Book '{book_id}' is not currently pinned. Use pin_book instead.")

        current_pos = book.featured.position
        if current_pos == position:
            return book

        now = datetime.now(timezone.utc)
        conflict = self.collection.find_one({
            "featured.pinned": True,
            "featured.position": position,
            "_id": {"$ne": book_id},
        })
        if conflict:
            # Swap positions atomically
            self.collection.update_one(
                {"_id": conflict["_id"]},
                {"$set": {"featured.position": current_pos, "updated_at": now}},
            )

        self.collection.update_one(
            {"_id": book_id},
            {"$set": {"featured.position": position, "updated_at": now}},
        )
        return self.get_by_id(book_id)

    def get_pinned_books(self) -> List[Book]:
        """Retrieve all currently pinned books ordered by position (1 to 5)."""
        docs = self.collection.find({"featured.pinned": True}).sort("featured.position", ASCENDING)
        books = []
        for doc in docs:
            doc.pop("_id", None)
            books.append(Book(**doc))
        return books

    def update_starting_page(self, book_id: str, starting_page_id: str) -> bool:
        """Update the starting page reference for a book."""
        res = self.collection.update_one(
            {"_id": book_id},
            {"$set": {"starting_page_id": starting_page_id, "updated_at": datetime.now(timezone.utc)}}
        )
        return res.modified_count > 0

    def update_cover_id(self, book_id: str, cover_id: str) -> bool:
        """Update the cover reference for a book."""
        res = self.collection.update_one(
            {"_id": book_id},
            {"$set": {"cover_id": cover_id, "updated_at": datetime.now(timezone.utc)}}
        )
        return res.modified_count > 0

    def update_publication_status(
        self,
        book_id: str,
        status: Union[PublicationStatus, str],
        visibility: Optional[Union[PublicationVisibility, str]] = None,
    ) -> bool:
        """Update publication status and visibility atomically."""
        stat_val = status.value if isinstance(status, PublicationStatus) else str(status)
        now = datetime.now(timezone.utc)
        update_set: Dict[str, Any] = {
            "status": stat_val,
            "publication.status": stat_val,
            "publication.updated_at": now,
            "updated_at": now,
        }
        if stat_val == PublicationStatus.PUBLISHED.value:
            update_set["publication.published_at"] = now
        if visibility:
            vis_val = visibility.value if isinstance(visibility, PublicationVisibility) else str(visibility)
            update_set["publication.visibility"] = vis_val

        res = self.collection.update_one({"_id": book_id}, {"$set": update_set})
        return res.modified_count > 0

    def update_metadata(self, book_id: str, updates: Dict[str, Any]) -> Optional[Book]:
        """Update arbitrary book metadata fields with updated_at maintenance."""
        clean_updates = dict(updates)
        clean_updates.pop("_id", None)
        clean_updates.pop("id", None)
        clean_updates["updated_at"] = datetime.now(timezone.utc)

        if "title" in clean_updates:
            clean_updates["discovery.search_title"] = clean_updates["title"].strip().lower()

        res = self.collection.update_one({"_id": book_id}, {"$set": clean_updates})
        if res.matched_count == 0:
            return None
        return self.get_by_id(book_id)

    def increment_views(self, book_id: str) -> bool:
        """Atomically increment book views counter."""
        res = self.collection.update_one(
            {"_id": book_id},
            {"$inc": {"stats.views": 1}}
        )
        return res.modified_count > 0

    def increment_opens(self, book_id: str) -> bool:
        """Atomically increment book opens counter."""
        res = self.collection.update_one(
            {"_id": book_id},
            {"$inc": {"stats.opens": 1}}
        )
        return res.modified_count > 0

    def delete_book(self, book_id: str) -> bool:
        """Safely delete book and cascade delete all associated pages and cover. Ads are preserved."""
        res = self.collection.delete_one({"_id": book_id})
        # Cascade delete pages and covers
        self.db["pages"].delete_many({"book_id": book_id})
        self.db["covers"].delete_many({"book_id": book_id})
        return res.deleted_count > 0


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

    def get_page(self, book_id: str, page_number: int) -> Optional[Page]:
        """Find a specific page by book ID and page number."""
        doc = self.collection.find_one({"book_id": book_id, "page_number": page_number})
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

    def get_book_pages(self, book_id: str, start_page: int = 1, limit: Optional[int] = None) -> List[Page]:
        """Find pages for a book from start_page with optional limit."""
        query = {"book_id": book_id, "page_number": {"$gte": start_page}}
        cursor = self.collection.find(query).sort("page_number", ASCENDING)
        if limit:
            cursor = cursor.limit(limit)
        pages = []
        for doc in cursor:
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

    def update_page_content(
        self,
        page_id: str,
        content: Union[PageContent, Dict[str, Any]],
        rerender_html: bool = False,
        book_title: str = "",
    ) -> Optional[Page]:
        """Update structured page content and maintain updated_at."""
        page = self.get_by_id(page_id)
        if not page:
            return None

        if isinstance(content, dict):
            content_obj = PageContent(**content)
        else:
            content_obj = content

        page.content = content_obj
        page.updated_at = datetime.now(timezone.utc)

        update_fields: Dict[str, Any] = {
            "content": content_obj.model_dump(),
            "updated_at": page.updated_at,
        }

        if rerender_html:
            from vasukisquare.renderer.html import HtmlPageRenderer
            renderer = HtmlPageRenderer()
            new_html = renderer.render_page(page, book_title=book_title or "VasukiSquare Book")
            page.html = new_html
            update_fields["html"] = new_html

        self.collection.update_one({"_id": page_id}, {"$set": update_fields})
        return page

    def update_page_style(
        self,
        page_id: str,
        style: Union[PageStyle, Dict[str, Any]],
        rerender_html: bool = False,
        book_title: str = "",
    ) -> Optional[Page]:
        """Update structured page style and maintain updated_at."""
        page = self.get_by_id(page_id)
        if not page:
            return None

        if isinstance(style, dict):
            style_obj = PageStyle(**style)
        else:
            style_obj = style

        page.style = style_obj
        page.updated_at = datetime.now(timezone.utc)

        update_fields: Dict[str, Any] = {
            "style": style_obj.model_dump(),
            "updated_at": page.updated_at,
        }

        if rerender_html:
            from vasukisquare.renderer.html import HtmlPageRenderer
            renderer = HtmlPageRenderer()
            new_html = renderer.render_page(page, book_title=book_title or "VasukiSquare Book")
            page.html = new_html
            update_fields["html"] = new_html

        self.collection.update_one({"_id": page_id}, {"$set": update_fields})
        return page

    def delete_by_book_id(self, book_id: str) -> int:
        """Delete all pages belonging to a book."""
        res = self.collection.delete_many({"book_id": book_id})
        return res.deleted_count


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

    def update_metadata(self, cover_id: str, updates: Dict[str, Any]) -> Optional[Cover]:
        """Update cover metadata and maintain updated_at."""
        clean_updates = dict(updates)
        clean_updates.pop("_id", None)
        clean_updates.pop("id", None)
        clean_updates["updated_at"] = datetime.now(timezone.utc)
        res = self.collection.update_one({"_id": cover_id}, {"$set": clean_updates})
        if res.matched_count == 0:
            return None
        return self.get_by_id(cover_id)

    def delete_by_book_id(self, book_id: str) -> int:
        """Delete cover associated with a book ID."""
        res = self.collection.delete_many({"book_id": book_id})
        return res.deleted_count


class AdRepository:
    """Repository for native advertisement persistence and retrieval in 'ads' collection."""

    def __init__(self, db: Database):
        self.collection: Collection = db["ads"]

    def create_indexes(self) -> None:
        """Ensure required indexes on ads collection."""
        self.collection.create_indexes([
            IndexModel([("active", ASCENDING)], name="ads_active_idx"),
            IndexModel([("priority", ASCENDING)], name="ads_priority_idx"),
            IndexModel([("placements", ASCENDING)], name="ads_placements_idx"),
            IndexModel(
                [("starts_at", ASCENDING), ("ends_at", ASCENDING)],
                name="ads_dates_idx",
            ),
        ])

    def create(self, ad: Ad) -> Ad:
        """Insert a new native advertisement."""
        data = ad.model_dump()
        data["_id"] = data["id"]
        self.collection.insert_one(data)
        return ad

    def get_by_id(self, ad_id: str) -> Optional[Ad]:
        """Find an advertisement by ID."""
        doc = self.collection.find_one({"_id": ad_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Ad(**doc)

    def update(self, ad_id: str, updates: Dict[str, Any]) -> Optional[Ad]:
        """Update advertisement fields and maintain updated_at."""
        clean_updates = dict(updates)
        clean_updates.pop("_id", None)
        clean_updates.pop("id", None)
        clean_updates["updated_at"] = datetime.now(timezone.utc)
        res = self.collection.update_one({"_id": ad_id}, {"$set": clean_updates})
        if res.matched_count == 0:
            return None
        return self.get_by_id(ad_id)

    def delete(self, ad_id: str) -> bool:
        """Delete an advertisement."""
        res = self.collection.delete_one({"_id": ad_id})
        return res.deleted_count > 0

    def list_ads(self, active_only: bool = False) -> List[Ad]:
        """List advertisements, optionally filtering only active ones."""
        query = {"active": True} if active_only else {}
        docs = self.collection.find(query).sort("priority", ASCENDING)
        ads = []
        for doc in docs:
            doc.pop("_id", None)
            ads.append(Ad(**doc))
        return ads

    def get_active_ads(
        self,
        placement: Optional[str] = None,
        at_time: Optional[datetime] = None,
    ) -> List[Ad]:
        """Find currently eligible active ads for a placement and time."""
        now = at_time or datetime.now(timezone.utc)
        query: Dict[str, Any] = {
            "active": True,
            "$and": [
                {"$or": [{"starts_at": None}, {"starts_at": {"$lte": now}}]},
                {"$or": [{"ends_at": None}, {"ends_at": {"$gte": now}}]},
            ],
        }
        if placement:
            query["placements"] = placement

        docs = self.collection.find(query).sort("priority", ASCENDING)
        ads = []
        for doc in docs:
            doc.pop("_id", None)
            ads.append(Ad(**doc))
        return ads

    def increment_impression(self, ad_id: str) -> bool:
        """Atomically increment advertisement impressions counter."""
        res = self.collection.update_one(
            {"_id": ad_id},
            {"$inc": {"stats.impressions": 1}}
        )
        return res.modified_count > 0

    def increment_click(self, ad_id: str) -> bool:
        """Atomically increment advertisement clicks counter."""
        res = self.collection.update_one(
            {"_id": ad_id},
            {"$inc": {"stats.clicks": 1}}
        )
        return res.modified_count > 0


def select_weighted_ad(
    ads: List[Ad],
    rng: Optional[random.Random] = None,
    at_time: Optional[datetime] = None,
) -> Optional[Ad]:
    """Select an advertisement using priority-weighted random selection.

    Weights:
        Priority 1: 10
        Priority 2: 5
        Priority 3: 2

    Only ads with active=True, starts_at <= now, and ends_at >= now are eligible.
    """
    if not ads:
        return None

    now = at_time or datetime.now(timezone.utc)
    eligible: List[Ad] = []
    for ad in ads:
        if not ad.active:
            continue
        if ad.starts_at and ad.starts_at > now:
            continue
        if ad.ends_at and ad.ends_at < now:
            continue
        eligible.append(ad)

    if not eligible:
        return None

    priority_weights = {1: 10, 2: 5, 3: 2}
    weights = [priority_weights.get(ad.priority, 2) for ad in eligible]

    if rng is not None:
        return rng.choices(eligible, weights=weights, k=1)[0]
    return random.choices(eligible, weights=weights, k=1)[0]
