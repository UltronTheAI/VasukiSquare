"""Unit tests for PromotionRepository operations and stats management."""

from datetime import datetime, timedelta, timezone
import pytest

from tests.integration.test_database import create_mock_db
from vasukisquare.promotion.models import (
    PromotionPost,
    PromotionStats,
    PromotionStatus,
)
from vasukisquare.promotion.repository import PromotionRepository


@pytest.fixture
def mock_db():
    return create_mock_db()


@pytest.fixture
def promo_repo(mock_db):
    return PromotionRepository(mock_db, "promotion_stats", "promotion_posts")


def test_get_or_create_stats(promo_repo):
    stats = promo_repo.get_or_create_stats("book-100", "my-first-book", "devto")
    assert stats is not None
    assert stats.book_id == "book-100"
    assert stats.book_slug == "my-first-book"
    assert stats.platform == "devto"
    assert stats.promotion_count == 0

    # Getting again returns existing document
    stats2 = promo_repo.get_stats("book-100", "devto")
    assert stats2 is not None
    assert stats2.id == stats.id


def test_update_stats_on_success(promo_repo):
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    updated = promo_repo.update_stats_on_success(
        book_id="book-100",
        book_slug="my-first-book",
        platform="devto",
        cooldown_hours=72,
        timestamp=now,
    )
    assert updated.promotion_count == 1
    assert updated.successful_posts == 1
    assert updated.last_promoted_at == now
    assert updated.next_eligible_at == now + timedelta(hours=72)

    # Second success
    later = now + timedelta(days=5)
    updated2 = promo_repo.update_stats_on_success(
        book_id="book-100",
        book_slug="my-first-book",
        platform="devto",
        cooldown_hours=72,
        timestamp=later,
    )
    assert updated2.promotion_count == 2
    assert updated2.successful_posts == 2
    assert updated2.last_promoted_at == later


def test_update_stats_on_failure(promo_repo):
    updated = promo_repo.update_stats_on_failure(
        book_id="book-200",
        book_slug="failed-book",
        platform="devto",
    )
    assert updated.failed_posts == 1
    assert updated.promotion_count == 0


def test_get_stats_for_books(promo_repo):
    promo_repo.update_stats_on_success("b1", "slug-1", "devto")
    promo_repo.update_stats_on_success("b2", "slug-2", "devto")

    stats_map = promo_repo.get_stats_for_books(["b1", "b2", "b3"], "devto")
    assert len(stats_map) == 2
    assert "b1" in stats_map
    assert "b2" in stats_map
    assert "b3" not in stats_map


def test_record_generation_and_idempotency(promo_repo):
    post = PromotionPost(
        campaign_run_id="camp_123",
        book_id="book-1",
        book_slug="book-one",
        platform="devto",
        title="Deep Dive into Distributed Systems",
        body_markdown="# Distributed Systems...",
        tags=["python", "systems"],
        canonical_url="https://vasukisquare.cc/book/book-one",
    )
    saved = promo_repo.record_generation(post)
    assert saved.id == post.id

    fetched = promo_repo.get_post_by_id(post.id)
    assert fetched is not None
    assert fetched.title == post.title
    assert fetched.status == PromotionStatus.GENERATED

    # Re-recording with modified title updates the record
    post.title = "Updated Title"
    saved_again = promo_repo.record_generation(post)
    assert saved_again.title == "Updated Title"


def test_publication_lifecycle_state_transitions(promo_repo):
    post = PromotionPost(
        campaign_run_id="camp_lifecycle",
        book_id="book-life",
        book_slug="life-cycle",
        platform="devto",
        title="Title",
        body_markdown="Body",
        canonical_url="https://vasukisquare.cc/book/life-cycle",
    )
    promo_repo.record_generation(post)

    # 1. Start publication
    started = promo_repo.record_publication_start(post.id)
    assert started.status == PromotionStatus.PUBLISHING
    assert started.publish_attempts == 1

    # 2. Complete with success
    pub_time = datetime(2026, 9, 22, 14, 30, 0, tzinfo=timezone.utc)
    success = promo_repo.record_publication_success(
        post_id=post.id,
        external_post_id="devto_98765",
        external_url="https://dev.to/user/post-98765",
        published_at=pub_time,
    )
    assert success.status == PromotionStatus.PUBLISHED
    assert success.external_post_id == "devto_98765"
    assert success.external_url == "https://dev.to/user/post-98765"
    assert success.published_at == pub_time

    # 3. Test failure recording on another post
    failed_post = PromotionPost(
        campaign_run_id="camp_fail",
        book_id="book-fail",
        book_slug="fail-slug",
        platform="devto",
        title="Fail",
        body_markdown="Body",
        canonical_url="https://vasukisquare.cc/book/fail-slug",
    )
    promo_repo.record_generation(failed_post)
    failed = promo_repo.record_publication_failure(failed_post.id, "HTTP 401 Unauthorized")
    assert failed.status == PromotionStatus.FAILED
    assert failed.last_error == "HTTP 401 Unauthorized"

