"""Unit tests for PromotionService campaign orchestration and resilience."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from tests.integration.test_database import create_mock_db
from vasukisquare.book.models import (
    Book,
    PublicationInfo,
    PublicationStatus,
    PublicationVisibility,
)
from vasukisquare.config import Settings
from vasukisquare.database.repository import BookRepository
from vasukisquare.promotion.models import (
    GeneratedArticleContent,
    PromotionPost,
    PromotionStatus,
)
from vasukisquare.promotion.publishers.base import PromotionPublisher, PublishResult
from vasukisquare.promotion.repository import PromotionRepository
from vasukisquare.promotion.selector import BookSelector
from vasukisquare.promotion.service import PromotionService
from vasukisquare.promotion.writer import PromotionWriter


def make_published_book(book_id: str, slug: str, title: str) -> Book:
    return Book(
        id=book_id,
        slug=slug,
        title=title,
        prompt=f"Topic for {title}",
        description=f"Overview of {title}",
        publication=PublicationInfo(
            status=PublicationStatus.PUBLISHED,
            visibility=PublicationVisibility.PUBLIC,
        ),
    )


@pytest.fixture
def mock_db():
    return create_mock_db()


@pytest.fixture
def test_setup(mock_db):
    settings = Settings(
        app_env="test",
        publication_base_url="https://vasukisquare.cc",
        promotion_book_cooldown_hours=72,
        promotion_posts_per_run=3,
        devto_api_key="test_key",
    )

    book_repo = BookRepository(mock_db)
    # Insert 4 test books
    b1 = book_repo.create(make_published_book("b1", "distributed-consensus", "Distributed Consensus"))
    b2 = book_repo.create(make_published_book("b2", "rust-async-io", "Async IO in Rust"))
    b3 = book_repo.create(make_published_book("b3", "graphql-federation", "GraphQL Federation"))
    b4 = book_repo.create(make_published_book("b4", "ebpf-observability", "eBPF Observability"))

    promo_repo = PromotionRepository(mock_db)

    # Mock Writer
    mock_writer = MagicMock(spec=PromotionWriter)
    async def fake_generate(book, campaign_run_id, platform="devto"):
        return PromotionPost(
            campaign_run_id=campaign_run_id,
            book_id=book.id,
            book_slug=book.slug,
            platform=platform,
            title=f"Exploring {book.title}",
            body_markdown=f"# {book.title}\n\nTechnical insights.\n\nhttps://vasukisquare.cc/book/{book.slug}",
            tags=["tech", "coding"],
            canonical_url=f"https://vasukisquare.cc/book/{book.slug}",
            status=PromotionStatus.GENERATED,
            generation_model="mock-model",
        )
    mock_writer.generate_article = AsyncMock(side_effect=fake_generate)

    # Mock Publisher
    mock_publisher = MagicMock(spec=PromotionPublisher)
    mock_publisher.platform_name.return_value = "devto"
    async def fake_publish(post):
        return PublishResult(
            success=True,
            external_post_id=f"devto_{post.book_id}",
            external_url=f"https://dev.to/vasukisquare/{post.book_slug}-devto_{post.book_id}",
        )
    mock_publisher.publish = AsyncMock(side_effect=fake_publish)

    service = PromotionService(
        db=mock_db,
        settings=settings,
        repository=promo_repo,
        book_repo=book_repo,
        selector=BookSelector(settings=settings),
        writer=mock_writer,
        publishers={"devto": mock_publisher},
    )

    return {
        "service": service,
        "promo_repo": promo_repo,
        "mock_writer": mock_writer,
        "mock_publisher": mock_publisher,
        "books": [b1, b2, b3, b4],
    }


@pytest.mark.asyncio
async def test_full_campaign_live_run(test_setup):
    service = test_setup["service"]
    promo_repo = test_setup["promo_repo"]

    summary = await service.run_campaign(count=3, dry_run=False, campaign_run_id="camp_live_1")

    assert summary.selected_count == 3
    assert summary.generated_count == 3
    assert summary.published_count == 3
    assert summary.failed_count == 0
    assert len(summary.posts) == 3

    # Check database persistence of posts
    for p in summary.posts:
        saved_post = promo_repo.get_post_by_id(p.id)
        assert saved_post is not None
        assert saved_post.status == PromotionStatus.PUBLISHED
        assert saved_post.external_url.startswith("https://dev.to/")

        # Check tracking stats
        stats = promo_repo.get_stats(p.book_id, "devto")
        assert stats is not None
        assert stats.promotion_count == 1
        assert stats.successful_posts == 1
        assert stats.last_promoted_at is not None
        assert stats.next_eligible_at is not None


@pytest.mark.asyncio
async def test_dry_run_campaign(test_setup):
    service = test_setup["service"]
    promo_repo = test_setup["promo_repo"]
    mock_pub = test_setup["mock_publisher"]

    summary = await service.run_campaign(count=2, dry_run=True, campaign_run_id="camp_dry_1")

    assert summary.dry_run is True
    assert summary.selected_count == 2
    assert summary.generated_count == 2
    assert summary.published_count == 0
    assert summary.failed_count == 0

    # Publisher must NOT have been invoked
    mock_pub.publish.assert_not_called()

    # Posts must still be persisted as GENERATED
    for p in summary.posts:
        saved_post = promo_repo.get_post_by_id(p.id)
        assert saved_post is not None
        assert saved_post.status == PromotionStatus.GENERATED

        # Stats should not count dry run as a successful external promotion
        stats = promo_repo.get_stats(p.book_id, "devto")
        assert stats is None or stats.promotion_count == 0


@pytest.mark.asyncio
async def test_idempotent_campaign_rerun(test_setup):
    service = test_setup["service"]
    mock_pub = test_setup["mock_publisher"]

    # 1. First run publishes 3 books
    summary1 = await service.run_campaign(count=3, dry_run=False, campaign_run_id="camp_rerun")
    assert summary1.published_count == 3
    assert mock_pub.publish.call_count == 3

    # 2. Rerunning with the exact same campaign ID
    summary2 = await service.run_campaign(count=3, dry_run=False, campaign_run_id="camp_rerun")
    assert summary2.published_count == 3
    # Call count should not increase because already published posts were safely skipped
    assert mock_pub.publish.call_count == 3


@pytest.mark.asyncio
async def test_partial_failure_tolerance(test_setup):
    service = test_setup["service"]
    promo_repo = test_setup["promo_repo"]
    mock_pub = test_setup["mock_publisher"]

    # Mock publisher to fail on book 'b2' but succeed on others
    async def flawed_publish(post):
        if post.book_id == "b2":
            return PublishResult(success=False, error_message="HTTP 422: Rate limit reached")
        return PublishResult(
            success=True,
            external_post_id=f"devto_{post.book_id}",
            external_url=f"https://dev.to/vasukisquare/{post.book_slug}-devto_{post.book_id}",
        )
    mock_pub.publish = AsyncMock(side_effect=flawed_publish)

    service.selector.select_books = MagicMock(
        return_value=[test_setup["books"][0], test_setup["books"][1], test_setup["books"][2]]
    )

    summary = await service.run_campaign(count=3, dry_run=False, campaign_run_id="camp_partial_fail")

    assert summary.selected_count == 3
    assert summary.published_count == 2
    assert summary.failed_count == 1
    assert len(summary.failures) == 1
    assert summary.failures[0]["book_id"] == "b2"

    # Failed post recorded in DB
    failed_posts = promo_repo.list_posts(book_id="b2")
    assert len(failed_posts) > 0
    assert failed_posts[0].status == PromotionStatus.FAILED
    assert "Rate limit" in failed_posts[0].last_error


@pytest.mark.asyncio
async def test_target_specific_book(test_setup):
    service = test_setup["service"]
    summary = await service.run_campaign(book_id_or_slug="ebpf-observability", dry_run=False, campaign_run_id="camp_single")

    assert summary.selected_count == 1
    assert summary.selected_books[0]["slug"] == "ebpf-observability"
    assert summary.published_count == 1

