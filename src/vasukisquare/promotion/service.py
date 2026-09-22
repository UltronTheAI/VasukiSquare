"""Promotion campaign orchestration service coordinating selection, generation, and multi-platform publishing."""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pymongo.database import Database

from vasukisquare.book.models import Book, PublicationStatus, PublicationVisibility
from vasukisquare.config import Settings, get_settings
from vasukisquare.database.connection import DatabaseManager
from vasukisquare.database.repository import BookRepository
from vasukisquare.promotion.models import (
    CampaignSummary,
    PromotionPlatform,
    PromotionPost,
    PromotionStats,
    PromotionStatus,
)
from vasukisquare.promotion.publishers.base import PromotionPublisher
from vasukisquare.promotion.publishers.devto import DevToPublisher
from vasukisquare.promotion.repository import PromotionRepository
from vasukisquare.promotion.selector import BookSelector
from vasukisquare.promotion.writer import PromotionWriter

logger = logging.getLogger("vasukisquare.promotion.service")


class PromotionService:
    """End-to-end orchestration service for automated ebook promotion campaigns."""

    def __init__(
        self,
        db: Optional[Database] = None,
        settings: Optional[Settings] = None,
        repository: Optional[PromotionRepository] = None,
        selector: Optional[BookSelector] = None,
        writer: Optional[PromotionWriter] = None,
        publishers: Optional[Dict[str, PromotionPublisher]] = None,
        book_repo: Optional[BookRepository] = None,
    ):
        self.settings = settings or get_settings()
        self.db = db if db is not None else DatabaseManager(settings=self.settings).db
        
        self.repository = repository or PromotionRepository(
            db=self.db,
            stats_collection_name=self.settings.promotion_stats_collection,
            posts_collection_name=self.settings.promotion_post_collection,
        )
        self.book_repo = book_repo or BookRepository(self.db)
        self.selector = selector or BookSelector(settings=self.settings)
        self.writer = writer or PromotionWriter(settings=self.settings)

        # Initialize publishers registry
        if publishers is not None:
            self.publishers = publishers
        else:
            self.publishers = {
                PromotionPlatform.DEVTO.value: DevToPublisher(settings=self.settings)
            }

    def register_publisher(self, platform_name: str, publisher: PromotionPublisher) -> None:
        """Register a new external promotion platform publisher adapter."""
        self.publishers[platform_name.lower()] = publisher

    def _fetch_all_public_books(self) -> List[Book]:
        """Fetch all public published books from MongoDB."""
        filter_q = {
            "publication.status": PublicationStatus.PUBLISHED.value,
            "publication.visibility": PublicationVisibility.PUBLIC.value,
        }
        cursor = self.book_repo.collection.find(filter_q)
        books: List[Book] = []
        for doc in cursor:
            doc.pop("_id", None)
            try:
                books.append(Book(**doc))
            except Exception as e:
                logger.warning(f"[PromotionService] Skipping unparseable book document {doc.get('id')}: {e}")
        return books

    async def run_campaign(
        self,
        count: Optional[int] = None,
        platform: Optional[str] = None,
        dry_run: Optional[bool] = None,
        book_id_or_slug: Optional[str] = None,
        campaign_run_id: Optional[str] = None,
    ) -> CampaignSummary:
        """Execute a full promotional campaign run."""
        start_time = datetime.now(timezone.utc)
        target_platform = (platform or self.settings.promotion_platform or "devto").lower()
        is_dry_run = dry_run if dry_run is not None else self.settings.promotion_dry_run
        target_count = count if count is not None else self.settings.promotion_posts_per_run
        
        run_id = (
            campaign_run_id
            or f"camp_{start_time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        )

        logger.info(
            f"==========================================================\n"
            f"[PROMOTION CAMPAIGN START]\n"
            f" Campaign Run ID: {run_id}\n"
            f" Platform:        {target_platform}\n"
            f" Dry Run:         {is_dry_run}\n"
            f" Target Count:    {target_count}\n"
            f" Specific Book:   {book_id_or_slug or 'None (Auto-selection)'}\n"
            f"=========================================================="
        )

        # 1. Ensure indexes exist
        self.repository.create_indexes()

        summary = CampaignSummary(
            campaign_run_id=run_id,
            platform=target_platform,
            dry_run=is_dry_run,
            started_at=start_time,
            completed_at=start_time,
        )

        # 2. Select eligible books (or resume existing campaign run)
        selected_books: List[Book] = []
        if book_id_or_slug:
            # Single book targeted mode
            book = self.book_repo.get_by_id(book_id_or_slug) or self.book_repo.get_by_slug(book_id_or_slug)
            if not book:
                err_msg = f"Book '{book_id_or_slug}' was not found in MongoDB."
                logger.error(f"[PromotionService] {err_msg}")
                summary.failures.append({"book_id": book_id_or_slug, "error": err_msg})
                summary.completed_at = datetime.now(timezone.utc)
                return summary
            selected_books = [book]
        else:
            # Check if this campaign run already has recorded posts (e.g. action retry / resume)
            existing_campaign_posts = self.repository.list_posts(
                campaign_run_id=run_id,
                platform=target_platform,
            )
            if existing_campaign_posts:
                logger.info(
                    f"[PromotionService:RESUME] Resuming existing campaign run '{run_id}' "
                    f"with {len(existing_campaign_posts)} existing post(s)."
                )
                seen_book_ids = set()
                for cp in existing_campaign_posts:
                    if cp.book_id not in seen_book_ids:
                        b = self.book_repo.get_by_id(cp.book_id) or self.book_repo.get_by_slug(cp.book_slug)
                        if b:
                            selected_books.append(b)
                            seen_book_ids.add(cp.book_id)

            if not selected_books:
                all_public_books = self._fetch_all_public_books()
                if not all_public_books:
                    logger.warning("[PromotionService] No published public books found in MongoDB.")
                    summary.completed_at = datetime.now(timezone.utc)
                    return summary

                book_ids = [b.id for b in all_public_books]
                stats_map = self.repository.get_stats_for_books(book_ids, target_platform)
                selected_books = self.selector.select_books(
                    books=all_public_books,
                    stats_by_book_id=stats_map,
                    count=target_count,
                    current_time=start_time,
                )

        summary.selected_count = len(selected_books)
        summary.selected_books = [
            {"id": b.id, "slug": b.slug, "title": b.title} for b in selected_books
        ]
        logger.info(
            f"[PromotionService] Selected {len(selected_books)} book(s) for promotion: "
            f"{[b.slug for b in selected_books]}"
        )

        if not selected_books:
            logger.info("[PromotionService] No eligible books available to promote at this time.")
            summary.completed_at = datetime.now(timezone.utc)
            return summary

        # 3. Process each selected book independently
        publisher = self.publishers.get(target_platform)

        for book in selected_books:
            logger.info(f"\n--- Processing Book: '{book.title}' (slug: {book.slug}) ---")

            # Check existing post for this campaign run (idempotency check)
            existing_post = self.repository.get_post_for_campaign(
                campaign_run_id=run_id,
                book_id=book.id,
                platform=target_platform,
            )

            post: Optional[PromotionPost] = None

            if existing_post:
                if existing_post.status == PromotionStatus.PUBLISHED:
                    logger.info(
                        f"[PromotionService:IDEMPOTENT] Post already published for book='{book.slug}' "
                        f"in campaign='{run_id}'. Skipping duplication."
                    )
                    summary.posts.append(existing_post)
                    summary.published_count += 1
                    continue
                else:
                    logger.info(
                        f"[PromotionService:REUSE] Found existing post in state='{existing_post.status}' "
                        f"for book='{book.slug}'. Resuming."
                    )
                    post = existing_post
            else:
                # Generate new article using Groq LLM
                try:
                    post = await self.writer.generate_article(
                        book=book,
                        campaign_run_id=run_id,
                        platform=target_platform,
                    )
                    summary.generated_count += 1
                    # Persist generated post prior to attempting publication
                    post = self.repository.record_generation(post)
                except Exception as e:
                    err_msg = f"Generation failed for book '{book.slug}': {e}"
                    logger.error(f"[PromotionService:GEN_FAILED] {err_msg}")
                    summary.failed_count += 1
                    summary.failures.append({"book_id": book.id, "book_slug": book.slug, "error": err_msg})
                    continue

            summary.posts.append(post)

            # 4. Publish post if not in dry-run mode
            if is_dry_run:
                logger.info(
                    f"[PromotionService:DRY_RUN] Successfully generated and stored post for '{book.slug}'. "
                    f"Skipping publication to {target_platform}."
                )
                continue

            if not publisher:
                err_msg = f"No publisher registered for platform '{target_platform}'."
                logger.error(f"[PromotionService:NO_PUBLISHER] {err_msg}")
                self.repository.record_publication_failure(post.id, err_msg)
                summary.failed_count += 1
                summary.failures.append({"book_id": book.id, "book_slug": book.slug, "error": err_msg})
                continue

            # Execute publication with atomic state transition
            self.repository.record_publication_start(post.id)
            try:
                pub_result = await publisher.publish(post)
                if pub_result.success:
                    updated_post = self.repository.record_publication_success(
                        post_id=post.id,
                        external_post_id=pub_result.external_post_id or "",
                        external_url=pub_result.external_url or "",
                    )
                    self.repository.update_stats_on_success(
                        book_id=book.id,
                        book_slug=book.slug,
                        platform=target_platform,
                        cooldown_hours=self.settings.promotion_book_cooldown_hours,
                    )
                    summary.published_count += 1
                    if updated_post:
                        # Replace with updated instance in summary
                        summary.posts[-1] = updated_post
                    logger.info(
                        f"[PromotionService:PUBLISHED] Successfully published '{book.slug}' to {target_platform}! "
                        f"URL: {pub_result.external_url}"
                    )
                else:
                    err_msg = pub_result.error_message or "Unknown publication error"
                    self.repository.record_publication_failure(post.id, err_msg)
                    self.repository.update_stats_on_failure(book.id, book.slug, target_platform)
                    summary.failed_count += 1
                    summary.failures.append({"book_id": book.id, "book_slug": book.slug, "error": err_msg})
                    logger.error(
                        f"[PromotionService:PUB_FAILED] Publication failed for '{book.slug}': {err_msg}"
                    )
            except Exception as e:
                err_msg = f"Unexpected exception publishing '{book.slug}': {e}"
                self.repository.record_publication_failure(post.id, err_msg)
                self.repository.update_stats_on_failure(book.id, book.slug, target_platform)
                summary.failed_count += 1
                summary.failures.append({"book_id": book.id, "book_slug": book.slug, "error": err_msg})
                logger.error(f"[PromotionService:EXCEPTION] {err_msg}")

        summary.completed_at = datetime.now(timezone.utc)
        duration_sec = (summary.completed_at - summary.started_at).total_seconds()
        logger.info(
            f"\n==========================================================\n"
            f"[PROMOTION CAMPAIGN COMPLETE]\n"
            f" Duration:        {duration_sec:.2f}s\n"
            f" Selected:        {summary.selected_count}\n"
            f" Generated:       {summary.generated_count}\n"
            f" Published:       {summary.published_count}\n"
            f" Failed:          {summary.failed_count}\n"
            f"=========================================================="
        )
        return summary
