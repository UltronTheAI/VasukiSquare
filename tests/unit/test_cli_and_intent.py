"""Unit tests for CLI arguments, BookIntent inference, Title constraints, Non-technical handling, and Manifest generation."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from vasukisquare.book.models import BookIntent, validate_book_title
from vasukisquare.agents.editorial import EditorialPlannerAgent, clean_and_resolve_title
from vasukisquare.book.layout import VisualAnchorType
from vasukisquare.research.planner import ResearchPlanner
from vasukisquare.config import Settings
from vasukisquare.pipeline.orchestrator import EbookGenerationPipeline


@pytest.fixture
def mock_settings():
    return Settings(vasukisquare_mock_mode=True)


def test_validate_book_title():
    """Verify strict title validation rules (<= 50 chars, no commentary, clean)."""
    assert validate_book_title("How to Build Better Daily Habits") is True
    assert validate_book_title("LioranDB for Noobs") is True
    assert validate_book_title("A" * 50) is True
    assert validate_book_title("A" * 51) is False
    assert validate_book_title("") is False
    assert validate_book_title(None) is False
    assert validate_book_title("Here is the title of the book") is False
    assert validate_book_title("Title: My Great Book") is False
    assert validate_book_title("Book Title: My Great Book") is False
    assert validate_book_title("Multiline\nTitle") is False


def test_clean_and_resolve_title_explicit():
    """Explicit titles must be preserved verbatim or cleaned cleanly to <= 50 chars."""
    t1 = clean_and_resolve_title(
        topic="How to Build Better Daily Habits",
        explicit_title="Atomic Daily Routines",
    )
    assert t1 == "Atomic Daily Routines"
    assert len(t1) <= 50

    # Quoted explicit title
    t2 = clean_and_resolve_title(
        topic="How to Build Better Daily Habits",
        explicit_title='"The Habit Blueprint"',
    )
    assert t2 == "The Habit Blueprint"

    # Very long explicit title truncated to <= 50 chars
    long_title = "This Is An Extremely Long Explicit Book Title That Definitely Exceeds Fifty Characters Limit"
    t3 = clean_and_resolve_title(topic="Test", explicit_title=long_title)
    assert len(t3) <= 50
    assert t3.endswith("...")


def test_clean_and_resolve_title_from_topic():
    """When title is omitted, resolve from topic and enforce <= 50 chars."""
    # Short topic used directly
    t1 = clean_and_resolve_title(topic="How to Build Better Daily Habits")
    assert t1 == "How to Build Better Daily Habits"
    assert len(t1) <= 50

    # Topic with subtitle after colon
    t2 = clean_and_resolve_title(topic="LioranDB for Noobs: From Zero Knowledge to Building Real Apps with LioranDB")
    assert t2 == "LioranDB for Noobs"
    assert len(t2) <= 50

    # Verbose long topic without colon
    long_topic = "A Very Comprehensive and In-Depth Guide to Advanced Distributed Systems Architecture and Engineering"
    t3 = clean_and_resolve_title(topic=long_topic)
    assert len(t3) <= 50


@pytest.mark.asyncio
async def test_infer_intent_technical(mock_settings):
    """Test intent inference for technical book."""
    agent = EditorialPlannerAgent(settings=mock_settings)
    intent = await agent.infer_intent(
        topic="LioranDB for Noobs: From Zero Knowledge to Building Real Apps with LioranDB",
        target_pages=40,
    )
    assert intent.is_technical is True
    assert intent.code_requirements is True
    assert intent.target_pages == 40
    assert len(intent.title) <= 50


@pytest.mark.asyncio
async def test_infer_intent_non_technical_with_prompt(mock_settings):
    """Test intent inference for non-technical book with user prompt."""
    agent = EditorialPlannerAgent(settings=mock_settings)
    prompt = (
        "Write a practical beginner-friendly guide for students and young professionals. "
        "Focus on sustainable habits, realistic examples, exercises, checklists, common mistakes, "
        "and a simple 30-day improvement plan."
    )
    intent = await agent.infer_intent(
        topic="How to Build Better Daily Habits",
        prompt=prompt,
        title="Better Daily Habits",
        target_pages=30,
    )
    assert intent.is_technical is False
    assert intent.code_requirements is False
    assert intent.primary_programming_language is None
    assert intent.title == "Better Daily Habits"
    assert "exercises" in intent.desired_elements
    assert "checklists" in intent.desired_elements
    assert any("30-day" in e for e in intent.desired_elements)


@pytest.mark.asyncio
async def test_non_technical_chapters_have_no_code_anchors(mock_settings):
    """Non-technical books must never generate code anchors in deterministic plans."""
    agent = EditorialPlannerAgent(settings=mock_settings)
    intent = await agent.infer_intent(
        topic="How to Build Better Daily Habits",
        prompt="Focus on exercises and checklists.",
        target_pages=20,
    )
    book_plan = await agent.generate_book_plan(
        topic="How to Build Better Daily Habits",
        intent=intent,
        target_pages=20,
    )
    assert book_plan.title == intent.title
    # Verify no section has VisualAnchorType.CODE
    for ch in book_plan.chapters:
        for sec in ch.sections:
            assert VisualAnchorType.CODE not in sec.visual_anchors


@pytest.mark.asyncio
async def test_research_planner_adapts_to_non_technical(mock_settings):
    """Research planner should generate psychological/practical queries for non-technical topics."""
    planner = ResearchPlanner(settings=mock_settings)
    intent = BookIntent(
        topic="How to Build Better Daily Habits",
        title="Better Daily Habits",
        is_technical=False,
        code_requirements=False,
    )
    plan = await planner.plan_research("How to Build Better Daily Habits", intent=intent)
    assert len(plan.queries) >= 4
    # None of the queries should ask for GitHub repository or API SDKs
    query_texts = " ".join([q.query.lower() for q in plan.queries])
    assert "github" not in query_texts
    assert "sdk" not in query_texts
    assert "crud" not in query_texts


@pytest.mark.asyncio
async def test_pipeline_generates_manifest_json(mock_settings):
    """Pipeline run in mock mode should produce book_manifest.json with correct metadata."""
    pipeline = EbookGenerationPipeline(settings=mock_settings)
    with TemporaryDirectory() as tmpdir:
        prompt_text = "Write a beginner-friendly habit guide with exercises and checklists."
        state = await pipeline.run(
            topic="How to Build Better Daily Habits",
            title="Mastering Daily Habits",
            prompt=prompt_text,
            target_pages=8,
            output_dir=tmpdir,
            generate_pdf=False,
            persist_db=False,
            resume=False,
        )
        manifest_path = Path(tmpdir) / "book_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["topic"] == "How to Build Better Daily Habits"
        assert manifest["title"] == "Mastering Daily Habits"
        assert manifest["prompt"] == prompt_text
        assert manifest["is_technical"] is False
        assert manifest["actual_pages"] == len(state.pages)
        assert "book_manifest_json" in state.artifacts

