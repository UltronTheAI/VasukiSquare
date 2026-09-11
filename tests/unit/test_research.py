"""Unit tests for research sources, deduplication, near-duplicate detection, and ranking."""

import pytest
from vasukisquare.research.models import (
    SourceDocument,
    SourceType,
    Citation,
    Fact,
    ResearchQuery,
    ResearchPlan,
    normalize_url,
)
from vasukisquare.research.deduplication import (
    DeduplicationService,
    is_near_duplicate,
    jaccard_similarity,
    tokenize_text,
)
from vasukisquare.research.ranking import SourceRanker


def test_url_normalization_with_tracking():
    raw_url = "https://EXAMPLE.COM/docs/guide/?utm_source=twitter&utm_medium=social&ref=123"
    norm = normalize_url(raw_url)
    assert norm == "https://example.com/docs/guide"


def test_source_document_model():
    doc = SourceDocument(
        url="https://docs.python.org/3/library/asyncio.html",
        title="asyncio — Asynchronous I/O",
        source_type=SourceType.DOCUMENTATION,
        extracted_text="asyncio is a library to write concurrent code using the async/await syntax.",
    )
    assert doc.domain == "docs.python.org"
    assert doc.publisher == "docs.python.org"
    assert doc.source_type == SourceType.DOCUMENTATION
    assert doc.reliability_score == 1.0


def test_near_duplicate_detection():
    text1 = "Transformers use self-attention mechanisms to compute representations of their input and output without using sequence-aligned RNNs or convolution."
    text2 = "Transformers rely on self-attention mechanisms to compute representations of input and output without using sequence-aligned RNNs or convolutions."
    text3 = "PostgreSQL is an advanced, enterprise-class open-source relational database supporting both SQL and JSON querying."

    assert is_near_duplicate(text1, text2, threshold=0.70) is True
    assert is_near_duplicate(text1, text3, threshold=0.70) is False


def test_deduplication_service_pipeline():
    doc1 = SourceDocument(
        url="https://example.com/article?utm_source=newsletter",
        title="Distributed Systems Guide",
        extracted_text="Short snippet text.",
        reliability_score=0.6,
    )
    doc2 = SourceDocument(
        url="https://example.com/article",
        title="Distributed Systems Guide Full",
        extracted_text="Full comprehensive text about distributed consensus protocols, raft, and paxos in detail.",
        reliability_score=0.8,
    )
    doc3 = SourceDocument(
        url="https://different.com/guide",
        title="Distributed Systems Guide Mirror",
        extracted_text="Full comprehensive text about distributed consensus protocols, raft, and paxos in detail.",
        reliability_score=0.5,
    )

    dedup = DeduplicationService(near_duplicate_threshold=0.80)
    pruned = dedup.deduplicate([doc1, doc2, doc3])

    assert len(pruned) == 1
    assert pruned[0].url == "https://example.com/article"
    assert pruned[0].reliability_score == 0.8


def test_source_ranker_authority_weights():
    ranker = SourceRanker()

    doc_doc = SourceDocument(
        url="https://docs.python.org/3/",
        title="Python Official Docs",
        source_type=SourceType.DOCUMENTATION,
        extracted_text="A" * 3000,
    )
    doc_wiki = SourceDocument(
        url="https://en.wikipedia.org/wiki/Python_(programming_language)",
        title="Python - Wikipedia",
        source_type=SourceType.WIKIPEDIA,
        extracted_text="A" * 3000,
    )

    ranked = ranker.rank([doc_wiki, doc_doc])
    assert ranked[0].source_type == SourceType.DOCUMENTATION
    assert ranked[0].reliability_score > ranked[1].reliability_score


def test_research_plan_schema():
    query = ResearchQuery(
        query="mongodb replica set architecture",
        perspective="architecture",
        target_source_types=[SourceType.DOCUMENTATION],
        priority=1,
    )
    plan = ResearchPlan(
        topic="MongoDB Internals",
        queries=[query],
        perspective_goals={"architecture": "Understand oplog and raft election"},
    )
    assert plan.topic == "MongoDB Internals"
    assert len(plan.queries) == 1
    assert plan.queries[0].target_source_types[0] == SourceType.DOCUMENTATION
