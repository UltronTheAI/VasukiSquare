"""Data models for automated ebook promotion subsystem."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


def generate_id() -> str:
    """Generate a unique string ID."""
    return str(uuid4())


class PromotionPlatform(str, Enum):
    """Supported social/developer promotion platforms."""
    DEVTO = "devto"


class PromotionStatus(str, Enum):
    """Lifecycle status for an individual generated promotion post."""
    GENERATED = "generated"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class PromotionStats(BaseModel):
    """Tracking statistics and cooldown metadata for a book on a specific platform."""

    id: str = Field(default_factory=generate_id)
    book_id: str
    book_slug: str
    platform: str = PromotionPlatform.DEVTO.value
    promotion_count: int = Field(default=0, ge=0)
    successful_posts: int = Field(default=0, ge=0)
    failed_posts: int = Field(default=0, ge=0)
    last_promoted_at: Optional[datetime] = None
    next_eligible_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("platform", mode="before")
    @classmethod
    def _validate_platform(cls, v: Any) -> str:
        if isinstance(v, PromotionPlatform):
            return v.value
        return str(v).lower()


class PromotionPost(BaseModel):
    """Persisted record of a generated promotion article and its publication outcome."""

    id: str = Field(default_factory=generate_id)
    campaign_run_id: str
    book_id: str
    book_slug: str
    platform: str = PromotionPlatform.DEVTO.value
    title: str
    body_markdown: str
    tags: List[str] = Field(default_factory=list)
    canonical_url: str
    status: PromotionStatus = PromotionStatus.GENERATED
    generation_model: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    publish_attempts: int = Field(default=0, ge=0)
    published_at: Optional[datetime] = None
    external_post_id: Optional[str] = None
    external_url: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, v: Any) -> PromotionStatus:
        if isinstance(v, str):
            try:
                return PromotionStatus(v.lower())
            except ValueError:
                return PromotionStatus.GENERATED
        return v

    @field_validator("platform", mode="before")
    @classmethod
    def _validate_platform(cls, v: Any) -> str:
        if isinstance(v, PromotionPlatform):
            return v.value
        return str(v).lower()


class GeneratedArticleContent(BaseModel):
    """Structured LLM output schema for educational promotion articles."""

    title: str = Field(
        ...,
        description="Engaging, authoritative title for the developer/technical article. Avoid generic buzzwords and clickbait.",
    )
    body_markdown: str = Field(
        ...,
        description="Complete, well-structured DEV-compatible Markdown article teaching concepts from the ebook with headers and code/tables.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Up to 4 relevant tags (lowercase, alphanumeric or hyphens, no hashes) suitable for DEV Community.",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Optional 1-2 sentence synopsis or subtitle.",
    )


class CampaignSummary(BaseModel):
    """Structured summary of a promotion campaign execution."""

    campaign_run_id: str
    platform: str
    dry_run: bool
    selected_count: int = 0
    generated_count: int = 0
    published_count: int = 0
    failed_count: int = 0
    selected_books: List[Dict[str, Any]] = Field(default_factory=list)
    posts: List[PromotionPost] = Field(default_factory=list)
    failures: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

