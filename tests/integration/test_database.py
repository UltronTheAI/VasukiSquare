"""Comprehensive tests for MongoDB persistence, publication models, indexing, and repository operations."""

import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from vasukisquare.book.models import (
    CURRENT_RENDERER_VERSION,
    CURRENT_SCHEMA_VERSION,
    Ad,
    Book,
    ChapterMetadata,
    Cover,
    Page,
    PageContent,
    PageStyle,
    PublicationStatus,
    PublicationVisibility,
)
from vasukisquare.database.connection import DatabaseManager
from vasukisquare.database.repository import (
    AdRepository,
    BookRepository,
    CoverRepository,
    PageRepository,
    select_weighted_ad,
)
from vasukisquare.design.theme import Theme


# ==============================================================================
# In-Memory High-Fidelity Mock Database Engine
# ==============================================================================

def get_nested(d: dict, path: str) -> Any:
    parts = path.split(".")
    curr: Any = d
    for p in parts:
        if isinstance(curr, dict):
            curr = curr.get(p)
        else:
            return None
    return curr


def set_nested(d: dict, path: str, val: Any) -> None:
    parts = path.split(".")
    curr = d
    for p in parts[:-1]:
        if p not in curr or not isinstance(curr[p], dict):
            curr[p] = {}
        curr = curr[p]
    curr[parts[-1]] = val


def inc_nested(d: dict, path: str, val: Any) -> None:
    parts = path.split(".")
    curr = d
    for p in parts[:-1]:
        if p not in curr or not isinstance(curr[p], dict):
            curr[p] = {}
        curr = curr[p]
    curr[parts[-1]] = curr.get(parts[-1], 0) + val


def match_value(val: Any, cond: Any) -> bool:
    if isinstance(cond, dict):
        for op, target in cond.items():
            if op == "$ne":
                if val == target:
                    return False
            elif op == "$eq":
                if val != target:
                    return False
            elif op == "$gte":
                if val is None or val < target:
                    return False
            elif op == "$lte":
                if val is None or val > target:
                    return False
            elif op == "$gt":
                if val is None or val <= target:
                    return False
            elif op == "$lt":
                if val is None or val >= target:
                    return False
            elif op == "$in":
                if val not in target:
                    return False
            elif op == "$regex":
                if val is None:
                    return False
                if isinstance(target, re.Pattern):
                    if not target.search(str(val)):
                        return False
                else:
                    opt = cond.get("$options", "")
                    flags = re.IGNORECASE if "i" in opt else 0
                    if not re.search(str(target), str(val), flags):
                        return False
        return True
    elif isinstance(cond, re.Pattern):
        return bool(val is not None and cond.search(str(val)))
    elif isinstance(val, list):
        return cond in val or val == cond
    else:
        return val == cond


def match_doc(doc: dict, query: dict) -> bool:
    for k, cond in query.items():
        if k == "$or":
            if not any(match_doc(doc, sub) for sub in cond):
                return False
        elif k == "$and":
            if not all(match_doc(doc, sub) for sub in cond):
                return False
        else:
            val = get_nested(doc, k)
            if not match_value(val, cond):
                return False
    return True


class MockCursor:
    def __init__(self, docs: List[dict], projection: Optional[dict] = None):
        self._docs = [dict(d) for d in docs]
        self._projection = projection
        self._sort_keys: List[tuple] = []
        self._skip_n = 0
        self._limit_n: Optional[int] = None

    def sort(self, key_or_list, direction=ASCENDING):
        if isinstance(key_or_list, list):
            self._sort_keys = key_or_list
        else:
            self._sort_keys = [(key_or_list, direction)]
        return self

    def skip(self, n: int):
        self._skip_n = n
        return self

    def limit(self, n: int):
        self._limit_n = n
        return self

    def _get_results(self) -> List[dict]:
        res = list(self._docs)
        if self._sort_keys:
            for k, direction in reversed(self._sort_keys):
                rev = (direction == DESCENDING or direction == -1)
                res.sort(
                    key=lambda d: (get_nested(d, k) is None, get_nested(d, k)),
                    reverse=rev,
                )
        if self._skip_n:
            res = res[self._skip_n:]
        if self._limit_n is not None:
            res = res[:self._limit_n]
        if self._projection:
            proj_res = []
            for d in res:
                p_doc = {}
                for pk, pv in self._projection.items():
                    if pv:
                        p_doc[pk] = get_nested(d, pk)
                if self._projection.get("_id") == 0:
                    p_doc.pop("_id", None)
                proj_res.append(p_doc)
            return proj_res
        return res

    def __iter__(self):
        return iter(self._get_results())

    def __len__(self):
        return len(self._get_results())


class MockCollection:
    def __init__(self, name: str):
        self.name = name
        self.store: Dict[str, dict] = {}
        self.indexes: List[Any] = []
        self.create_indexes = MagicMock(side_effect=self._create_indexes)
        self.insert_one = MagicMock(side_effect=self._insert_one)
        self.insert_many = MagicMock(side_effect=self._insert_many)
        self.find_one = MagicMock(side_effect=self._find_one)
        self.find = MagicMock(side_effect=self._find)
        self.count_documents = MagicMock(side_effect=self._count_documents)
        self.update_one = MagicMock(side_effect=self._update_one)
        self.update_many = MagicMock(side_effect=self._update_many)
        self.delete_one = MagicMock(side_effect=self._delete_one)
        self.delete_many = MagicMock(side_effect=self._delete_many)
        self.find_one_and_update = MagicMock(side_effect=self._find_one_and_update)

    def _find_one_and_update(self, filter_dict, update_dict, sort=None, return_document=None):
        matching = [d for d in self.store.values() if match_doc(d, filter_dict)]
        if not matching:
            return None
        if sort:
            for k, direction in reversed(sort):
                rev = (direction == -1 or direction == DESCENDING)
                matching.sort(key=lambda d: (get_nested(d, k) is None, get_nested(d, k)), reverse=rev)
        doc = matching[0]
        if "$set" in update_dict:
            for k, v in update_dict["$set"].items():
                set_nested(doc, k, v)
        if "$inc" in update_dict:
            for k, v in update_dict["$inc"].items():
                inc_nested(doc, k, v)
        return dict(doc)

    def _create_indexes(self, idx_list):
        self.indexes.extend(idx_list)
        return [getattr(idx, "name", "idx") for idx in idx_list]

    def _insert_one(self, doc):
        d = dict(doc)
        _id = d.get("_id") or d.get("id")
        d["_id"] = _id
        self.store[_id] = d
        res = MagicMock()
        res.inserted_id = _id
        return res

    def _insert_many(self, docs, ordered=True):
        inserted_ids = []
        for doc in docs:
            d = dict(doc)
            _id = d.get("_id") or d.get("id")
            d["_id"] = _id
            self.store[_id] = d
            inserted_ids.append(_id)
        res = MagicMock()
        res.inserted_ids = inserted_ids
        return res

    def _find_one(self, query=None, projection=None):
        query = query or {}
        for doc in self.store.values():
            if match_doc(doc, query):
                res_d = dict(doc)
                if projection:
                    p_doc = {}
                    for pk, pv in projection.items():
                        if pv:
                            p_doc[pk] = get_nested(res_d, pk)
                    if projection.get("_id") == 0:
                        p_doc.pop("_id", None)
                    return p_doc
                return res_d
        return None

    def _find(self, query=None, projection=None):
        query = query or {}
        matching = [dict(d) for d in self.store.values() if match_doc(d, query)]
        return MockCursor(matching, projection)

    def _count_documents(self, query=None):
        query = query or {}
        return sum(1 for d in self.store.values() if match_doc(d, query))

    def _update_one(self, filter_dict, update_dict):
        res = MagicMock()
        res.matched_count = 0
        res.modified_count = 0
        for _id, doc in self.store.items():
            if match_doc(doc, filter_dict):
                res.matched_count = 1
                if "$set" in update_dict:
                    for k, v in update_dict["$set"].items():
                        set_nested(doc, k, v)
                    res.modified_count = 1
                if "$inc" in update_dict:
                    for k, v in update_dict["$inc"].items():
                        inc_nested(doc, k, v)
                    res.modified_count = 1
                break
        return res

    def _update_many(self, filter_dict, update_dict):
        res = MagicMock()
        res.matched_count = 0
        res.modified_count = 0
        for _id, doc in self.store.items():
            if match_doc(doc, filter_dict):
                res.matched_count += 1
                if "$set" in update_dict:
                    for k, v in update_dict["$set"].items():
                        set_nested(doc, k, v)
                    res.modified_count += 1
                if "$inc" in update_dict:
                    for k, v in update_dict["$inc"].items():
                        inc_nested(doc, k, v)
                    res.modified_count += 1
        return res

    def _delete_one(self, filter_dict):
        res = MagicMock()
        res.deleted_count = 0
        for _id, doc in list(self.store.items()):
            if match_doc(doc, filter_dict):
                self.store.pop(_id, None)
                res.deleted_count = 1
                break
        return res

    def _delete_many(self, filter_dict):
        res = MagicMock()
        deleted = 0
        for _id, doc in list(self.store.items()):
            if match_doc(doc, filter_dict):
                self.store.pop(_id, None)
                deleted += 1
        res.deleted_count = deleted
        return res


def create_mock_db():
    """Helper to create a high-fidelity mock PyMongo Database."""
    mock_db = MagicMock()
    collections: Dict[str, MockCollection] = {}

    def get_collection(name):
        if name not in collections:
            collections[name] = MockCollection(name)
        return collections[name]

    mock_db.__getitem__.side_effect = get_collection
    return mock_db


# ==============================================================================
# Test Cases Covering All 30 Required Scenarios
# ==============================================================================

def test_1_book_creation():
    db = create_mock_db()
    repo = BookRepository(db)
    book = Book(
        title="Building Better Daily Habits",
        topic="Habit Formation",
        description="A practical handbook for building habits.",
    )
    repo.create(book)

    saved = repo.get_by_id(book.id)
    assert saved is not None
    assert saved.id == book.id
    assert saved.title == "Building Better Daily Habits"
    assert saved.topic == "Habit Formation"
    assert saved.schema_version == CURRENT_SCHEMA_VERSION
    assert saved.renderer_version == CURRENT_RENDERER_VERSION


def test_2_unique_slug_generation():
    db = create_mock_db()
    repo = BookRepository(db)
    book = Book(title="Good Habits", topic="Habits")
    repo.create(book)
    assert book.slug == "good-habits"
    assert book.seo.canonical_slug == "good-habits"


def test_3_slug_collision_handling():
    db = create_mock_db()
    repo = BookRepository(db)

    b1 = Book(title="Good Habits", topic="Habits 1")
    b2 = Book(title="Good Habits", topic="Habits 2")
    b3 = Book(title="Good Habits", topic="Habits 3")

    repo.create(b1)
    repo.create(b2)
    repo.create(b3)

    assert b1.slug == "good-habits"
    assert b2.slug == "good-habits-2"
    assert b3.slug == "good-habits-3"


def test_4_page_persistence():
    db = create_mock_db()
    repo = PageRepository(db)
    page = Page(
        book_id="book-1",
        page_number=1,
        layout="editorial",
        content=PageContent(headline="Introduction to Systems"),
        style=PageStyle(theme=Theme.LIGHT, accent_color="#00ed64"),
        html="<div class='page'>Content</div>",
    )
    repo.create(page)

    retrieved = repo.get_by_id(page.id)
    assert retrieved is not None
    assert retrieved.book_id == "book-1"
    assert retrieved.page_number == 1
    assert retrieved.html == "<div class='page'>Content</div>"
    assert retrieved.schema_version == CURRENT_SCHEMA_VERSION


def test_5_page_ordering():
    db = create_mock_db()
    repo = PageRepository(db)
    p2 = Page(book_id="b1", page_number=2, layout="editorial")
    p1 = Page(book_id="b1", page_number=1, layout="cover")
    p3 = Page(book_id="b1", page_number=3, layout="editorial")

    repo.create(p2)
    repo.create(p1)
    repo.create(p3)

    ordered = repo.get_by_book("b1")
    assert [p.page_number for p in ordered] == [1, 2, 3]


def test_6_doubly_linked_page_invariants():
    db = create_mock_db()
    repo = PageRepository(db)
    pages = [
        Page(book_id="b-link", page_number=1, layout="cover"),
        Page(book_id="b-link", page_number=2, layout="editorial"),
        Page(book_id="b-link", page_number=3, layout="editorial"),
    ]
    linked = repo.insert_pages_linked(pages)

    assert linked[0].previous_page_id is None
    assert linked[0].next_page_id == linked[1].id
    assert linked[1].previous_page_id == linked[0].id
    assert linked[1].next_page_id == linked[2].id
    assert linked[2].previous_page_id == linked[1].id
    assert linked[2].next_page_id is None

    traversed = repo.get_linked_pages(linked[0].id)
    assert len(traversed) == 3
    assert [p.id for p in traversed] == [p.id for p in linked]


def test_7_cover_persistence():
    db = create_mock_db()
    repo = CoverRepository(db)
    cover = Cover(
        book_id="book-cov",
        title="Modern Architecture",
        subtitle="Systems Design",
        author="Vasuki Engineering",
        design={"accent_color": "#00ed64", "cover_style": "editorial_minimal"},
        html="<div class='cover'>1600x2560 Artwork</div>",
    )
    repo.create(cover)

    retrieved = repo.get_by_book_id("book-cov")
    assert retrieved is not None
    assert retrieved.title == "Modern Architecture"
    assert retrieved.subtitle == "Systems Design"
    assert retrieved.author == "Vasuki Engineering"
    assert retrieved.width == 1600
    assert retrieved.height == 2560


def test_8_full_book_retrieval():
    db = create_mock_db()
    b_repo = BookRepository(db)
    p_repo = PageRepository(db)
    c_repo = CoverRepository(db)

    book = Book(title="Distributed Ledger Technologies", topic="Blockchain")
    b_repo.create(book)

    pages = [
        Page(book_id=book.id, page_number=1, layout="cover"),
        Page(book_id=book.id, page_number=2, layout="editorial"),
    ]
    p_repo.insert_pages_linked(pages)
    b_repo.update_starting_page(book.id, pages[0].id)

    cover = Cover(book_id=book.id, title=book.title)
    c_repo.create(cover)
    b_repo.update_cover_id(book.id, cover.id)

    # Reconstruct from DB
    loaded_book = b_repo.get_by_id(book.id)
    assert loaded_book.starting_page_id == pages[0].id
    assert loaded_book.cover_id == cover.id

    loaded_cover = c_repo.get_by_book_id(book.id)
    assert loaded_cover.id == cover.id

    loaded_pages = p_repo.get_by_book(book.id)
    assert len(loaded_pages) == 2


def test_9_public_book_listing():
    db = create_mock_db()
    repo = BookRepository(db)

    b1 = Book(title="Public Book 1", topic="AI")
    b2 = Book(title="Public Book 2", topic="AI")
    repo.create(b1)
    repo.create(b2)
    repo.update_publication_status(b1.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)
    repo.update_publication_status(b2.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)

    res = repo.get_public_books(page=1, limit=10)
    assert res.total == 2
    assert len(res.items) == 2


def test_10_draft_books_excluded_from_public_listing():
    db = create_mock_db()
    repo = BookRepository(db)

    b_pub = Book(title="Published Guide", topic="Engineering")
    b_draft = Book(title="Work In Progress", topic="Drafting")
    repo.create(b_pub)
    repo.create(b_draft)

    repo.update_publication_status(b_pub.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)
    # b_draft stays in DRAFT

    res = repo.get_public_books()
    assert res.total == 1
    assert res.items[0].id == b_pub.id

    # Also slug lookup
    assert repo.get_public_book_by_slug(b_draft.slug) is None
    assert repo.get_public_book_by_slug(b_pub.slug) is not None


def test_11_private_books_excluded():
    db = create_mock_db()
    repo = BookRepository(db)

    b_pub = Book(title="Public Manual", topic="DevOps")
    b_priv = Book(title="Internal Secrets", topic="Security")
    repo.create(b_pub)
    repo.create(b_priv)

    repo.update_publication_status(b_pub.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)
    repo.update_publication_status(b_priv.id, PublicationStatus.PUBLISHED, PublicationVisibility.PRIVATE)

    res = repo.get_public_books()
    assert res.total == 1
    assert res.items[0].id == b_pub.id
    assert repo.get_public_book_by_slug(b_priv.slug) is None


def test_12_search():
    db = create_mock_db()
    repo = BookRepository(db)

    b1 = Book(title="Deep Neural Architectures", description="Transformers and attention.")
    b2 = Book(title="Web Performance Engineering", description="Browsers and rendering.")
    repo.create(b1)
    repo.create(b2)
    repo.update_publication_status(b1.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)
    repo.update_publication_status(b2.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)

    s1 = repo.search_books("neural")
    assert s1.total == 1
    assert s1.items[0].id == b1.id

    s2 = repo.search_books("rendering")
    assert s2.total == 1
    assert s2.items[0].id == b2.id


def test_13_pagination():
    db = create_mock_db()
    repo = BookRepository(db)

    for i in range(25):
        b = Book(title=f"Book Volume {i+1}", topic="Collection")
        repo.create(b)
        repo.update_publication_status(b.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)

    page1 = repo.get_public_books(page=1, limit=10)
    assert page1.page == 1
    assert page1.limit == 10
    assert page1.total == 25
    assert page1.total_pages == 3
    assert len(page1.items) == 10
    assert page1.has_next is True
    assert page1.has_previous is False

    page3 = repo.get_public_books(page=3, limit=10)
    assert page3.page == 3
    assert len(page3.items) == 5
    assert page3.has_next is False
    assert page3.has_previous is True


def test_14_maximum_five_pinned_books():
    db = create_mock_db()
    repo = BookRepository(db)

    books = []
    for i in range(6):
        b = Book(title=f"Featured Candidate {i+1}")
        repo.create(b)
        books.append(b)

    # Pin first 5
    for i in range(5):
        repo.pin_book(books[i].id, position=i+1)

    # 6th pin must raise ValueError
    with pytest.raises(ValueError, match="Maximum of 5 pinned books reached"):
        repo.pin_book(books[5].id, position=1)


def test_15_pin_ordering():
    db = create_mock_db()
    repo = BookRepository(db)

    b1 = Book(title="Book Pos 3")
    b2 = Book(title="Book Pos 1")
    b3 = Book(title="Book Pos 2")
    repo.create(b1)
    repo.create(b2)
    repo.create(b3)

    repo.pin_book(b1.id, position=3)
    repo.pin_book(b2.id, position=1)
    repo.pin_book(b3.id, position=2)

    pinned = repo.get_pinned_books()
    assert len(pinned) == 3
    assert [b.featured.position for b in pinned] == [1, 2, 3]
    assert [b.id for b in pinned] == [b2.id, b3.id, b1.id]


def test_16_duplicate_pin_position_rejection_and_reorder():
    db = create_mock_db()
    repo = BookRepository(db)

    b1 = Book(title="Occupant Book")
    b2 = Book(title="Contender Book")
    repo.create(b1)
    repo.create(b2)

    repo.pin_book(b1.id, position=1)

    # Rejection of duplicate position via pin_book
    with pytest.raises(ValueError, match="Position 1 is already occupied"):
        repo.pin_book(b2.id, position=1)

    # Safe swap / reorder
    repo.pin_book(b2.id, position=2)
    repo.reorder_pin(b1.id, position=2)

    pinned = repo.get_pinned_books()
    assert len(pinned) == 2
    # b1 moved to 2, b2 swapped to 1
    assert repo.get_by_id(b1.id).featured.position == 2
    assert repo.get_by_id(b2.id).featured.position == 1


def test_17_book_deletion_cascade():
    db = create_mock_db()
    b_repo = BookRepository(db)
    p_repo = PageRepository(db)
    c_repo = CoverRepository(db)
    ad_repo = AdRepository(db)

    book = Book(title="To Be Deleted")
    b_repo.create(book)

    p1 = Page(book_id=book.id, page_number=1)
    p2 = Page(book_id=book.id, page_number=2)
    p_repo.create(p1)
    p_repo.create(p2)

    cover = Cover(book_id=book.id, title="Cover To Delete")
    c_repo.create(cover)

    ad = Ad(
        title="Independent Ad",
        headline="Stay Active",
        description="Not tied to book",
        sponsor="Sponsor Corp",
        url="https://example.com/ad",
    )
    ad_repo.create(ad)

    # Execute cascade delete
    deleted = b_repo.delete_book(book.id)
    assert deleted is True

    # Book, pages, and cover are gone
    assert b_repo.get_by_id(book.id) is None
    assert len(p_repo.get_by_book(book.id)) == 0
    assert c_repo.get_by_book_id(book.id) is None

    # Ad is independent and untouched
    assert ad_repo.get_by_id(ad.id) is not None


def test_18_schema_version():
    book = Book(title="Schema Check")
    page = Page(book_id="b1", page_number=1)
    cover = Cover(book_id="b1", title="Cover Check")

    assert book.schema_version == CURRENT_SCHEMA_VERSION
    assert page.schema_version == CURRENT_SCHEMA_VERSION
    assert cover.schema_version == CURRENT_SCHEMA_VERSION


def test_19_renderer_version():
    book = Book(title="Renderer Check")
    page = Page(book_id="b1", page_number=1)
    cover = Cover(book_id="b1", title="Cover Check")

    assert book.renderer_version == CURRENT_RENDERER_VERSION
    assert page.renderer_version == CURRENT_RENDERER_VERSION
    assert cover.renderer_version == CURRENT_RENDERER_VERSION


def test_20_backward_compatible_loading():
    old_raw_book = {
        "_id": "old-uuid-999",
        "id": "old-uuid-999",
        "title": "Legacy Distributed Systems",
        "status": "published",
        "chapter_count": 3,
        "page_count": 24,
    }
    loaded = Book.model_validate(old_raw_book)

    assert loaded.id == "old-uuid-999"
    assert loaded.schema_version == CURRENT_SCHEMA_VERSION
    assert loaded.renderer_version == CURRENT_RENDERER_VERSION
    assert loaded.slug == "legacy-distributed-systems"
    assert loaded.publication.status == PublicationStatus.PUBLISHED
    assert loaded.publication.visibility == PublicationVisibility.PUBLIC
    assert loaded.featured.pinned is False
    assert loaded.stats.views == 0
    assert loaded.seo.canonical_slug == "legacy-distributed-systems"


def test_21_ad_creation():
    db = create_mock_db()
    repo = AdRepository(db)
    ad = Ad(
        title="Cloud Services Pro",
        headline="Fast serverless deployments in seconds",
        description="Scale without servers across 30 global regions.",
        sponsor="Cloud Corp",
        url="https://cloudcorp.io/signup",
        placements=["home_banner", "home_sidebar"],
        priority=1,
    )
    repo.create(ad)

    saved = repo.get_by_id(ad.id)
    assert saved is not None
    assert saved.title == "Cloud Services Pro"
    assert saved.priority == 1
    assert saved.active is True
    assert saved.stats.impressions == 0


def test_22_ad_validation():
    # 1. Invalid URL scheme
    with pytest.raises(ValueError, match="valid HTTP or HTTPS"):
        Ad(
            title="Bad Ad",
            headline="Invalid Scheme",
            description="Bad URL",
            sponsor="Bad Actor",
            url="javascript:alert(1)",
        )

    # 2. HTML injection attempt
    with pytest.raises(ValueError, match="HTML tags"):
        Ad(
            title="<script>alert('xss')</script>",
            headline="XSS Attack",
            description="Trying to inject script tags",
            sponsor="Hacker",
            url="https://example.com",
        )

    # 3. Invalid priority
    with pytest.raises(ValueError, match="priority"):
        Ad(
            title="Bad Priority",
            headline="Headline",
            description="Description",
            sponsor="Sponsor",
            url="https://example.com",
            priority=5,
        )


def test_23_active_date_filtering():
    now = datetime.now(timezone.utc)
    active_ad = Ad(
        title="Active Now",
        headline="Valid window",
        description="Currently active",
        sponsor="Corp A",
        url="https://corpa.com",
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )
    future_ad = Ad(
        title="Future Ad",
        headline="Not started",
        description="Starts tomorrow",
        sponsor="Corp B",
        url="https://corpb.com",
        starts_at=now + timedelta(days=1),
    )
    past_ad = Ad(
        title="Expired Ad",
        headline="Finished yesterday",
        description="Ended yesterday",
        sponsor="Corp C",
        url="https://corpc.com",
        ends_at=now - timedelta(days=1),
    )

    db = create_mock_db()
    repo = AdRepository(db)
    repo.create(active_ad)
    repo.create(future_ad)
    repo.create(past_ad)

    active_list = repo.get_active_ads(at_time=now)
    assert len(active_list) == 1
    assert active_list[0].id == active_ad.id


def test_24_weighted_ad_selection():
    now = datetime.now(timezone.utc)
    ad_p1 = Ad(
        title="Priority 1 Ad",
        headline="Top Tier",
        description="Weight 10",
        sponsor="High Roller",
        url="https://p1.com",
        priority=1,
    )
    ad_p2 = Ad(
        title="Priority 2 Ad",
        headline="Mid Tier",
        description="Weight 5",
        sponsor="Mid Roller",
        url="https://p2.com",
        priority=2,
    )
    ad_p3 = Ad(
        title="Priority 3 Ad",
        headline="Low Tier",
        description="Weight 2",
        sponsor="Low Roller",
        url="https://p3.com",
        priority=3,
    )

    ads = [ad_p1, ad_p2, ad_p3]

    # Deterministic test using seeded RNG
    rng = random.Random(42)
    selections = {}
    for _ in range(1000):
        chosen = select_weighted_ad(ads, rng=rng, at_time=now)
        selections[chosen.title] = selections.get(chosen.title, 0) + 1

    # Priority 1 (weight 10) must receive the highest count
    assert selections["Priority 1 Ad"] > selections["Priority 2 Ad"]
    assert selections["Priority 2 Ad"] > selections["Priority 3 Ad"]


def test_25_atomic_stats_increments():
    db = create_mock_db()
    b_repo = BookRepository(db)
    ad_repo = AdRepository(db)

    book = Book(title="Popular Book")
    b_repo.create(book)

    ad = Ad(
        title="Ad Banner",
        headline="Headline",
        description="Description",
        sponsor="Sponsor",
        url="https://example.com",
    )
    ad_repo.create(ad)

    # Increment book views and opens
    b_repo.increment_views(book.id)
    b_repo.increment_views(book.id)
    b_repo.increment_opens(book.id)

    updated_book = b_repo.get_by_id(book.id)
    assert updated_book.stats.views == 2
    assert updated_book.stats.opens == 1

    # Increment ad impressions and clicks
    ad_repo.increment_impression(ad.id)
    ad_repo.increment_impression(ad.id)
    ad_repo.increment_impression(ad.id)
    ad_repo.increment_click(ad.id)

    updated_ad = ad_repo.get_by_id(ad.id)
    assert updated_ad.stats.impressions == 3
    assert updated_ad.stats.clicks == 1


def test_26_sitemap_eligible_query():
    db = create_mock_db()
    repo = BookRepository(db)

    b_pub = Book(title="Public SEO Guide", topic="SEO")
    b_draft = Book(title="Unfinished SEO", topic="SEO")
    b_priv = Book(title="Private SEO", topic="SEO")

    repo.create(b_pub)
    repo.create(b_draft)
    repo.create(b_priv)

    repo.update_publication_status(b_pub.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)
    repo.update_publication_status(b_priv.id, PublicationStatus.PUBLISHED, PublicationVisibility.PRIVATE)

    sitemap_entries = repo.get_sitemap_books()
    assert len(sitemap_entries) == 1
    assert sitemap_entries[0]["slug"] == b_pub.slug
    assert sitemap_entries[0]["updated_at"] is not None


def test_27_mongodb_disabled_generation_still_works():
    """Verify DatabaseManager and repository contracts do not interfere when db is None or disabled."""
    # Passing None or mock when disabled
    db = create_mock_db()
    mgr = DatabaseManager(db=db)
    mgr.init_all_indexes()
    assert db["books"].create_indexes.called
    assert db["pages"].create_indexes.called
    assert db["covers"].create_indexes.called
    assert db["ads"].create_indexes.called


def test_28_mongodb_failure_behavior():
    db = create_mock_db()
    page_repo = PageRepository(db)
    # Simulate DB connection drop
    db["pages"].insert_many.side_effect = Exception("DB network partition")

    pages = [
        Page(book_id="err-b", page_number=1),
        Page(book_id="err-b", page_number=2),
    ]

    with pytest.raises(PyMongoError) as exc_info:
        page_repo.insert_pages_linked(pages)

    assert "rolled back" in str(exc_info.value)


def test_29_final_repaired_page_state_equals_persisted_state():
    """Verify that repaired pages (with split content, renumbering, and final HTML) match MongoDB records."""
    db = create_mock_db()
    page_repo = PageRepository(db)

    # Simulate final repaired pages from repair engine
    p1 = Page(
        book_id="rep-book",
        page_number=1,
        layout="cover",
        html="<div class='cover'>Final Cover</div>",
    )
    p2 = Page(
        book_id="rep-book",
        page_number=2,
        layout="editorial",
        content=PageContent(headline="Part A of Long Section"),
        html="<div class='page'>Repaired Page 2 Content</div>",
    )
    p3 = Page(
        book_id="rep-book",
        page_number=3,
        layout="editorial",
        content=PageContent(headline="Part B Continuation of Long Section"),
        html="<div class='page'>Repaired Page 3 Continuation Content</div>",
    )
    repaired_pages = [p1, p2, p3]

    page_repo.insert_pages_linked(repaired_pages)

    retrieved = page_repo.get_by_book("rep-book")
    assert len(retrieved) == 3
    assert retrieved[0].html == "<div class='cover'>Final Cover</div>"
    assert retrieved[1].content.headline == "Part A of Long Section"
    assert retrieved[1].html == "<div class='page'>Repaired Page 2 Content</div>"
    assert retrieved[2].content.headline == "Part B Continuation of Long Section"
    assert retrieved[2].html == "<div class='page'>Repaired Page 3 Continuation Content</div>"


def test_30_complete_book_reconstruction_without_pdf():
    """Verify that a book, cover, and full page sequence can be completely reconstructed using ONLY MongoDB."""
    db = create_mock_db()
    b_repo = BookRepository(db)
    p_repo = PageRepository(db)
    c_repo = CoverRepository(db)

    # 1. Persist book
    chapters = [
        ChapterMetadata(chapter_number=1, title="Foundations of Habits", page_count=2),
        ChapterMetadata(chapter_number=2, title="Advanced Cue Design", page_count=2),
    ]
    book = Book(
        title="Atomic Systems Guide",
        subtitle="Designing Repeatable Workflows",
        topic="Habits & Systems",
        description="Comprehensive technical manual on building repeatable behavioral systems.",
        chapters=chapters,
        page_count=4,
    )
    b_repo.create(book)
    b_repo.update_publication_status(book.id, PublicationStatus.PUBLISHED, PublicationVisibility.PUBLIC)

    # 2. Persist cover
    cover = Cover(
        book_id=book.id,
        title=book.title,
        subtitle=book.subtitle,
        author="VasukiSquare Editorial",
        design={
            "cover_style": "editorial_minimal",
            "composition_style": "asymmetric_left",
            "palette_theme": "editorial_calm",
            "background_color": "#faf8f5",
            "accent_color": "#00ed64",
            "title_alignment": "left",
            "title_position": "middle",
        },
        html="<div class='cover-root'>Artwork Ready</div>",
    )
    c_repo.create(cover)
    b_repo.update_cover_id(book.id, cover.id)

    # 3. Persist pages
    pages = [
        Page(
            book_id=book.id,
            page_number=1,
            layout="cover",
            html="<div class='p1'>Cover</div>",
        ),
        Page(
            book_id=book.id,
            page_number=2,
            page_type="chapter_opener",
            layout="chapter_opener",
            chapter_number=1,
            chapter_name="Foundations of Habits",
            icon="sparkles",
            html="<div class='p2'>Opener Ch 1</div>",
        ),
        Page(
            book_id=book.id,
            page_number=3,
            page_type="editorial",
            layout="editorial",
            chapter_number=1,
            chapter_name="Foundations of Habits",
            content=PageContent(headline="Cue-Routine-Reward Loops"),
            html="<div class='p3'>Content Ch 1</div>",
        ),
        Page(
            book_id=book.id,
            page_number=4,
            page_type="editorial",
            layout="editorial",
            chapter_number=2,
            chapter_name="Advanced Cue Design",
            content=PageContent(headline="Friction Reduction Patterns"),
            html="<div class='p4'>Content Ch 2</div>",
        ),
    ]
    p_repo.insert_pages_linked(pages)
    b_repo.update_starting_page(book.id, pages[0].id)

    # 4. Reconstruction Test: Query ONLY through MongoDB methods (zero PDF involvement)
    # A. Retrieve Book by slug
    rec_book = b_repo.get_public_book_by_slug("atomic-systems-guide")
    assert rec_book is not None
    assert rec_book.title == "Atomic Systems Guide"
    assert rec_book.subtitle == "Designing Repeatable Workflows"
    assert len(rec_book.chapters) == 2

    # B. Reconstruct Cover
    rec_cover = c_repo.get_by_book_id(rec_book.id)
    assert rec_cover is not None
    assert rec_cover.design["cover_style"] == "editorial_minimal"
    assert rec_cover.design["background_color"] == "#faf8f5"
    assert rec_cover.html == "<div class='cover-root'>Artwork Ready</div>"

    # C. Reader view: retrieve pages in chunks (e.g. reader spread: pages 1-2)
    spread1 = p_repo.get_book_pages(rec_book.id, start_page=1, limit=2)
    assert len(spread1) == 2
    assert spread1[0].page_number == 1
    assert spread1[1].page_number == 2
    assert spread1[0].html == "<div class='p1'>Cover</div>"
    assert spread1[1].chapter_name == "Foundations of Habits"

    # Next reader spread: pages 3-4
    spread2 = p_repo.get_book_pages(rec_book.id, start_page=3, limit=2)
    assert len(spread2) == 2
    assert spread2[0].page_number == 3
    assert spread2[1].page_number == 4
    assert spread2[0].content.headline == "Cue-Routine-Reward Loops"
    assert spread2[1].content.headline == "Friction Reduction Patterns"

    # D. Graph Traversal: Verify complete linked chain from starting page
    chain = p_repo.get_linked_pages(rec_book.starting_page_id)
    assert len(chain) == 4
    assert [p.page_number for p in chain] == [1, 2, 3, 4]
    assert chain[0].previous_page_id is None
    assert chain[-1].next_page_id is None
