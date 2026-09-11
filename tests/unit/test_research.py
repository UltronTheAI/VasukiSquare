"""Unit tests for research sources, citations, and deduplication."""

import pytest
from vasukisquare.research.models import (
    Source,
    Citation,
    Fact,
    ResearchDossier,
    normalize_url,
)


def test_url_normalization():
    assert normalize_url("https://example.com/path/") == "https://example.com/path"
    assert normalize_url("HTTP://EXAMPLE.COM/test") == "http://example.com/test"


def test_source_model():
    source = Source(
        url="https://en.wikipedia.org/wiki/Artificial_intelligence",
        title="Artificial intelligence - Wikipedia",
    )
    assert source.domain == "en.wikipedia.org"
    assert source.reliability_score == 1.0


def test_research_dossier_deduplication():
    s1 = Source(url="https://example.com/article1", title="Article 1")
    s2 = Source(url="https://example.com/article1/", title="Article 1 Duplicate")
    s3 = Source(url="https://example.com/article2", title="Article 2")

    dossier = ResearchDossier(
        topic="AI Systems",
        sources=[s1, s2, s3],
    )
    assert len(dossier.sources) == 3
    dossier.deduplicate_sources()
    assert len(dossier.sources) == 2
    assert dossier.sources[0].url == "https://example.com/article1"
    assert dossier.sources[1].url == "https://example.com/article2"


def test_citation_parsing():
    citation = Citation(
        source_url="https://arxiv.org/abs/1706.03762/",
        claim="Attention is all you need.",
        page_number_in_source=1,
    )
    assert citation.source_url == "https://arxiv.org/abs/1706.03762"

