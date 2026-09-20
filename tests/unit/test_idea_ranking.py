"""Unit tests for IdeaRanker, page fit evaluation, and minimum score threshold filtering."""

import pytest
from vasukisquare.research.ranking import IdeaRanker
from vasukisquare.research.models import BookIdea, IdeaScores, IdeaStatus


def test_idea_ranker_page_fit_evaluation():
    ranker = IdeaRanker()

    # 45 pages beginner guide
    fit_45 = ranker.evaluate_page_count_fit(45, "beginner_guide", "A beginner crash course")
    assert fit_45 == 1.0

    # 60 pages practical guide
    fit_60 = ranker.evaluate_page_count_fit(60, "practical_guide", "A practical tutorial")
    assert fit_60 == 1.0

    # 90 pages comprehensive deep dive
    fit_90 = ranker.evaluate_page_count_fit(90, "deep_dive", "Comprehensive architecture")
    assert fit_90 == 1.0

    # Invalid page count
    fit_invalid = ranker.evaluate_page_count_fit(30, "practical_guide", "Too short")
    assert fit_invalid == 0.0


def test_idea_ranker_score_and_filter():
    ranker = IdeaRanker(min_score_threshold=0.70)

    idea_high = BookIdea(
        topic="Vector Databases",
        title="Vector Databases",
        prompt="Deep dive...",
        pages=75,
        scores=IdeaScores(trend=0.85, uniqueness=0.85, bookworthiness=0.88, evergreen=0.80, confidence=0.85),
    )
    idea_low = BookIdea(
        topic="Outdated Tech",
        title="Outdated Tech",
        prompt="Short...",
        pages=45,
        scores=IdeaScores(trend=0.30, uniqueness=0.30, bookworthiness=0.40, evergreen=0.20, confidence=0.40),
    )

    ranked = ranker.rank_ideas([idea_low, idea_high])
    assert len(ranked) == 1
    assert ranked[0].title == "Vector Databases"

