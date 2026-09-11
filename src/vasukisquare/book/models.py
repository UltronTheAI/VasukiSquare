"""Domain schemas and models for Books, Pages, Covers, and Plans."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme, get_chapter_theme


def generate_id() -> str:
    """Generate a unique string ID."""
    return str(uuid4())


class Page(BaseModel):
    """Represents an individual A4 rendered page stored independently in MongoDB."""

    id: str = Field(default_factory=generate_id)
    book_id: str
    page_number: int = Field(ge=1)
    chapter_number: Optional[int] = Field(default=None, ge=1)
    chapter_title: Optional[str] = None
    layout_type: LayoutType
    theme: Theme = Theme.LIGHT
    icon_name: Optional[str] = None
    html_content: str = ""
    previous_page_id: Optional[str] = None
    next_page_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_page_rules(self) -> "Page":
        """Validate chapter opener and theme consistency."""
        if self.chapter_number is not None:
            # Enforce odd=dark, even=light theme rule
            expected_theme = get_chapter_theme(self.chapter_number)
            if self.theme != expected_theme:
                self.theme = expected_theme

        if self.layout_type == LayoutType.CHAPTER_OPENER:
            if self.chapter_number is None or not self.chapter_title:
                raise ValueError("Chapter opener pages must specify chapter_number and chapter_title.")
            if not self.icon_name:
                raise ValueError("Chapter opener pages must contain exactly one Lucide icon.")
        return self


class Cover(BaseModel):
    """Represents book cover artwork metadata and asset references."""

    id: str = Field(default_factory=generate_id)
    book_id: str
    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = "VasukiSquare AI"
    width: int = Field(default=1600)
    height: int = Field(default=2560)
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Book(BaseModel):
    """Represents the complete book entity."""

    id: str = Field(default_factory=generate_id)
    title: str
    subtitle: Optional[str] = None
    topic: str
    target_pages: int = Field(default=60, ge=1)
    starting_page_id: Optional[str] = None
    total_pages: int = 0
    total_chapters: int = 0
    status: str = "draft"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PagePlan(BaseModel):
    """Plan for an individual page."""

    page_number: int
    layout_type: LayoutType
    chapter_number: Optional[int] = None
    title: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    icon_name: Optional[str] = None


class ChapterPlan(BaseModel):
    """Plan for an entire chapter."""

    chapter_number: int = Field(ge=1)
    title: str
    summary: str
    icon_name: str
    pages: List[PagePlan] = Field(default_factory=list)

    @property
    def theme(self) -> Theme:
        """Chapter theme derived from chapter number."""
        return get_chapter_theme(self.chapter_number)


class EditorialPlan(BaseModel):
    """Editorial plan structuring the book's narrative and chapters."""

    book_title: str
    book_subtitle: Optional[str] = None
    target_audience: str
    tone: str
    estimated_pages: int
    chapters: List[ChapterPlan] = Field(default_factory=list)

