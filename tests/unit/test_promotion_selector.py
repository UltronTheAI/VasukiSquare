"""Unit tests for BookSelector fair weighted selection and cooldown filtering."""

from datetime import datetime, timedelta, timezone
import random
import pytest

from vasukisquare.book.models import (
    Book,
    PublicationInfo,
    PublicationStatus,
    PublicationVisibility,
)
from vasukisquare.promotion.models import PromotionStats
from vasukisquare.promotion.selector import BookSelector


def make_book(
    book_id: str,
    slug: str,
    status: PublicationStatus = PublicationStatus.PUBLISHED,
    visibility: PublicationVisibility = PublicationVisibility.PUBLIC,
) -> Book:
    """Helper to create test Book instances."""
    return Book(
        id=book_id,
        title=f"Title {slug}",
        slug=slug,
        prompt="Test prompt",
        description="Test description",
        publication=PublicationInfo(status=status, visibility=visibility),
    )


def test_is_eligible_status_and_visibility():
    selector = BookSelector(cooldown_hours=72)
    now = datetime.now(timezone.utc)

    # Valid published & public
    b1 = make_book("b1", "valid-slug")
    assert selector.is_eligible(b1, None, current_time=now) is True

    # Draft
    b2 = make_book("b2", "draft-slug", status=PublicationStatus.DRAFT)
    assert selector.is_eligible(b2, None, current_time=now) is False

    # Private
    b3 = make_book("b3", "priv-slug", visibility=PublicationVisibility.PRIVATE)
    assert selector.is_eligible(b3, None, current_time=now) is False

    # Missing / empty slug
    b4 = make_book("b4", "some-slug")
    b4.slug = ""
    assert selector.is_eligible(b4, None, current_time=now) is False


def test_is_eligible_cooldown():
    selector = BookSelector(cooldown_hours=72)
    now = datetime.now(timezone.utc)
    book = make_book("b1", "cool-book")

    # In cooldown (promoted 10 hours ago)
    stats_recent = PromotionStats(
        book_id="b1",
        book_slug="cool-book",
        promotion_count=1,
        last_promoted_at=now - timedelta(hours=10),
        next_eligible_at=now + timedelta(hours=62),
    )
    assert selector.is_eligible(book, stats_recent, current_time=now) is False

    # Cooldown expired (promoted 80 hours ago)
    stats_expired = PromotionStats(
        book_id="b1",
        book_slug="cool-book",
        promotion_count=1,
        last_promoted_at=now - timedelta(hours=80),
        next_eligible_at=now - timedelta(hours=8),
    )
    assert selector.is_eligible(book, stats_expired, current_time=now) is True


def test_calculate_weight_prefers_lower_promotion_count():
    selector = BookSelector()
    now = datetime.now(timezone.utc)
    book = make_book("b1", "book-1")

    # Zero promotions
    stats_zero = PromotionStats(book_id="b1", book_slug="book-1", promotion_count=0)
    w0 = selector.calculate_weight(book, stats_zero, current_time=now)

    # 1 promotion
    stats_one = PromotionStats(
        book_id="b1",
        book_slug="book-1",
        promotion_count=1,
        last_promoted_at=now - timedelta(days=5),
    )
    w1 = selector.calculate_weight(book, stats_one, current_time=now)

    # 5 promotions
    stats_five = PromotionStats(
        book_id="b1",
        book_slug="book-1",
        promotion_count=5,
        last_promoted_at=now - timedelta(days=5),
    )
    w5 = selector.calculate_weight(book, stats_five, current_time=now)

    assert w0 > w1 > w5


def test_select_books_fewer_than_target():
    selector = BookSelector()
    books = [
        make_book("b1", "book-1"),
        make_book("b2", "book-2"),
    ]
    stats = {}
    selected = selector.select_books(books, stats, count=3)
    assert len(selected) == 2
    assert {b.id for b in selected} == {"b1", "b2"}


def test_select_books_all_on_cooldown():
    selector = BookSelector(cooldown_hours=72)
    now = datetime.now(timezone.utc)
    books = [
        make_book("b1", "book-1"),
        make_book("b2", "book-2"),
    ]
    stats = {
        "b1": PromotionStats(
            book_id="b1",
            book_slug="book-1",
            next_eligible_at=now + timedelta(hours=24),
        ),
        "b2": PromotionStats(
            book_id="b2",
            book_slug="book-2",
            next_eligible_at=now + timedelta(hours=48),
        ),
    }
    selected = selector.select_books(books, stats, count=3, current_time=now)
    assert len(selected) == 0


def test_select_books_fair_weighted_distribution():
    # 5 books with 0 promotions, 5 books with 10 promotions
    rng = random.Random(42)
    selector = BookSelector(rng=rng)
    now = datetime.now(timezone.utc)

    books = [make_book(f"fresh_{i}", f"fresh-{i}") for i in range(5)] + [
        make_book(f"heavy_{i}", f"heavy-{i}") for i in range(5)
    ]
    stats = {}
    for i in range(5):
        stats[f"fresh_{i}"] = PromotionStats(book_id=f"fresh_{i}", book_slug=f"fresh-{i}", promotion_count=0)
        stats[f"heavy_{i}"] = PromotionStats(
            book_id=f"heavy_{i}",
            book_slug=f"heavy-{i}",
            promotion_count=10,
            last_promoted_at=now - timedelta(days=10),
            next_eligible_at=now - timedelta(days=7),
        )

    fresh_selected_count = 0
    total_samples = 100
    for seed in range(total_samples):
        sel = BookSelector(rng=random.Random(seed))
        chosen = sel.select_books(books, stats, count=3, current_time=now)
        assert len(chosen) == 3
        fresh_selected_count += sum(1 for b in chosen if b.id.startswith("fresh_"))

    # Fresh books should constitute the clear majority of selections due to higher weights
    assert fresh_selected_count > (total_samples * 3 * 0.65)
