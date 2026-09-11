"""Research domain models: sources, citations, facts, and dossiers."""

from datetime import datetime, timezone
from typing import List, Optional, Set
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


def normalize_url(url: str) -> str:
    """Normalize a URL to prevent duplicate tracking."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


class Source(BaseModel):
    """Represents an external research source."""

    url: str
    title: str
    snippet: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    domain: Optional[str] = None
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        cleaned = normalize_url(v)
        if not cleaned:
            raise ValueError("URL cannot be empty.")
        return cleaned

    def model_post_init(self, __context: object) -> None:
        if not self.domain and self.url:
            self.domain = urlparse(self.url).netloc.lower()


class Citation(BaseModel):
    """Represents a direct citation referencing a source."""

    source_url: str
    claim: str
    quote: Optional[str] = None
    page_number_in_source: Optional[int] = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        return normalize_url(v)


class Fact(BaseModel):
    """Represents a verified fact extracted during research."""

    statement: str
    citations: List[Citation] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ResearchDossier(BaseModel):
    """Consolidated research dossier for a topic or book."""

    topic: str
    sources: List[Source] = Field(default_factory=list)
    facts: List[Fact] = Field(default_factory=list)
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def deduplicate_sources(self) -> None:
        """Deduplicate sources by normalized URL."""
        seen_urls: Set[str] = set()
        unique_sources: List[Source] = []
        for src in self.sources:
            norm = normalize_url(src.url)
            if norm not in seen_urls:
                seen_urls.add(norm)
                unique_sources.append(src)
        self.sources = unique_sources

