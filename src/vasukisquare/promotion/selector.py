"""Fair weighted book selection algorithm for automated promotion campaigns."""

from datetime import datetime, timezone
import logging
import math
import random
from typing import Dict, List, Optional

from vasukisquare.book.models import Book, PublicationStatus, PublicationVisibility
from vasukisquare.config import Settings, get_settings
from vasukisquare.promotion.models import PromotionStats

logger = logging.getLogger("vasukisquare.promotion.selector")


class BookSelector:
    """Selects eligible published ebooks for promotional campaigns using fair weighted sampling."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        cooldown_hours: Optional[int] = None,
        rng: Optional[random.Random] = None,
    ):
        self.settings = settings or get_settings()
        self.cooldown_hours = (
            cooldown_hours
            if cooldown_hours is not None
            else self.settings.promotion_book_cooldown_hours
        )
        self.rng = rng or random.Random()

    def is_eligible(
        self,
        book: Book,
        stats: Optional[PromotionStats],
        current_time: Optional[datetime] = None,
    ) -> bool:
        """Evaluate whether a book is eligible for promotion at the given time."""
        now = current_time or datetime.now(timezone.utc)

        # 1. Publication status and visibility
        pub_status = getattr(book.publication, "status", None) or getattr(book, "status", None)
        if isinstance(pub_status, PublicationStatus):
            pub_status = pub_status.value
        if str(pub_status).lower() != PublicationStatus.PUBLISHED.value:
            return False

        pub_vis = getattr(book.publication, "visibility", None)
        if isinstance(pub_vis, PublicationVisibility):
            pub_vis = pub_vis.value
        if str(pub_vis).lower() != PublicationVisibility.PUBLIC.value:
            return False

        # 2. Valid slug
        if not book.slug or not str(book.slug).strip():
            return False

        # 3. Cooldown check
        if stats:
            if stats.next_eligible_at:
                next_el = stats.next_eligible_at
                if next_el.tzinfo is None:
                    next_el = next_el.replace(tzinfo=timezone.utc)
                if now < next_el:
                    return False
            elif stats.last_promoted_at:
                last_pr = stats.last_promoted_at
                if last_pr.tzinfo is None:
                    last_pr = last_pr.replace(tzinfo=timezone.utc)
                elapsed_hours = (now - last_pr).total_seconds() / 3600.0
                if elapsed_hours < self.cooldown_hours:
                    return False

        return True

    def calculate_weight(
        self,
        book: Book,
        stats: Optional[PromotionStats],
        current_time: Optional[datetime] = None,
    ) -> float:
        """Calculate selection weight favoring under-promoted books and older promotions.
        
        Formula:
            base_weight = 1.0 / (1.0 + promotion_count)
            recency_multiplier = 1.0 + min(days_since_last / 30.0, 1.0)
            weight = base_weight * recency_multiplier
        """
        now = current_time or datetime.now(timezone.utc)
        promo_count = stats.promotion_count if stats else 0
        base_weight = 1.0 / (1.0 + max(0, promo_count))

        # Aging boost for books not promoted recently
        recency_mult = 1.0
        if stats and stats.last_promoted_at:
            last_pr = stats.last_promoted_at
            if last_pr.tzinfo is None:
                last_pr = last_pr.replace(tzinfo=timezone.utc)
            days_since = max(0.0, (now - last_pr).total_seconds() / 86400.0)
            recency_mult = 1.0 + min(days_since / 30.0, 1.0)
        elif not stats or promo_count == 0:
            # Fresh books never promoted get maximum recency boost
            recency_mult = 2.0

        return max(0.001, base_weight * recency_mult)

    def select_books(
        self,
        books: List[Book],
        stats_by_book_id: Dict[str, PromotionStats],
        count: int = 3,
        current_time: Optional[datetime] = None,
    ) -> List[Book]:
        """Select distinct eligible books using weighted random sampling without replacement."""
        now = current_time or datetime.now(timezone.utc)

        # 1. Filter eligible books
        eligible: List[Book] = []
        for book in books:
            st = stats_by_book_id.get(book.id)
            if self.is_eligible(book, st, current_time=now):
                eligible.append(book)

        logger.info(
            f"[BookSelector] {len(eligible)} eligible out of {len(books)} total books "
            f"(target={count}, cooldown={self.cooldown_hours}h)"
        )

        if not eligible:
            return []

        if len(eligible) <= count:
            # Return all eligible books if fewer or equal to target count
            self.rng.shuffle(eligible)
            return eligible

        # 2. Weighted sampling without replacement using Efraimidis-Spirakis algorithm:
        # key = u ** (1.0 / weight), sort descending
        scored_candidates: List[tuple[float, Book]] = []
        for book in eligible:
            st = stats_by_book_id.get(book.id)
            w = self.calculate_weight(book, st, current_time=now)
            u = self.rng.random()
            # Guard against u == 0
            u = max(1e-9, min(u, 1.0 - 1e-9))
            score = u ** (1.0 / w)
            scored_candidates.append((score, book))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        selected = [b for _, b in scored_candidates[:count]]
        return selected

