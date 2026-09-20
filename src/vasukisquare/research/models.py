"""Research domain models: sources, source documents, citations, queries, and corpus."""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, model_validator


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
    target_source_types: List[str] = Field(default_factory=lambda: ["web", "documentation"])
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


class ResearchBundle(BaseModel):
    """Structured evidence package provided to the writer without raw scraped garbage."""

    facts: List[str] = Field(default_factory=list, description="Verified factual statements")
    definitions: List[Dict[str, str]] = Field(default_factory=list, description="Term definitions (term -> definition)")
    verified_commands: List[str] = Field(default_factory=list, description="Verified shell/CLI commands")
    verified_code_examples: List[Dict[str, str]] = Field(default_factory=list, description="Verified syntax-checked code examples")
    expected_outputs: List[Dict[str, str]] = Field(default_factory=list, description="Expected stdout for code examples")
    concepts: List[str] = Field(default_factory=list, description="Core concepts covered")
    source_refs: List[Dict[str, str]] = Field(default_factory=list, description="Clean authoritative source references")
    warnings: List[str] = Field(default_factory=list, description="Common pitfalls and warnings")


# ==============================================================================
# BOOK IDEA LIFECYCLE & DISCOVERY MODELS
# ==============================================================================


class IdeaStatus(str, Enum):
    """Lifecycle states for book ideas in MongoDB."""

    CANDIDATE = "candidate"
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class IdeaSource(BaseModel):
    """Tracked factual reference or source for a book idea."""

    title: str = ""
    url: str = ""
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("url")
    @classmethod
    def clean_url(cls, v: str) -> str:
        if not v:
            return ""
        return normalize_url(v)


class TrendSignal(BaseModel):
    """Market, search, or industry trend signal backing a candidate topic."""

    source: str
    signal: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class IdeaScores(BaseModel):
    """Multi-dimensional evaluation metrics for an idea."""

    trend: float = Field(default=0.5, ge=0.0, le=1.0, description="Current market interest and relevance")
    uniqueness: float = Field(default=0.5, ge=0.0, le=1.0, description="Differentiation from existing catalog")
    bookworthiness: float = Field(default=0.5, ge=0.0, le=1.0, description="Substance to sustain 40-100 pages")
    evergreen: float = Field(default=0.5, ge=0.0, le=1.0, description="Long-term practical value")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Reliability of evidence and signals")

    @property
    def composite_score(self) -> float:
        """Weighted overall score (0.0 to 1.0)."""
        return round(
            0.25 * self.trend
            + 0.25 * self.uniqueness
            + 0.30 * self.bookworthiness
            + 0.20 * self.evergreen,
            3,
        )


class IdeaGenerationInfo(BaseModel):
    """Tracking fields for when an idea is claimed and processed by the generation pipeline."""

    book_id: Optional[str] = None
    output_path: Optional[str] = None
    error: Optional[str] = None


class BookIdea(BaseModel):
    """Canonical representation of a book idea stored in MongoDB book_ideas collection."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    title: str
    slug: str = ""
    pages: int = Field(default=60, ge=40, le=100, description="Target page count strictly between 40 and 100")
    prompt: str = Field(description="Production-quality editorial brief prompt for VasukiSquare")
    category: str = "Technology"
    audience: str = "General Practitioners and Professionals"
    book_type: str = "practical_guide"
    summary: str = ""
    angle: str = ""
    why_now: str = ""
    keywords: List[str] = Field(default_factory=list)
    research_queries: List[str] = Field(default_factory=list)
    sources: List[IdeaSource] = Field(default_factory=list)
    trend_signals: List[TrendSignal] = Field(default_factory=list)
    scores: IdeaScores = Field(default_factory=IdeaScores)
    similar_to: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    status: IdeaStatus = IdeaStatus.READY
    rejection_reason: Optional[str] = None
    attempt_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    generation: IdeaGenerationInfo = Field(default_factory=IdeaGenerationInfo)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        clean = v.strip().strip('"\'`')
        if not clean:
            raise ValueError("Idea title cannot be empty.")
        if len(clean) > 50:
            clean = clean[:50].rsplit(" ", 1)[0]
        return clean

    @field_validator("pages")
    @classmethod
    def validate_pages_range(cls, v: int) -> int:
        if v < 40 or v > 100:
            raise ValueError(f"Pages must be strictly between 40 and 100 (got {v}).")
        return v

    @model_validator(mode="before")
    @classmethod
    def _ensure_slug_and_status(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("slug"):
                title = data.get("title") or data.get("topic") or "idea"
                slug_base = re.sub(r"[^\w\s-]", "", str(title)).strip().lower()
                data["slug"] = re.sub(r"[-\s]+", "-", slug_base)
            if "status" in data and isinstance(data["status"], str):
                try:
                    data["status"] = IdeaStatus(data["status"].lower())
                except ValueError:
                    data["status"] = IdeaStatus.READY
        return data


# Structured LLM Output Schemas for Idea Discovery and Formulation
class RawTrendDiscovery(BaseModel):
    """Candidate trending topic generated during discovery stage."""

    topic: str
    category: str = "Technology"
    why_now: str = ""
    target_audience: str = "Practitioners and Enthusiasts"
    estimated_depth: str = Field(default="moderate", description="narrow, moderate, broad, comprehensive")
    suggested_pages: int = Field(default=60, ge=40, le=100)
    angle: str = ""
    trend_signals: List[str] = Field(default_factory=list)


class TrendDiscoveryList(BaseModel):
    """Collection of discovered trending topic candidates."""

    trends: List[RawTrendDiscovery] = Field(default_factory=list)


class DetailedIdeaPrompt(BaseModel):
    """Polished production generation prompt and metadata generated by the editorial agent."""

    title: str = Field(description="Crisp public title <= 50 chars")
    summary: str = Field(description="Executive summary of the book")
    audience: str = "General Practitioners and Professionals"
    book_type: str = "practical_guide"
    angle: str = ""
    why_now: str = ""
    pages: int = Field(default=60, ge=40, le=100)
    keywords: List[str] = Field(default_factory=list)
    research_queries: List[str] = Field(default_factory=list)
    full_prompt: str = Field(description="Detailed editorial brief for VasukiSquare generation")
    trend_score: float = Field(default=0.8, ge=0.0, le=1.0)
    uniqueness_score: float = Field(default=0.8, ge=0.0, le=1.0)
    bookworthiness_score: float = Field(default=0.8, ge=0.0, le=1.0)
    evergreen_score: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
