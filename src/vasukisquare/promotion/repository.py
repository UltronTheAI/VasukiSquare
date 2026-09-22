"""MongoDB persistence repository for promotion tracking statistics and generated posts."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from vasukisquare.promotion.models import PromotionPost, PromotionStats, PromotionStatus

logger = logging.getLogger("vasukisquare.promotion.repository")


class PromotionRepository:
    """Repository managing promotion_stats and promotion_posts collections."""

    def __init__(
        self,
        db: Database,
        stats_collection_name: str = "promotion_stats",
        posts_collection_name: str = "promotion_posts",
    ):
        self.db = db
        self.stats_collection: Collection = db[stats_collection_name]
        self.posts_collection: Collection = db[posts_collection_name]

    def create_indexes(self) -> None:
        """Create required indexes on promotion collections."""
        try:
            self.stats_collection.create_indexes([
                IndexModel(
                    [("book_id", ASCENDING), ("platform", ASCENDING)],
                    unique=True,
                    name="promo_stats_book_platform_unique",
                ),
                IndexModel(
                    [("platform", ASCENDING), ("promotion_count", ASCENDING)],
                    name="promo_stats_platform_count_idx",
                ),
                IndexModel(
                    [("platform", ASCENDING), ("next_eligible_at", ASCENDING)],
                    name="promo_stats_platform_eligible_idx",
                ),
            ])
            self.posts_collection.create_indexes([
                IndexModel(
                    [("campaign_run_id", ASCENDING), ("book_id", ASCENDING), ("platform", ASCENDING)],
                    unique=True,
                    name="promo_posts_campaign_book_platform_unique",
                ),
                IndexModel(
                    [("book_id", ASCENDING), ("created_at", DESCENDING)],
                    name="promo_posts_book_idx",
                ),
                IndexModel(
                    [("platform", ASCENDING), ("status", ASCENDING)],
                    name="promo_posts_platform_status_idx",
                ),
                IndexModel([("status", ASCENDING)], name="promo_posts_status_idx"),
                IndexModel([("campaign_run_id", ASCENDING)], name="promo_posts_campaign_idx"),
                IndexModel([("generated_at", DESCENDING)], name="promo_posts_generated_idx"),
            ])
            logger.debug("[PromotionRepository] Indexes initialized successfully.")
        except Exception as e:
            logger.warning(f"[PromotionRepository] Error creating indexes: {e}")

    # =========================================================================
    # Promotion Stats Operations
    # =========================================================================

    def get_stats(self, book_id: str, platform: str) -> Optional[PromotionStats]:
        """Fetch tracking stats for a book on a platform."""
        doc = self.stats_collection.find_one({"book_id": book_id, "platform": platform.lower()})
        if not doc:
            return None
        doc.pop("_id", None)
        return PromotionStats(**doc)

    def get_or_create_stats(self, book_id: str, book_slug: str, platform: str) -> PromotionStats:
        """Fetch stats or initialize an empty tracking record if none exists."""
        stats = self.get_stats(book_id, platform)
        if stats:
            return stats
        
        new_stats = PromotionStats(
            book_id=book_id,
            book_slug=book_slug,
            platform=platform.lower(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        data = new_stats.model_dump()
        data["_id"] = new_stats.id
        try:
            self.stats_collection.insert_one(data)
            return new_stats
        except Exception:
            # Handle race condition if created concurrently
            found = self.get_stats(book_id, platform)
            if found:
                return found
            return new_stats

    def get_stats_for_books(self, book_ids: List[str], platform: str) -> Dict[str, PromotionStats]:
        """Batch fetch promotion stats for a list of book IDs on a given platform."""
        if not book_ids:
            return {}
        cursor = self.stats_collection.find({
            "book_id": {"$in": book_ids},
            "platform": platform.lower(),
        })
        results: Dict[str, PromotionStats] = {}
        for doc in cursor:
            doc.pop("_id", None)
            stats = PromotionStats(**doc)
            results[stats.book_id] = stats
        return results

    def update_stats_on_success(
        self,
        book_id: str,
        book_slug: str,
        platform: str,
        cooldown_hours: int = 72,
        timestamp: Optional[datetime] = None,
    ) -> PromotionStats:
        """Update stats document after a successful post publication."""
        self.get_or_create_stats(book_id, book_slug, platform)
        ts = timestamp or datetime.now(timezone.utc)
        next_eligible = ts + timedelta(hours=cooldown_hours)
        now = datetime.now(timezone.utc)

        update_ops = {
            "$inc": {
                "promotion_count": 1,
                "successful_posts": 1,
            },
            "$set": {
                "book_slug": book_slug,
                "last_promoted_at": ts,
                "next_eligible_at": next_eligible,
                "updated_at": now,
            },
        }

        doc = self.stats_collection.find_one_and_update(
            {"book_id": book_id, "platform": platform.lower()},
            update_ops,
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            # Fallback for mock environments returning None before update
            doc = self.stats_collection.find_one({"book_id": book_id, "platform": platform.lower()})
        doc.pop("_id", None)
        return PromotionStats(**doc)

    def update_stats_on_failure(
        self,
        book_id: str,
        book_slug: str,
        platform: str,
        timestamp: Optional[datetime] = None,
    ) -> PromotionStats:
        """Update stats document after a failed post publication."""
        self.get_or_create_stats(book_id, book_slug, platform)
        now = timestamp or datetime.now(timezone.utc)
        update_ops = {
            "$inc": {
                "failed_posts": 1,
            },
            "$set": {
                "book_slug": book_slug,
                "updated_at": now,
            },
        }

        doc = self.stats_collection.find_one_and_update(
            {"book_id": book_id, "platform": platform.lower()},
            update_ops,
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            # Fallback for mock environments
            doc = self.stats_collection.find_one({"book_id": book_id, "platform": platform.lower()})
        doc.pop("_id", None)
        return PromotionStats(**doc)

    # =========================================================================
    # Promotion Posts Operations
    # =========================================================================

    def record_generation(self, post: PromotionPost) -> PromotionPost:
        """Persist or upsert a newly generated promotion post before attempting publication."""
        data = post.model_dump()
        data["_id"] = post.id
        filter_query = {
            "campaign_run_id": post.campaign_run_id,
            "book_id": post.book_id,
            "platform": post.platform,
        }
        
        # Upsert ensures idempotency if rerun
        existing = self.posts_collection.find_one(filter_query)
        if existing:
            # If already published, do not overwrite status
            if existing.get("status") == PromotionStatus.PUBLISHED.value:
                existing.pop("_id", None)
                return PromotionPost(**existing)
            self.posts_collection.update_one(filter_query, {"$set": data})
            return post

        self.posts_collection.insert_one(data)
        return post

    def get_post_by_id(self, post_id: str) -> Optional[PromotionPost]:
        """Fetch a promotion post by its primary ID."""
        doc = self.posts_collection.find_one({"_id": post_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return PromotionPost(**doc)

    def get_post_for_campaign(
        self, campaign_run_id: str, book_id: str, platform: str
    ) -> Optional[PromotionPost]:
        """Fetch an existing post record for a campaign run and book."""
        doc = self.posts_collection.find_one({
            "campaign_run_id": campaign_run_id,
            "book_id": book_id,
            "platform": platform.lower(),
        })
        if not doc:
            return None
        doc.pop("_id", None)
        return PromotionPost(**doc)

    def record_publication_start(self, post_id: str) -> Optional[PromotionPost]:
        """Mark post as currently publishing and increment attempt counter."""
        now = datetime.now(timezone.utc)
        doc = self.posts_collection.find_one_and_update(
            {"_id": post_id},
            {
                "$set": {
                    "status": PromotionStatus.PUBLISHING.value,
                    "updated_at": now,
                },
                "$inc": {"publish_attempts": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return None
        doc.pop("_id", None)
        return PromotionPost(**doc)

    def record_publication_success(
        self,
        post_id: str,
        external_post_id: str,
        external_url: str,
        published_at: Optional[datetime] = None,
    ) -> Optional[PromotionPost]:
        """Mark post as successfully published with external references."""
        now = published_at or datetime.now(timezone.utc)
        doc = self.posts_collection.find_one_and_update(
            {"_id": post_id},
            {
                "$set": {
                    "status": PromotionStatus.PUBLISHED.value,
                    "external_post_id": external_post_id,
                    "external_url": external_url,
                    "published_at": now,
                    "last_error": None,
                    "updated_at": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return None
        doc.pop("_id", None)
        return PromotionPost(**doc)

    def record_publication_failure(
        self,
        post_id: str,
        error_message: str,
    ) -> Optional[PromotionPost]:
        """Mark post as failed with error details."""
        now = datetime.now(timezone.utc)
        doc = self.posts_collection.find_one_and_update(
            {"_id": post_id},
            {
                "$set": {
                    "status": PromotionStatus.FAILED.value,
                    "last_error": error_message,
                    "updated_at": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return None
        doc.pop("_id", None)
        return PromotionPost(**doc)

    def list_posts(
        self,
        book_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        campaign_run_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[PromotionPost]:
        """List promotion posts matching optional filter criteria."""
        query: Dict[str, Any] = {}
        if book_id:
            query["book_id"] = book_id
        if platform:
            query["platform"] = platform.lower()
        if status:
            query["status"] = status.lower()
        if campaign_run_id:
            query["campaign_run_id"] = campaign_run_id

        cursor = self.posts_collection.find(query).sort("generated_at", DESCENDING).limit(limit)
        posts: List[PromotionPost] = []
        for doc in cursor:
            doc.pop("_id", None)
            posts.append(PromotionPost(**doc))
        return posts
