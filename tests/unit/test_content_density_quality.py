"""Comprehensive unit tests for interior content density, utilization budgeting, and type-specific enrichment."""

import pytest
from vasukisquare.book.layout import (
    ContentDensity,
    ContentBudget,
    PAGE_TYPE_SPECS,
    TechnicalPageType,
    LayoutType,
)
from vasukisquare.book.models import (
    Page,
    PageContent,
    PagePurpose,
    PageStyle,
    generate_id,
)
from vasukisquare.book.components import (
    TextBlock,
    CodeBlock,
    OutputBlock,
    CalloutBlock,
    TableBlock,
    TimelineBlock,
    TimelineEvent,
    CommonMistakeBlock,
)
from vasukisquare.renderer.overflow import (
    DensityEstimator,
    estimate_page_utilization,
    PageUtilization,
)
from vasukisquare.renderer.preflight import (
    preflight_page,
    preflight_book,
)
from vasukisquare.renderer.validator import ContentValidator
from vasukisquare.agents.writer import repair_underfilled_page


def test_underfilled_normal_page_fails_preflight_and_validation():
    """A normal content page with only a title and 30 words must be flagged as severely underfilled."""
    short_content = PageContent(
        headline="Key Features of Python",
        blocks=[
            TextBlock(text="Python is a popular programming language created by Guido van Rossum.")
        ],
    )
    page = Page(
        id=generate_id(),
        book_id="python-101",
        page_number=3,
        chapter_number=1,
        chapter_name="Foundations",
        page_type="chapter_content",
        layout="editorial",
        content=short_content,
    )

    util = estimate_page_utilization(page)
    assert util.is_underfilled is True
    assert util.is_hard_fail is True  # utilization is way under 45%
    assert util.content_units < 2

    report = preflight_page(page)
    assert report.valid is False
    assert any("severely underfilled" in err.lower() or "utilization" in err.lower() for err in report.errors)


def test_chapter_opener_low_utilization_passes():
    """Chapter opener pages naturally contain less text and must not trigger underfill errors."""
    opener_page = Page(
        id=generate_id(),
        book_id="python-101",
        page_number=2,
        chapter_number=1,
        chapter_name="Foundations of Python",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        icon="sparkles",
        content=PageContent(headline="Foundations of Python"),
    )

    util = estimate_page_utilization(opener_page)
    # Chapter openers have target 0.25 - 0.60 and should not be hard failed
    assert util.is_hard_fail is False

    report = preflight_page(opener_page)
    assert report.valid is True
    assert not any("severely underfilled" in err.lower() for err in report.errors)


def test_decorative_icon_excluded_from_content_height():
    """Decorative background icons or watermarks must not artificially inflate educational utilization."""
    estimator = DensityEstimator()

    page_with_text_only = PageContent(
        headline="History of Python",
        blocks=[
            TextBlock(text="Python was conceived in 1989 as a successor to ABC.")
        ],
    )
    util_plain = estimator.estimate_utilization(page_with_text_only)

    page_with_icon = Page(
        id=generate_id(),
        book_id="python-101",
        page_number=4,
        page_type="chapter_content",
        layout="editorial",
        icon="book-open",
        content=page_with_text_only,
    )
    util_icon = estimator.estimate_utilization(page_with_icon)

    # Educational content height must be identical regardless of icon presence
    assert abs(util_plain.estimated_height_mm - util_icon.estimated_height_mm) < 0.1
    assert util_icon.is_hard_fail is True


def test_code_page_with_code_output_prose_passes():
    """A rich technical page with explanation, code block, output block, and tip achieves target utilization."""
    rich_blocks = [
        TextBlock(
            text="Functions organize code into reusable, modular building blocks. In Python, functions are declared with the `def` keyword, "
            "support typed parameters and return values, and enable clean algorithmic abstraction across large codebases."
        ),
        CodeBlock(
            language="python",
            filename="functions_demo.py",
            code=(
                "def calculate_tax(amount: float, rate: float = 0.08) -> float:\n"
                "    \"\"\"Calculate total tax for given amount.\"\"\"\n"
                "    return round(amount * rate, 2)\n\n"
                "subtotal = 125.00\n"
                "tax = calculate_tax(subtotal)\n"
                "print(f'Subtotal: ${subtotal:.2f} | Tax: ${tax:.2f} | Total: ${subtotal + tax:.2f}')"
            ),
            caption="Listing 5.1: Function definition with default arguments.",
            line_numbers=True,
        ),
        OutputBlock(
            title="Console Output",
            content="Subtotal: $125.00 | Tax: $10.00 | Total: $135.00",
        ),
        CalloutBlock(
            title="Type Annotations",
            content="Always add type hints to function signatures. They make code self-documenting and prevent type-related bugs.",
            variant="tip",
        ),
        TextBlock(
            text="Functions can also be passed as first-class citizens to higher-order tools like `map()`, `filter()`, and custom decorators."
        ),
    ]
    page = Page(
        id=generate_id(),
        book_id="python-101",
        page_number=10,
        chapter_number=5,
        chapter_name="Functions & Scope",
        page_type="chapter_content",
        layout=LayoutType.CODE_FOCUS.value,
        content=PageContent(headline="Declaring Modular Functions", blocks=rich_blocks),
    )

    util = estimate_page_utilization(page)
    assert util.estimated_ratio >= 0.65
    assert util.is_underfilled is False
    assert util.is_hard_fail is False
    assert util.content_units >= 3

    report = preflight_page(page)
    assert report.valid is True


def test_repair_underfilled_history_page():
    """Underfilled history pages are enriched with timeline, impact analysis, and takeaway callouts."""
    sparse_history = PageContent(
        headline="History of Python",
        blocks=[
            TextBlock(text="Python was created by Guido van Rossum in the late 1980s.")
        ],
    )
    spec = PAGE_TYPE_SPECS[TechnicalPageType.HISTORY]

    repaired = repair_underfilled_page(
        sparse_history,
        spec=spec,
        primary_subject="Python Programming",
    )

    block_types = [getattr(b, "type", "") for b in repaired.blocks]
    assert "timeline" in block_types
    assert any(getattr(b, "type", "") in ("callout", "tip") for b in repaired.blocks)

    util = estimate_page_utilization(repaired)
    assert util.estimated_ratio >= 0.70
    assert util.is_hard_fail is False
    assert util.content_units >= 3


def test_repair_underfilled_features_page():
    """Underfilled features pages are enriched with structured feature breakdown, code snippet, and callout."""
    sparse_features = PageContent(
        headline="Key Features and Benefits of Python",
        blocks=[
            TextBlock(text="Python is a high-level language with many features.")
        ],
    )
    spec = PAGE_TYPE_SPECS[TechnicalPageType.FEATURES]

    repaired = repair_underfilled_page(
        sparse_features,
        spec=spec,
        primary_subject="Python Programming",
    )

    block_types = [getattr(b, "type", "") for b in repaired.blocks]
    assert "table" in block_types or "comparison" in block_types
    assert "code" in block_types
    assert "output" in block_types

    util = estimate_page_utilization(repaired)
    assert util.estimated_ratio >= 0.70
    assert util.is_hard_fail is False
    assert util.content_units >= 3


def test_python_code_block_filenames():
    """All code blocks in Python chapters must have filenames ending in .py."""
    spec = PAGE_TYPE_SPECS[TechnicalPageType.CODE_TUTORIAL]
    sparse_page = PageContent(
        headline="List Comprehensions",
        blocks=[
            TextBlock(text="List comprehensions provide a concise way to create lists.")
        ],
    )
    repaired = repair_underfilled_page(
        sparse_page,
        spec=spec,
        primary_subject="Python Programming",
    )

    code_blocks = [b for b in repaired.blocks if getattr(b, "type", "") == "code"]
    assert len(code_blocks) >= 1
    for cb in code_blocks:
        assert cb.filename.endswith(".py")
        assert not cb.filename.endswith(".sh")


def test_preflight_book_underfill_rate_threshold():
    """Book preflight must fail if > 15% of normal content pages are severely underfilled."""
    pages = []
    # 2 good pages
    for i in range(1, 3):
        pages.append(
            Page(
                id=generate_id(),
                book_id="python-101",
                page_number=i,
                page_type="chapter_content",
                layout="editorial",
                content=PageContent(
                    headline=f"Section {i}",
                    blocks=[
                        TextBlock(text="Substantive explanation teaching the architectural foundations and mechanical principles of Python." * 3),
                        CodeBlock(language="python", filename=f"demo_{i}.py", code="def run(): return 42\nprint(run())"),
                        OutputBlock(title="Output", content="42"),
                        CalloutBlock(title="Tip", content="Write clean code."),
                    ],
                ),
            )
        )
    # 2 underfilled pages (50% underfilled > 15% threshold)
    for i in range(3, 5):
        pages.append(
            Page(
                id=generate_id(),
                book_id="python-101",
                page_number=i,
                page_type="chapter_content",
                layout="editorial",
                content=PageContent(
                    headline=f"Section {i}",
                    blocks=[TextBlock(text="Short paragraph.")],
                ),
            )
        )

    report = preflight_book(pages)
    assert report.all_valid is False
    assert report.underfilled_pages >= 2
    assert any("density qa" in err.lower() or "underfilled" in err.lower() for err in report.overall_warnings or report.page_reports[2].errors)
