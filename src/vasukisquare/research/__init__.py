"""Research domain: models, deduplication, ranking, planning, and pipeline service."""

from vasukisquare.research.models import (
    SourceType,
    SourceDocument,
    Citation,
    Fact,
    Source,
    ResearchQuery,
    ResearchPlan,
    ResearchCorpus,
    ResearchDossier,
    normalize_url,
)
from vasukisquare.research.deduplication import (
    DeduplicationService,
    is_near_duplicate,
    jaccard_similarity,
)
from vasukisquare.research.ranking import SourceRanker
from vasukisquare.research.planner import ResearchPlanner
from vasukisquare.research.service import ResearchService

__all__ = [
    "SourceType",
    "SourceDocument",
    "Citation",
    "Fact",
    "Source",
    "ResearchQuery",
    "ResearchPlan",
    "ResearchCorpus",
    "ResearchDossier",
    "normalize_url",
    "DeduplicationService",
    "is_near_duplicate",
    "jaccard_similarity",
    "SourceRanker",
    "ResearchPlanner",
    "ResearchService",
]
