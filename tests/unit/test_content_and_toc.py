"""Unit tests for Python content generation, dynamic TOC rendering, and topic relevance validation."""

import pytest
from vasukisquare.book.components import (
    CodeBlock,
    TextBlock,
    TocBlock,
    TocEntry,
)
from vasukisquare.book.layout import LayoutType, VisualAnchorType
from vasukisquare.book.models import (
    BookIntent,
    BookPlan,
    Page,
    PageContent,
    PlannedPage,
)
from vasukisquare.agents.writer import PageWriterAgent
from vasukisquare.renderer.components import ComponentRenderer
from vasukisquare.renderer.validator import ContentValidator
from vasukisquare.design.theme import Theme


from vasukisquare.config import Settings


@pytest.mark.asyncio
async def test_writer_generates_python_code():
    writer = PageWriterAgent(settings=Settings(vasukisquare_mock_mode=True))
    intent = BookIntent(
        book_type="beginner_guide",
        target_audience="Beginners",
        technical_depth="introductory",
        primary_programming_language="python",
    )
    plan = BookPlan(
        title="Getting Started with Python",
        subtitle="A Beginner's Guide",
        description="Python tutorial",
        intent=intent,
    )

    planned_page = PlannedPage(
        page_number=6,
        page_type="chapter_content",
        layout=LayoutType.CODE_FOCUS.value,
        chapter_number=1,
        chapter_title="Introduction to Python",
        visual_anchor=VisualAnchorType.CODE,
        brief="Installing Python & Your First Hello World",
    )

    page = await writer.write_page(planned_page, plan)
    assert page.page_number == 6
    assert len(page.content.blocks) > 0

    code_blocks = [b for b in page.content.blocks if isinstance(b, CodeBlock)]
    assert len(code_blocks) == 1
    assert code_blocks[0].language == "python"
    assert "print(" in code_blocks[0].code
    assert "raft" not in code_blocks[0].code.lower()
    assert "pub struct" not in code_blocks[0].code


def test_toc_component_rendering():
    entries = [
        TocEntry(chapter_number=1, title="Introduction to Python", page_number=5, icon="terminal"),
        TocEntry(chapter_number=2, title="Variables and Data Types", page_number=9, icon="code"),
        TocEntry(chapter_number=3, title="Control Flow & Conditionals", page_number=13, icon="layers"),
    ]
    toc_block = TocBlock(
        title="Table of Contents",
        subtitle="Complete Book Outline",
        entries=entries,
    )

    html_out = ComponentRenderer.render_block(toc_block, theme=Theme.LIGHT)
    assert "component-toc" in html_out
    assert "Table of Contents" in html_out
    assert "Introduction to Python" in html_out
    assert "Variables and Data Types" in html_out
    assert "Chapter 1" in html_out
    assert "toc-dots-leader" in html_out
    assert "5" in html_out
    assert "9" in html_out
    assert "13" in html_out


def test_toc_page_no_duplicate_title_in_html():
    """TOC page must render exactly one 'Table of Contents' title and avoid duplicate headline."""
    from vasukisquare.renderer.html import HTMLRenderer

    entries = [
        TocEntry(chapter_number=1, title="Introduction to Good Habits", page_number=4, icon="sparkles"),
        TocEntry(chapter_number=2, title="Building Blocks of Good Habits", page_number=7, icon="compass"),
    ]
    toc_block = TocBlock(
        title="Table of Contents",
        subtitle="A Guide to Good Habits",
        entries=entries,
    )
    page = Page(
        id="toc-page-id",
        book_id="habits-101",
        page_number=2,
        page_type="toc",
        layout="toc",
        theme=Theme.LIGHT,
        content=PageContent(headline="Table of Contents", blocks=[toc_block]),
    )

    renderer = HTMLRenderer()
    html_single = renderer.render_page(page, book_title="Good Habits", running_title="GOOD HABITS")
    assert '<h2 class="content-headline">' not in html_single
    assert '<h1 class="toc-title">Table of Contents</h1>' in html_single
    assert '<div class="typo-eyebrow">Contents</div>' in html_single
    assert '<p class="toc-subtitle">A Guide to Good Habits</p>' in html_single
    assert "GOOD HABITS" in html_single

    html_book = renderer.render_book([page], book_title="Good Habits", running_title="GOOD HABITS")
    assert '<h2 class="content-headline">' not in html_book
    assert '<h1 class="toc-title">Table of Contents</h1>' in html_book
    assert '<div class="typo-eyebrow">Contents</div>' in html_book



def test_validator_detects_topic_relevance():
    intent = BookIntent(primary_programming_language="python")

    valid_page = Page(
        book_id="py-1",
        page_number=5,
        content=PageContent(
            headline="Python Functions",
            blocks=[
                TextBlock(text="Functions in Python are defined with the def keyword."),
                CodeBlock(language="python", code="def greet(name: str) -> str:\n    return f'Hello, {name}'"),
            ],
        ),
    )

    errors = ContentValidator.validate_topic_relevance([valid_page], expected_topic="Getting Started with Python", expected_language="python")
    assert len(errors) == 0

    invalid_page = Page(
        book_id="py-1",
        page_number=6,
        content=PageContent(
            headline="Consensus Engines",
            blocks=[
                TextBlock(text="The consensus engine coordinates state replication with RaftNode transitions."),
                CodeBlock(language="rust", code="pub struct RaftNode { node_id: String }"),
            ],
        ),
    )

    errors = ContentValidator.validate_topic_relevance([invalid_page], expected_topic="Getting Started with Python", expected_language="python")
    assert len(errors) >= 1
    assert any("RUST" in e for e in errors) or any("raftnode" in e for e in errors)


def test_validator_detects_duplicate_pages():
    p1 = Page(
        book_id="book-1",
        page_number=5,
        content=PageContent(
            headline="Identical Lesson",
            blocks=[TextBlock(text="This is an identical block of lesson text that should not repeat across distinct book pages.")],
        ),
    )
    p2 = Page(
        book_id="book-1",
        page_number=8,
        content=PageContent(
            headline="Identical Lesson",
            blocks=[TextBlock(text="This is an identical block of lesson text that should not repeat across distinct book pages.")],
        ),
    )

    errors = ContentValidator.validate_no_duplicate_pages([p1, p2])
    assert len(errors) == 1
    assert "Page 8 is an exact duplicate of Page 5" in errors[0]
