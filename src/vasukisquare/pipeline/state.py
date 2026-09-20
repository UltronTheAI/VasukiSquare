"""Typed state model for the end-to-end ebook generation pipeline."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from vasukisquare.book.models import (
    Book,
    BookIntent,
    BookPlan,
    Cover,
    CoverPlan,
    Page,
)
from vasukisquare.research.models import ResearchCorpus


class GenerationState(BaseModel):
    """Encapsulates all stage outputs and metadata across the book generation lifecycle."""

    topic: str
    target_pages: int = 60
    intent: Optional[BookIntent] = None
    research_corpus: Optional[ResearchCorpus] = None
    book_plan: Optional[BookPlan] = None
    cover_plan: Optional[CoverPlan] = None
    pages: List[Page] = Field(default_factory=list)
    book: Optional[Book] = None
    cover: Optional[Cover] = None
    assembled_html: Optional[str] = None
    pdf_path: Optional[str] = None
    artifacts: Dict[str, str] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Alias for compatibility
PipelineState = GenerationState
