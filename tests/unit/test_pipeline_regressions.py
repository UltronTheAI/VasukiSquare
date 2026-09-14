"""Unit tests validating pipeline fixes for regressions A, B, C, D, E, F:
1. Terminal block literal newline escaping and multi-command splitting.
2. Glitched / meaningless single-character content page rejection.
3. Code blocks requiring comprehensive post-code walkthroughs/explanations.
4. Fake/inappropriate source rejection (eliminating synthetic ACM sources).
5. Empty visual component suppression.
6. Literal escaped characters audit across rendering layers.
"""

import pytest
from vasukisquare.book.components import (
    CalloutBlock,
    ChecklistBlock,
    CodeBlock,
    ComparisonBlock,
    OutputBlock,
    TableBlock,
    TerminalBlock,
    TerminalLine,
    TextBlock,
)
from vasukisquare.book.models import Page, PageContent
from vasukisquare.agents.content_validator import validate_generated_section, validate_terminal_command, validate_code_block
from vasukisquare.renderer.components import (
    ComponentRenderer,
    normalize_preformatted_text,
)
from vasukisquare.renderer.validator import ContentValidator
from vasukisquare.tools.search import MockSearchProvider


# ============================================================
# TEST A: TERMINAL NEWLINE NORMALIZATION & MULTI-COMMAND SPLIT
# ============================================================
def test_terminal_newline_splitting_and_rendering():
    """Terminal blocks with literal \\n or multiline strings must split into individual commands with $ prompt."""
    raw_cmd = "python -m venv env\\nsource env/bin/activate\\npip install -r requirements.txt"
    
    # Check validator recognizes valid commands
    assert validate_terminal_command(raw_cmd) is True

    # Check normalization
    norm = normalize_preformatted_text(raw_cmd)
    assert "\\n" not in norm
    assert len(norm.split("\n")) == 3

    # Render terminal block with single command containing newlines
    block = TerminalBlock(
        title="Setup Virtual Environment",
        shell="bash",
        lines=[TerminalLine(kind="command", text=raw_cmd)],
    )
    html = ComponentRenderer.render_terminal(block)
    
    # HTML must not contain literal \n
    assert "\\n" not in html
    # HTML should have 3 rendered command lines
    assert html.count("class=\"terminal-line is-command\"") == 3
    assert "python -m venv env" in html
    assert "source env/bin/activate" in html
    assert "pip install -r requirements.txt" in html


# ============================================================
# TEST B: GLITCHED / SINGLE-CHAR PAGE CONTENT REJECTION
# ============================================================
def test_glitched_junk_content_rejection():
    """Validator must strictly reject single-character headings or repeated 'r' nonsense paragraphs."""
    # Glitched heading 'r'
    glitched_heading = {
        "headline": "r",
        "lead_paragraph": "Python is a versatile programming language used widely in data science and web development.",
    }
    val_h = validate_generated_section(glitched_heading, topic="Python Basics")
    assert val_h.valid is False
    assert any("1-2 meaningless characters" in r for r in val_h.reasons)

    # Glitched repeated paragraph 'r\nr\nr'
    glitched_para = {
        "headline": "Python Functions",
        "lead_paragraph": "r\nr\nr\nr\nr\nr",
    }
    val_p = validate_generated_section(glitched_para, topic="Python Functions")
    assert val_p.valid is False
    assert any("repeated single-character junk" in r for r in val_p.reasons)


# ============================================================
# TEST C: CODE EXPLANATION / WALKTHROUGH REQUIREMENT
# ============================================================
def test_code_explanation_required():
    """Every code block must be accompanied by an explanation walkthrough explaining how it works."""
    # Code snippet without explanation
    unexplained_code = {
        "headline": "Working with Lists",
        "lead_paragraph": "Lists are ordered, mutable sequences in Python.",
        "code_snippet": "numbers = [1, 2, 3]\nprint(sum(numbers))",
        "code_explanation": "",  # Missing!
    }
    val_missing = validate_generated_section(unexplained_code, topic="Working with Lists")
    assert val_missing.valid is False
    assert any("Code example lacks an explanation" in r for r in val_missing.reasons)

    # Code snippet with proper explanation
    explained_code = {
        "headline": "Working with Lists",
        "lead_paragraph": "Lists are ordered, mutable sequences in Python.",
        "code_snippet": "numbers = [1, 2, 3]\nprint(sum(numbers))",
        "code_explanation": "The sum() function iterates over the list elements and returns their accumulated total.",
    }
    val_ok = validate_generated_section(explained_code, topic="Working with Lists")
    assert val_ok.valid is True


# ============================================================
# TEST D: FAKE / INAPPROPRIATE SOURCE REJECTION
# ============================================================
@pytest.mark.asyncio
async def test_search_provider_authoritative_sources():
    """Search provider must never return synthetic ACM URLs for programming guides."""
    provider = MockSearchProvider()
    docs = await provider.search("Python list comprehensions")
    
    assert len(docs) > 0
    for doc in docs:
        assert "acm.org" not in doc.url
        assert "Primary Specification" not in doc.title
        assert any(domain in doc.url for domain in ["python.org", "realpython.com", "peps.python.org", "developer.mozilla.org"])


# ============================================================
# TEST E: EMPTY VISUAL COMPONENT SUPPRESSION
# ============================================================
def test_empty_visual_components_suppressed():
    """Empty tables, checklists, comparisons, and callouts must render as empty string without empty containers."""
    # Empty table
    empty_table = TableBlock(caption="Empty", columns=["A", "B"], rows=[])
    assert ComponentRenderer.render_table(empty_table) == ""

    # Empty checklist
    empty_chk = ChecklistBlock(title="Empty Checklist", items=[])
    assert ComponentRenderer.render_block(empty_chk) == ""

    # Empty comparison
    empty_comp = ComparisonBlock(title="Empty Comparison", left_items=[], right_items=[])
    assert ComponentRenderer.render_block(empty_comp) == ""

    # Empty callout
    empty_callout = CalloutBlock(title="Empty", content="")
    assert ComponentRenderer.render_callout(empty_callout) == ""


# ============================================================
# TEST F: FULL BOOK AUDIT SYSTEM
# ============================================================
def test_full_book_audit():
    """Audit system must check all 15 quality criteria and report status correctly."""
    clean_page = Page(
        id="p1",
        book_id="python-guide",
        page_number=1,
        page_type="content",
        layout="code_focus",
        theme="light",
        content=PageContent(
            headline="Python Variables & Data Types",
            blocks=[
                TextBlock(text="Variables in Python store dynamic references to typed objects in memory."),
                CodeBlock(
                    language="python",
                    code="age: int = 25\nname: str = 'Alice'\nprint(f'{name} is {age}')",
                    caption="Listing 1.1: Declaring variables with type annotations.",
                ),
                OutputBlock(title="Output", content="Alice is 25"),
                TextBlock(text="This code binds integer and string literals to annotated identifiers and formats them into standard output."),
                CalloutBlock(variant="tip", title="Type Hints", content="Use type hints to clarify function signatures and enable static type checking with mypy."),
            ],
        ),
    )

    audit_result = ContentValidator.audit_book([clean_page], topic="Python Basics", language="python")
    assert audit_result["is_valid"] is True
    assert audit_result["issues_count"] == 0
    assert len(audit_result["passed_checks"]) >= 6
