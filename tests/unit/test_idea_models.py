"""Unit tests for BookIdea schema, validation rules, page count bounds, and title normalization."""

import pytest
from pydantic import ValidationError

from vasukisquare.research.models import (
    BookIdea,
    IdeaScores,
    IdeaStatus,
    RawTrendDiscovery,
)


def test_book_idea_schema_defaults_and_slug():
    idea = BookIdea(
        topic="Modern Vector Search",
        title="Modern Vector Search",
        prompt="A detailed guide to vector search...",
        pages=60,
    )
    assert idea.slug == "modern-vector-search"
    assert idea.status == IdeaStatus.READY
    assert idea.pages == 60
    assert idea.category == "Technology"
    assert idea.scores.composite_score > 0.0
    assert idea.attempt_count == 0
    assert idea.generation.book_id is None


def test_book_idea_page_count_bounds():
    # Valid bounds: 40 to 100
    idea_min = BookIdea(
        topic="Quick Start",
        title="Quick Start Guide",
        prompt="A short guide",
        pages=40,
    )
    assert idea_min.pages == 40

    idea_max = BookIdea(
        topic="Deep Architecture",
        title="Comprehensive Architecture",
        prompt="A deep guide",
        pages=100,
    )
    assert idea_max.pages == 100

    # Invalid: < 40
    with pytest.raises(ValidationError):
        BookIdea(
            topic="Too Short",
            title="Too Short Guide",
            prompt="Brief",
            pages=39,
        )

    # Invalid: > 100
    with pytest.raises(ValidationError):
        BookIdea(
            topic="Too Long",
            title="Too Long Guide",
            prompt="Brief",
            pages=101,
        )


def test_book_idea_title_validation():
    # Empty title raises error
    with pytest.raises(ValidationError):
        BookIdea(
            topic="Valid Topic",
            title="   ",
            prompt="Valid prompt",
            pages=50,
        )

    # Long title is safely truncated to <= 50 characters
    long_title = "This is an extremely long title that exceeds the strict fifty character publishing limit"
    idea = BookIdea(
        topic="Topic",
        title=long_title,
        prompt="Valid prompt",
        pages=50,
    )
    assert len(idea.title) <= 50
    assert not idea.title.startswith(" ")


def test_idea_scores_composite_calculation():
    scores = IdeaScores(
        trend=0.8,
        uniqueness=0.9,
        bookworthiness=0.7,
        evergreen=0.6,
        confidence=0.85,
    )
    # 0.25*0.8 + 0.25*0.9 + 0.30*0.7 + 0.20*0.6 = 0.20 + 0.225 + 0.21 + 0.12 = 0.755
    assert scores.composite_score == 0.755


def test_raw_trend_discovery_model():
    trend = RawTrendDiscovery(
        topic="eBPF Kernel Profiling",
        category="Systems",
        why_now="Kernel tracing adoption",
        target_audience="SREs",
        estimated_depth="comprehensive",
        suggested_pages=90,
        angle="Deep dive into BCC and Cilium",
        trend_signals=["Linux conference talk"],
    )
    assert trend.suggested_pages == 90
    assert len(trend.trend_signals) == 1

