"""Source ranking and reliability scoring engine."""

from typing import List
from vasukisquare.research.models import SourceDocument, SourceType


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
    "arxiv.org",
    "github.com",
    "w3.org",
    "ietf.org",
    "developer.mozilla.org",
    "docs.python.org",
    "mongodb.com/docs",
    ".edu",
    ".gov",
]


class SourceRanker:
    """Ranks research documents based on source authority, type, and content density."""

    def score_document(self, doc: SourceDocument) -> float:
        """Calculate composite reliability score for a document between 0.0 and 1.0."""
        base_weight = SOURCE_TYPE_WEIGHTS.get(doc.source_type, 0.6)

        # Domain bonus
        domain_bonus = 0.0
        domain_lower = (doc.domain or "").lower()
        for pattern in AUTHORITY_DOMAIN_PATTERNS:
            if pattern in domain_lower:
                domain_bonus = 0.15
                break

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

        raw_score = (base_weight + domain_bonus) * length_factor
        return min(max(round(raw_score, 3), 0.1), 1.0)

    def rank(self, documents: List[SourceDocument]) -> List[SourceDocument]:
        """Score and sort documents in descending order of reliability."""
        for doc in documents:
            doc.reliability_score = self.score_document(doc)

        return sorted(documents, key=lambda d: (d.reliability_score, len(d.extracted_text)), reverse=True)

