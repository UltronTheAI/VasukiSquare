"""Research domain models: sources, source documents, citations, queries, and corpus."""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    """Categorization of research source origins."""

    WEB = "web"
    WIKIPEDIA = "wikipedia"
    WEBPAGE = "webpage"
    NEWS = "news"
    DOCUMENTATION = "documentation"
    BLOG = "blog"
    ACADEMIC = "academic"


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, fragments, trailing slashes, and standardizing casing."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    # Strip marketing/tracking query parameters (utm_*, ref, etc.)
    query_params = parse_qs(parsed.query)
    clean_params = {
        k: v for k, v in query_params.items()
        if not (k.startswith("utm_") or k in {"ref", "source", "fbclid", "gclid", "fb_action_ids"})
    }
    encoded_query = urlencode(clean_params, doseq=True)

    clean_url = urlunparse((scheme, netloc, path, "", encoded_query, ""))
    return clean_url.rstrip("?")


class SourceDocument(BaseModel):
    """Unified representation of an ingested and validated research document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    url: str
    title: str
    publisher: Optional[str] = None
    domain: Optional[str] = None
    retrieval_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_type: SourceType = SourceType.WEB
    extracted_text: str = ""
    summary: Optional[str] = None
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def clean_url(cls, v: str) -> str:
        norm = normalize_url(v)
        if not norm:
            raise ValueError("URL cannot be empty.")
        return norm

    def model_post_init(self, __context: object) -> None:
        if not self.domain and self.url:
            self.domain = urlparse(self.url).netloc.lower()
        if not self.publisher and self.domain:
            self.publisher = self.domain


# Backwards compatibility and structured citation models
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


class Source(BaseModel):
    """Legacy source model for backwards compatibility."""

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
        return normalize_url(v)

    def model_post_init(self, __context: object) -> None:
        if not self.domain and self.url:
            self.domain = urlparse(self.url).netloc.lower()


class ResearchQuery(BaseModel):
    """Structured research query targeting a specific perspective."""

    query: str
    perspective: str
    target_source_types: List[SourceType] = Field(default_factory=lambda: [SourceType.WEB])
    priority: int = 1


class ResearchPlan(BaseModel):
    """Multi-perspective research plan produced by the LLM planner."""

    topic: str
    queries: List[ResearchQuery] = Field(default_factory=list)
    perspective_goals: Dict[str, str] = Field(default_factory=dict)


class ResearchCorpus(BaseModel):
    """Clean structured research corpus ready for citation by downstream agents."""

    topic: str
    documents: List[SourceDocument] = Field(default_factory=list)
    queries_executed: List[str] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResearchDossier(BaseModel):
    """Consolidated research dossier containing legacy sources and facts."""

    topic: str
    sources: List[Source] = Field(default_factory=list)
    facts: List[Fact] = Field(default_factory=list)
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def deduplicate_sources(self) -> None:
        """Deduplicate sources by normalized URL."""
        seen_urls: set[str] = set()
        unique_sources: List[Source] = []
        for src in self.sources:
            norm = normalize_url(src.url)
            if norm not in seen_urls:
                seen_urls.add(norm)
                unique_sources.append(src)
        self.sources = unique_sources
