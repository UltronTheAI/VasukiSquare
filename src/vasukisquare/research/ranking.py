"""Source ranking and reliability scoring engine."""

from typing import Any, List, Optional
from vasukisquare.research.models import IdeaScores, SourceDocument, SourceType


# Base weight multipliers by source type
SOURCE_TYPE_WEIGHTS = {
    SourceType.DOCUMENTATION: 1.0,
    SourceType.ACADEMIC: 0.95,
    SourceType.BLOG: 0.75,
    SourceType.NEWS: 0.70,
    SourceType.WEBPAGE: 0.65,
    SourceType.WEB: 0.60,
    SourceType.WIKIPEDIA: 0.50,  # Orientation damping rule from AGENTS.md
}

# High authority domains
AUTHORITY_DOMAIN_PATTERNS = [
    "docs.python.org",
    "python.org",
    "peps.python.org",
    "doc.rust-lang.org",
    "rust-lang.org",
    "go.dev",
    "golang.org",
    "developer.mozilla.org",
    "w3.org",
    "ietf.org",
    "arxiv.org",
    "github.com",
    "mongodb.com/docs",
    "docs.docker.com",
    "kubernetes.io/docs",
    ".edu",
    ".gov",
]

# SEO / Consulting / Marketing domains or synthetic academic proceedings that should not dictate outline or rank top
LOW_AUTHORITY_PATTERNS = [
    "uvik.net",
    "software.uvik",
    "clickbait",
    "acm.org/publications/proceedings",
]


class SourceRanker:
    """Ranks research documents based on source authority, type, and content density."""

    def score_document(self, doc: SourceDocument) -> float:
        """Calculate composite reliability score for a document between 0.0 and 1.0."""
        base_weight = SOURCE_TYPE_WEIGHTS.get(doc.source_type, 0.6)

        # Domain bonus
        domain_bonus = 0.0
        domain_lower = (doc.domain or "").lower()
        url_lower = (doc.url or "").lower()
        title_lower = (doc.title or "").lower()

        for pattern in AUTHORITY_DOMAIN_PATTERNS:
            if pattern in domain_lower or pattern in url_lower:
                domain_bonus = 0.15
                break

        # Penalty for low authority or synthetic proceedings
        penalty = 0.0
        for pattern in LOW_AUTHORITY_PATTERNS:
            if pattern in domain_lower or pattern in url_lower:
                penalty = 0.4
                break

        if "primary specification" in title_lower and "acm.org" in url_lower:
            penalty = 0.5

        # Content length factor (penalize stub documents < 200 chars, reward rich docs)
        text_len = len(doc.extracted_text)
        if text_len < 100:
            length_factor = 0.4
        elif text_len < 500:
            length_factor = 0.7
        elif text_len < 2000:
            length_factor = 0.9
        else:
            length_factor = 1.0

        raw_score = (base_weight + domain_bonus - penalty) * length_factor
        return min(max(round(raw_score, 3), 0.1), 1.0)

    def rank(self, documents: List[SourceDocument]) -> List[SourceDocument]:
        """Score and sort documents in descending order of reliability."""
        for doc in documents:
            doc.reliability_score = self.score_document(doc)

        return sorted(documents, key=lambda d: (d.reliability_score, len(d.extracted_text)), reverse=True)


# ==============================================================================
# BOOK IDEA RANKING & SCORING ENGINE
# ==============================================================================


class IdeaRanker:
    """Evaluates and ranks candidate book ideas across trendiness, uniqueness, bookworthiness, and evergreen value."""

    def __init__(self, min_score_threshold: float = 0.70):
        self.min_score_threshold = min_score_threshold

    def evaluate_page_count_fit(self, pages: int, book_type: str, summary: str) -> float:
        """Evaluate how appropriately the page count (40-100) matches the topic complexity."""
        if pages < 40 or pages > 100:
            return 0.0

        b_type = (book_type or "").lower()
        # 40-50: focused beginner guides, compact how-to
        if 40 <= pages <= 50:
            if any(k in b_type for k in ["beginner", "quick", "crash", "starter", "how_to", "handbook"]):
                return 1.0
            return 0.85
        # 50-70: normal practical guides
        if 50 < pages <= 70:
            if "practical" in b_type or "guide" in b_type or "tutorial" in b_type:
                return 1.0
            return 0.90
        # 70-85: broader technical / educational
        if 70 < pages <= 85:
            if "technical" in b_type or "educational" in b_type or "deep_dive" in b_type:
                return 1.0
            return 0.85
        # 85-100: substantial depth
        if 85 < pages <= 100:
            if "deep_dive" in b_type or "comprehensive" in b_type or "architecture" in b_type or "internals" in b_type:
                return 1.0
            return 0.80

        return 0.85

    def score_idea(
        self,
        trend: float,
        uniqueness: float,
        bookworthiness: float,
        evergreen: float,
        confidence: float,
        pages: int = 60,
        book_type: str = "practical_guide",
        summary: str = "",
        sources_count: int = 0,
        signals_count: int = 0,
    ) -> IdeaScores:
        """Compute consolidated scores ensuring page depth calibration and evidence backing."""
        page_fit = self.evaluate_page_count_fit(pages, book_type, summary)
        adjusted_bookworthiness = min(max(round(bookworthiness * page_fit, 3), 0.1), 1.0)

        # Boost confidence with verified sources and trend signals
        conf_boost = min(sources_count * 0.05 + signals_count * 0.05, 0.20)
        adjusted_confidence = min(max(round(confidence + conf_boost, 3), 0.1), 1.0)

        return IdeaScores(
            trend=min(max(round(trend, 3), 0.1), 1.0),
            uniqueness=min(max(round(uniqueness, 3), 0.1), 1.0),
            bookworthiness=adjusted_bookworthiness,
            evergreen=min(max(round(evergreen, 3), 0.1), 1.0),
            confidence=adjusted_confidence,
        )

    def rank_ideas(self, ideas: List[Any], min_score: Optional[float] = None) -> List[Any]:
        """Sort ideas by composite score and filter by minimum score threshold."""
        threshold = min_score if min_score is not None else self.min_score_threshold
        sorted_ideas = sorted(
            ideas,
            key=lambda x: (x.scores.composite_score if hasattr(x, "scores") else 0.0, x.scores.bookworthiness if hasattr(x, "scores") else 0.0),
            reverse=True,
        )
        return [i for i in sorted_ideas if hasattr(i, "scores") and i.scores.composite_score >= threshold]

