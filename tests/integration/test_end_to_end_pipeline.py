"""End-to-end integration tests for the full VasukiSquare ebook generation pipeline."""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from vasukisquare.config import Settings
from vasukisquare.pipeline.orchestrator import EbookGenerationPipeline
from vasukisquare.pipeline.state import GenerationState
from vasukisquare.design.theme import Theme
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.components import CodeBlock
from tests.integration.test_database import create_mock_db


@pytest.mark.asyncio
async def test_end_to_end_pipeline_execution(tmp_path: Path):
    """Verify that the full generation pipeline runs end-to-end and produces all required artifacts."""
    output_dir = tmp_path / "pipeline_out"
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        app_env="test",
        groq_api_key="gsk_test_key_dummy",
        groq_model="llama-3.3-70b-versatile",
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="vasukisquare_test",
    )

    pipeline = EbookGenerationPipeline(settings=settings)

    # Wire up mock database so no live MongoDB instance is strictly required
    mock_db = create_mock_db()
    pipeline.db_manager.db = mock_db

    topic = "Modern Distributed Key-Value Stores: LSM-Trees, Raft, and Consistent Hashing"

    state = await pipeline.run(
        topic=topic,
        target_pages=15,
        output_dir=output_dir,
        generate_pdf=False,  # Skip headless browser launch during fast unit test
        save_raster_cover=False,
        persist_db=True,
    )

    # 1. State Invariants
    assert state.book is not None
    assert state.intent is not None
    assert state.book_plan is not None
    assert state.research_corpus is not None
    assert len(state.research_corpus.documents) > 0
    assert len(state.pages) > 0
    assert state.cover is not None
    assert state.assembled_html is not None
    assert len(state.assembled_html) > 0

    # 2. File Artifacts on Disk
    assert (output_dir / "book.html").exists()
    assert (output_dir / "cover.html").exists()
    assert (output_dir / "research.json").exists()
    assert (output_dir / "book_plan.json").exists()

    pages_dir = output_dir / "pages"
    assert pages_dir.exists()
    page_files = list(pages_dir.glob("page_*.html"))
    assert len(page_files) == len(state.pages)

    # Check JSON validity
    with open(output_dir / "research.json", "r", encoding="utf-8") as f:
        research_data = json.load(f)
        assert "documents" in research_data
        assert len(research_data["documents"]) > 0

    with open(output_dir / "book_plan.json", "r", encoding="utf-8") as f:
        plan_data = json.load(f)
        assert "title" in plan_data
        assert "chapters" in plan_data

    # 3. Linked-List Page Graph Invariants
    pages = state.pages
    assert pages[0].previous_page_id is None
    assert pages[-1].next_page_id is None
    for i in range(1, len(pages) - 1):
        assert pages[i].previous_page_id == pages[i - 1].id
        assert pages[i].next_page_id == pages[i + 1].id

    # 4. Book document links
    assert state.book.starting_page_id == pages[0].id
    assert state.book.cover_id == state.cover.id
    assert state.book.page_count == len(pages)

    # 5. Theme rules: odd dark, even light
    for page in pages:
        if page.chapter_number is not None and page.chapter_number > 0:
            if page.chapter_number % 2 == 1:
                assert page.theme == Theme.DARK.value
            else:
                assert page.theme == Theme.LIGHT.value

    # 6. Chapter opener validation
    opener_pages = [p for p in pages if p.layout == LayoutType.CHAPTER_OPENER.value]
    for opener in opener_pages:
        assert opener.chapter_number is not None
        assert opener.chapter_name is not None
        assert opener.icon is not None
        # Opener HTML must contain chapter number
        assert f"Chapter {opener.chapter_number}" in opener.html
        assert "chapter-title" in opener.html


@pytest.mark.asyncio
async def test_pipeline_retry_and_error_handling(tmp_path: Path):
    """Verify that stage error handlers record errors cleanly in PipelineState."""
    settings = Settings(
        app_env="test",
        groq_api_key="gsk_test_key_dummy",
        groq_model="llama-3.3-70b-versatile",
    )
    pipeline = EbookGenerationPipeline(settings=settings)

    # Simulate database persistence failure
    mock_db = MagicMock()
    mock_db["books"].insert_one.side_effect = Exception("Mongo connection timed out")
    mock_db["pages"].insert_many.side_effect = Exception("Mongo connection timed out")
    pipeline.db_manager.db = mock_db

    state = await pipeline.run(
        topic="Fault Tolerant Systems",
        target_pages=10,
        output_dir=tmp_path / "fault_test",
        generate_pdf=False,
        save_raster_cover=False,
        persist_db=True,
    )

    # The pipeline should complete file rendering gracefully even if DB persistence logs an error
    assert (tmp_path / "fault_test" / "book.html").exists()
    assert any("MongoDB" in err for err in state.errors)


@pytest.mark.asyncio
async def test_python_beginner_pipeline_end_to_end(tmp_path: Path):
    """Verify that generating a Python beginner guide produces topical content, valid TOC, and no database demo copy."""
    output_dir = tmp_path / "python_book_out"
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        app_env="test",
        groq_api_key="gsk_test_key_dummy",
        groq_model="llama-3.3-70b-versatile",
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="vasukisquare_test",
    )

    pipeline = EbookGenerationPipeline(settings=settings)
    mock_db = create_mock_db()
    pipeline.db_manager.db = mock_db

    topic = "Getting Started with Python: A Beginner's Guide from Zero to Building Your First Real Programs"

    state = await pipeline.run(
        topic=topic,
        target_pages=40,
        output_dir=output_dir,
        generate_pdf=False,
        save_raster_cover=False,
        persist_db=True,
    )

    # 1. State Invariants & Page Count
    assert state.book is not None
    assert len(state.pages) == 40
    assert state.intent.primary_programming_language == "python"
    assert state.intent.technical_depth == "introductory"

    # 2. Check Table of Contents Page (Page 4)
    toc_page = state.pages[3]
    assert toc_page.page_number == 4
    assert toc_page.layout == LayoutType.TOC.value
    assert "component-toc" in toc_page.html
    assert "Chapter 1" in toc_page.html
    assert "Introduction to Python" in toc_page.html

    # 3. Content Relevance across all pages: must contain Python, zero Raft/B-Tree leaks
    assembled = state.assembled_html.lower()
    assert "python" in assembled
    assert "language-python" in assembled or "hl-nb" in assembled or "def " in assembled
    assert "raftnode" not in assembled
    assert "memtable / wal" not in assembled
    assert "b+ tree" not in assembled

    # Verify at least one code block has Python code
    all_code_blocks = [
        b for p in state.pages for b in p.content.blocks if isinstance(b, CodeBlock)
    ]
    assert len(all_code_blocks) > 0
    assert any("print(" in b.code or "def " in b.code for b in all_code_blocks)

    # 4. Acknowledgement & References
    ack_page = [p for p in state.pages if p.layout == LayoutType.ACKNOWLEDGEMENT.value][0]
    assert "Python" in ack_page.html

    refs_page = [p for p in state.pages if p.layout == LayoutType.REFERENCES.value][0]
    assert len(refs_page.content.blocks) > 0

    # 5. Output files exist
    assert (output_dir / "book.html").exists()
    assert (output_dir / "research.json").exists()
    assert (output_dir / "book_plan.json").exists()

