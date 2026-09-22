"""Tests for VasukiSquare editorial identity, quality gate, and practical publishing pipeline."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from vasukisquare.agents.quality_gate import (
    EditorialQualityGate,
    QualityValidationResult,
    BANNED_AI_CLICHES,
)
from vasukisquare.research.models import BookIdea, IdeaScores, IdeaSource, IdeaStatus, TrendSignal
from vasukisquare.research.idea_researcher import (
    CURATED_TREND_CORPUS,
    generate_production_prompt,
    IdeaResearchService,
)
from vasukisquare.agents.editorial import (
    EditorialPlannerAgent,
    build_requirement_coverage_matrix,
)
from vasukisquare.agents.technical_content import classify_topic
from vasukisquare.book.models import Book, BookIntent, Page, PageContent
from vasukisquare.book.components import TextBlock, CodeBlock, ChecklistBlock, TableBlock
from vasukisquare.promotion.models import PromotionPost, PromotionStatus
from vasukisquare.promotion.writer import PromotionWriter


def test_curated_trend_corpus_adheres_to_practical_guides():
    """Verify that all items in the curated trend corpus are practical guides, not raw coding manuals."""
    for item in CURATED_TREND_CORPUS:
        topic = item["topic"].lower()
        angle = item["angle"].lower()
        # Should not contain pure coding tutorial markers
        assert "syntax" not in topic
        assert "building a crud app" not in topic
        assert "installing packages" not in topic

        # Must have practical metadata fields
        assert "intended_reader" in item
        assert "problem_solved" in item
        assert "practical_outcome" in item
        assert len(item["intended_reader"]) > 5
        assert len(item["problem_solved"]) > 5
        assert len(item["practical_outcome"]) > 5


def test_generate_production_prompt_enforces_anti_cliche_and_no_code():
    """Verify that generated production prompts forbid coding tutorials and AI cliches."""
    prompt = generate_production_prompt(
        topic="How to Write Better AI Prompts",
        title="The Art of Effective AI Prompting",
        target_audience="Knowledge Workers and Students",
        pages=46,
        angle="Mental models and structured prompting frameworks",
        why_now="Generative AI adoption is surging",
        category="Technology",
        intended_reader="Professionals using AI daily",
        problem_solved="Vague and inaccurate AI outputs",
        practical_outcome="Reliable prompting frameworks and mental models",
    )

    assert "NO CODING TUTORIALS" in prompt
    assert "ZERO AI CLICHES" in prompt
    assert "VasukiSquare Publishing Identity" in prompt
    assert "Intended Reader: Professionals using AI daily" in prompt
    assert "Core Problem Solved: Vague and inaccurate AI outputs" in prompt
    assert "Practical Outcome: Reliable prompting frameworks" in prompt


def test_quality_gate_idea_validation():
    """Verify Quality Gate accepts high-value practical ideas and flags generic coding manuals."""
    good_idea = BookIdea(
        topic="A Practical Guide to Digital Privacy",
        title="Practical Digital Privacy Handbook",
        pages=50,
        prompt="A comprehensive guide to digital privacy and account security without paranoia.",
        category="Technology",
        audience="Everyday Internet Users",
        intended_reader="Individuals seeking practical online privacy",
        problem_solved="Unchecked tracking and data broker profiling",
        practical_outcome="Practical password hygiene, 2FA, and browser hardening",
        book_type="practical_guide",
        summary="Actionable steps to safeguard personal information online.",
        angle="Layered approach to online defense without technical complexity.",
        why_now="Frequent data breaches and online surveillance.",
        sources=[
            IdeaSource(
                title="Privacy Reference",
                url="https://en.wikipedia.org/wiki/Information_privacy",
                publisher="Wikipedia",
                accessed_at=datetime.now(timezone.utc),
            )
        ],
        scores=IdeaScores(
            trend=0.85,
            uniqueness=0.88,
            bookworthiness=0.90,
            evergreen=0.85,
            confidence=0.88,
            composite_score=0.87,
        ),
        status=IdeaStatus.READY,
    )

    res = EditorialQualityGate.validate_idea(good_idea)
    assert res.is_valid is True
    assert res.score >= 0.70

    bad_idea = BookIdea(
        topic="Tutorial on writing syntax and building a crud app in React",
        title="React Syntax Tutorial",
        pages=50,
        prompt="A step by step tutorial on writing syntax and building a crud app in React with npm install commands.",
        category="Programming",
        audience="Developers",
        book_type="tutorial_manual",
        summary="Coding tutorial for React.",
        angle="Writing React components and API routes.",
        why_now="React popularity.",
        scores=IdeaScores(
            trend=0.5,
            uniqueness=0.2,
            bookworthiness=0.3,
            evergreen=0.4,
            confidence=0.5,
            composite_score=0.35,
        ),
        status=IdeaStatus.READY,
    )

    bad_res = EditorialQualityGate.validate_idea(bad_idea)
    assert bad_res.is_valid is False
    assert any("generic programming tutorial" in r.lower() for r in bad_res.reasons)


def test_quality_gate_cliche_detection():
    """Verify Quality Gate detects and penalizes banned AI clichés."""
    clean_text = (
        "Focus is a fragile resource in remote work. Establishing clear asynchronous handoff protocols "
        "reduces friction and protects uninterrupted work blocks."
    )
    res_clean = EditorialQualityGate.validate_page_text(clean_text)
    assert res_clean.is_valid is True
    assert len(res_clean.detected_cliches) == 0

    cliche_text = (
        "In today's fast-paced world, in the digital age, unlocking the power of artificial intelligence is a game-changer. "
        "Let's dive in and delve into how to navigate the complexities."
    )
    res_cliche = EditorialQualityGate.validate_page_text(cliche_text)
    assert len(res_cliche.detected_cliches) >= 3


def test_quality_gate_unsolicited_code_detection():
    """Verify Quality Gate rejects code dumps when code is not permitted."""
    text_with_code = """
    To configure the system, run:
    pip install package-name
    npm install express
    def __init__(self):
        pass
    """
    res = EditorialQualityGate.validate_page_text(text_with_code, allow_code=False)
    assert res.code_dump_detected is True
    assert res.is_valid is False

    # Should pass when allow_code is True
    res_allowed = EditorialQualityGate.validate_page_text(text_with_code, allow_code=True)
    assert res_allowed.code_dump_detected is False


def test_editorial_coverage_matrix_does_not_inject_syntax():
    """Verify that build_requirement_coverage_matrix does NOT inject programming syntax topics."""
    intent = BookIntent(
        topic="Understanding Cloud Computing Without the Jargon",
        title="Cloud Computing Demystified",
        book_type="practical_guide",
        target_audience="Non-Technical Managers and Beginners",
        purpose="Explain cloud computing through mental models and analogies.",
        tone="Clear and approachable",
        technical_depth="introductory",
        is_technical=True,
        code_requirements=False,
        required_topics=["Compute & Virtualization", "Object Storage vs Block Storage", "Cost Economics"],
    )

    matrix = build_requirement_coverage_matrix(intent, chapters=[], all_pages=[])
    req_names = [item.requirement for item in matrix.items]
    assert "Core Syntax & Variables" not in req_names
    assert "Control Flow & Loops" not in req_names
    assert "Functions & Reusability" not in req_names


def test_classify_topic_distinguishes_practical_tech_from_coding_tutorial():
    """Verify classify_topic enables code/CLI requirements only for actual coding tutorials."""
    practical_tech = classify_topic("How AI Agents Actually Work", "Conceptual breakdown of reasoning loops and tool use")
    assert practical_tech.is_technical is True
    assert practical_tech.require_code_examples is False
    assert practical_tech.require_cli_commands is False
    assert practical_tech.require_practical_exercises is True

    coding_tutorial = classify_topic("Python Programming for Beginners", "Learn to write python code, scripts, and syntax from scratch")
    assert coding_tutorial.is_technical is True
    assert coding_tutorial.require_code_examples is True
    assert coding_tutorial.require_cli_commands is True


def test_promotion_quality_gate_and_multi_angle_writer():
    """Verify promotion article validation and multi-angle prompt construction."""
    writer = PromotionWriter()
    book = Book(
        id="test-book",
        title="The Architecture of Daily Habits",
        slug="daily-habits",
        category="Personal Growth",
        target_audience="Students and Professionals",
    )

    # Test mental model angle
    prompt_mm = writer._format_book_context(book, "https://vasukisquare.cc/book/daily-habits", angle_type="mental_model")
    assert "EDITORIAL ANGLE: Break down the core mental models" in prompt_mm
    assert "https://vasukisquare.cc/book/daily-habits" in prompt_mm

    # Test mistakes angle
    prompt_mb = writer._format_book_context(book, "https://vasukisquare.cc/book/daily-habits", angle_type="mistakes_breakdown")
    assert "EDITORIAL ANGLE: Focus on the top misconceptions" in prompt_mb

    # Test promotion post quality gate
    valid_post = PromotionPost(
        campaign_run_id="campaign-1",
        book_id="test-book",
        book_slug="daily-habits",
        title="Why Willpower Fails: The Architecture of Daily Habits",
        body_markdown=(
            "## Why Willpower Fails\n\n"
            "Most people rely on willpower when trying to build new routines. Behavioral science shows that "
            "environmental design and friction manipulation are vastly more reliable drivers of lasting change.\n\n"
            "### The Cue-Routine-Reward Framework\n"
            "Every habit begins with a clear trigger. By deliberately placing environmental cues in your direct sightline, "
            "you reduce the activation energy required to begin.\n\n"
            "### 3 Principles for Friction Reduction\n"
            "1. **Prep the environment**: Set out tools the night before.\n"
            "2. **The 2-minute rule**: Scale the initial action down until it is absurdly easy.\n"
            "3. **Habit stacking**: Anchor the new action to an established ritual.\n\n"
            "---\n\n"
            "For a complete, comprehensive guide on building sustainable daily routines, "
            "[Read the full guide online for free: The Architecture of Daily Habits](https://vasukisquare.cc/book/daily-habits)."
        ),
        canonical_url="https://vasukisquare.cc/book/daily-habits",
        tags=["productivity", "habits", "selfimprovement"],
    )

    q_res = EditorialQualityGate.validate_promotion_post(valid_post)
    assert q_res.is_valid is True
    assert len(q_res.reasons) == 0

    spam_post = PromotionPost(
        campaign_run_id="campaign-1",
        book_id="test-book",
        book_slug="daily-habits",
        title="Buy this book now!",
        body_markdown="Buy this book today! Read my new book with a special discount! Short text.",
        canonical_url="https://vasukisquare.cc/book/daily-habits",
    )

    q_spam_res = EditorialQualityGate.validate_promotion_post(spam_post)
    assert q_spam_res.is_valid is False
    assert any("promotional sales spam" in r.lower() for r in q_spam_res.reasons)
    assert any("too short" in r.lower() for r in q_spam_res.reasons)

