"""Unit tests for the Editorial Planning Agent, BookIntent, and BookPlan models."""

import asyncio
import pytest
from vasukisquare.config import Settings
from vasukisquare.agents.editorial import EditorialPlannerAgent
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import (
    BookIntent,
    BookPlan,
    PlannedChapter,
    PlannedPage,
    VisualAnchorType,
)
from vasukisquare.design.theme import Theme
from vasukisquare.research.models import ResearchCorpus, SourceDocument, SourceType


def test_book_intent_inference():
    agent = EditorialPlannerAgent(settings=Settings(vasukisquare_mock_mode=True))
    
    async def _test():
        intent = await agent.infer_intent("Advanced Rust Memory Management and Concurrency")
        assert intent.book_type == "technical_deep_dive"
        assert intent.technical_depth == "advanced"
        assert intent.code_requirements is True
        assert intent.diagram_requirements is True
        assert intent.chapter_count >= 4

    asyncio.run(_test())


def test_book_plan_generation_structure():
    agent = EditorialPlannerAgent(settings=Settings(vasukisquare_mock_mode=True))
    
    async def _test():
        prompt = "Distributed Consensus Algorithms in Modern Databases"
        intent = BookIntent(
            book_type="architecture_guide",
            target_audience="Distributed Systems Engineers",
            technical_depth="expert",
            tone="authoritative",
            approximate_length="standard",
            chapter_count=5,
            research_intensity="deep",
            code_requirements=True,
            diagram_requirements=True,
        )
        corpus = ResearchCorpus(
            topic=prompt,
            documents=[
                SourceDocument(
                    url="https://raft.github.io/raft.pdf",
                    title="In Search of an Understandable Consensus Algorithm",
                    source_type=SourceType.ACADEMIC,
                )
            ],
            key_findings=["Raft election", "Log replication"],
        )

        plan: BookPlan = await agent.generate_book_plan(prompt, intent, corpus)

        # 1. Metadata assertions
        assert "Distributed Consensus" in plan.title
        assert plan.intent.technical_depth == "expert"
        assert len(plan.chapters) == 5

        # 2. Frontmatter assertions (Cover, Imprint, Copyright, TOC)
        assert len(plan.frontmatter_pages) == 4
        assert plan.frontmatter_pages[0].page_number == 1
        assert plan.frontmatter_pages[0].layout == LayoutType.COVER.value
        assert plan.frontmatter_pages[1].page_number == 2
        assert plan.frontmatter_pages[2].page_number == 3
        assert plan.frontmatter_pages[2].layout == LayoutType.COPYRIGHT.value
        assert plan.frontmatter_pages[3].page_number == 4
        assert plan.frontmatter_pages[3].layout == LayoutType.TOC.value

        # 3. Chapter structure, page budgets, and theme alternation
        for ch in plan.chapters:
            assert ch.page_budget >= 2
            # Odd chapters dark, even chapters light
            if ch.chapter_number % 2 == 1:
                assert ch.theme == Theme.DARK
            else:
                assert ch.theme == Theme.LIGHT

            # Lucide icon present
            assert ch.icon is not None

        # 4. Backmatter assertions (References, Acknowledgement, Thank You)
        backmatter_layouts = [p.layout for p in plan.backmatter_pages]
        assert LayoutType.REFERENCES.value in backmatter_layouts
        assert LayoutType.THANK_YOU.value in backmatter_layouts
        assert plan.backmatter_pages[-1].layout == LayoutType.THANK_YOU.value

        # 5. Full sequential page numbering and total summation
        all_pages = plan.all_planned_pages
        assert len(all_pages) == plan.total_pages
        for idx, page in enumerate(all_pages):
            assert page.page_number == idx + 1

        # 6. Chapter opener verification: exactly 1 per chapter, theme matches
        opener_pages = [p for p in all_pages if p.layout == LayoutType.CHAPTER_OPENER.value]
        assert len(opener_pages) == len(plan.chapters)
        for opener in opener_pages:
            assert opener.chapter_number is not None
            assert opener.chapter_title is not None
            assert opener.icon is not None
            # Theme check
            expected_theme = Theme.DARK if opener.chapter_number % 2 == 1 else Theme.LIGHT
            assert opener.theme == expected_theme

        # 7. Visual anchor verification across content pages
        visual_anchors = [p.visual_anchor for p in all_pages if p.visual_anchor is not None]
        assert len(visual_anchors) > 0
        assert VisualAnchorType.CODE in visual_anchors or VisualAnchorType.COMPARISON in visual_anchors

    asyncio.run(_test())


def test_deterministic_repeatability():
    agent = EditorialPlannerAgent(settings=Settings(vasukisquare_mock_mode=True))

    async def _test():
        prompt = "Microservice Observability and OpenTelemetry"
        plan1 = await agent.generate_book_plan(prompt)
        plan2 = await agent.generate_book_plan(prompt)

        assert plan1.title == plan2.title
        assert plan1.total_pages == plan2.total_pages
        assert len(plan1.chapters) == len(plan2.chapters)
        for c1, c2 in zip(plan1.chapters, plan2.chapters):
            assert c1.title == c2.title
            assert c1.theme == c2.theme
            assert c1.page_budget == c2.page_budget

    asyncio.run(_test())


def test_python_beginner_planning_and_chapters():
    agent = EditorialPlannerAgent(settings=Settings(vasukisquare_mock_mode=True))

    async def _test():
        prompt = "Getting Started with Python: A Beginner's Guide from Zero to Building Your First Real Programs"
        intent = await agent.infer_intent(prompt)

        assert intent.primary_programming_language == "python"
        assert intent.technical_depth == "introductory"
        assert "beginner" in intent.target_audience.lower() or "new programmer" in intent.target_audience.lower()
        assert intent.book_type == "beginner_guide"

        plan = await agent.generate_book_plan(prompt, intent, target_pages=40)
        assert plan.total_pages == 40
        assert len(plan.chapters) >= 6

        # Check that chapters are about Python and not distributed databases
        all_titles = " ".join(ch.title for ch in plan.chapters).lower()
        assert "python" in all_titles or "variable" in all_titles or "function" in all_titles
        assert "raft" not in all_titles
        assert "lsm" not in all_titles

    asyncio.run(_test())


