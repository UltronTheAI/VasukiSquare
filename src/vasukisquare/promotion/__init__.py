"""Automated ebook promotion subsystem for VasukiSquare."""

from vasukisquare.promotion.models import (
    CampaignSummary,
    GeneratedArticleContent,
    PromotionPlatform,
    PromotionPost,
    PromotionStats,
    PromotionStatus,
)
from vasukisquare.promotion.publishers.base import PromotionPublisher, PublishResult
from vasukisquare.promotion.publishers.devto import DevToPublisher
from vasukisquare.promotion.repository import PromotionRepository
from vasukisquare.promotion.selector import BookSelector
from vasukisquare.promotion.service import PromotionService
from vasukisquare.promotion.writer import PromotionWriter

__all__ = [
    "CampaignSummary",
    "GeneratedArticleContent",
    "PromotionPlatform",
    "PromotionPost",
    "PromotionStats",
    "PromotionStatus",
    "PromotionPublisher",
    "PublishResult",
    "DevToPublisher",
    "PromotionRepository",
    "BookSelector",
    "PromotionService",
    "PromotionWriter",
]

