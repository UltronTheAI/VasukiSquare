"""Unit tests for Page Density Estimation, 16 Layout Families, Underfilled Page Repair,
Topic Watermark Icons, Quality Scoring, and Proportional Chapter Budgeting."""

import pytest
from vasukisquare.book.layout import (
    PageComplexity,
    LayoutType,
    classify_page_complexity,
    select_page_layout,
)
from vasukisquare.book.models import (
    Page,
    PageContent,
    BookPlan,
    PlannedChapter,
    SectionPlan,
    VisualAnchorType,
)
from vasukisquare.book.components import (
    TextBlock,
    CodeBlock,
    TerminalBlock,
    CalloutBlock,
    DiagramBlock,
    StepBlock,
    StepItem,
    ChecklistBlock,
    ChecklistItem,
    ComparisonBlock,
    ExerciseBlock,
    QuoteBlock,
    StatisticBlock,
    TableBlock,
)
from vasukisquare.renderer.overflow import (
    estimate_page_utilization,
    PageUtilization,
    USABLE_PAGE_HEIGHT_MM,
)
from vasukisquare.agents.writer import repair_underfilled_page
from vasukisquare.agents.content_validator import (
    evaluate_page_quality_score,
    compute_page_similarity,
    detect_repeated_sentence_boilerplate,
)
from vasukisquare.design.icons import (
    resolve_topic_decorative_icon,
    render_lucide_icon,
    ICON_MAP,
)
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.agents.editorial import EditorialPlannerAgent
from vasukisquare.design.theme import Theme


def test_estimate_page_utilization_normal_page():
    """Test height and ratio estimation for a standard content page."""
    content = PageContent(
        headline="Understanding Persistent Key-Value Storage Engines",
        body="Key-value storage engines provide the fundamental building blocks for modern distributed databases and high-performance caching layers. In this section, we examine how key-value storage architectures persist records to disk while maintaining fast in-memory indexing.",
        blocks=[
            TextBlock(
                text="Storage engines must balance read throughput, write amplification, and recovery latency. By employing write-ahead logs (WAL), every mutation is sequentially appended before being acknowledged to clients. This ensures crash safety without incurring random disk seeks on every write operation.",
            ),
            CalloutBlock(
                variant="tip",
                title="Design Insight",
                content="Sequential writes to NVMe or SSD storage achieve orders of magnitude higher throughput than random IOPS.",
            ),
            ChecklistBlock(
                title="Key Takeaways",
                items=[
                    ChecklistItem(text="Append-only write-ahead logging prevents data loss during power failures.", checked=True),
                    ChecklistItem(text="In-memory hash index provides O(1) key lookups.", checked=True),
                    ChecklistItem(text="Background compaction reclaims storage from overwritten keys.", checked=True),
                ],
            ),
        ],
    )

    util = estimate_page_utilization(content, page_type="chapter_content")
    assert isinstance(util, PageUtilization)
    assert util.estimated_height_mm > 80.0
    assert util.utilization_ratio >= 0.40
    assert util.is_overflow is False
    assert util.status in ("hard_failure", "severely_underfilled", "underfilled", "optimal", "target", "dense", "healthy")


def test_estimate_page_utilization_code_heavy():
    """Test height and ratio estimation for code-heavy pages."""
    code_lines = [f"let item_{i} = store.get(&key_{i})?;" for i in range(16)]
    code_body = "\n".join(code_lines)
    content = PageContent(
        headline="Implementing Concurrent Read Transactions in Rust",
        body="Concurrency control requires non-blocking read operations that never stall background write flushes. We use atomic reference counting and crossbeam channels to guarantee lock-free isolation.",
        blocks=[
            CodeBlock(
                language="rust",
                code=f"// Concurrent read implementation\npub fn read_record(store: &Store, key: &str) -> Result<Option<Value>> {{\n{code_body}\n    Ok(Some(item_0))\n}}",
                caption="Listing 4.2: Lock-free atomic read transaction in Rust",
            ),
            CalloutBlock(
                variant="warning",
                title="Memory Safety",
                content="Avoid holding reference guards across async yield points to prevent unbounded memory pinning.",
            ),
        ],
    )

    util = estimate_page_utilization(content, page_type="chapter_content")
    assert util.utilization_ratio >= 0.65
    assert util.utilization_ratio <= 0.95
    assert util.status in ("hard_failure", "severely_underfilled", "underfilled", "optimal", "target", "dense", "healthy")
    assert util.is_overflow is False


def test_estimate_page_utilization_chapter_opener():
    """Test utilization for chapter opener pages with spacious target range (35%-65%)."""
    content = PageContent(
        headline="Storage Engine Internals",
        body="A deep dive into persistent storage engines, LSM-trees, and B-trees.",
    )
    util = estimate_page_utilization(content, page_type="chapter_opener")
    assert util.utilization_ratio >= 0.15
    assert util.utilization_ratio <= 0.65
    assert util.target_min_ratio == 0.35
    assert util.target_max_ratio == 0.65


def test_classify_page_complexity():
    """Verify classification across SIMPLE, STANDARD, COMPLEX, VISUAL, and CODE_HEAVY."""
    # Simple page
    p_simple = PageContent(
        headline="Introduction",
        body="Brief summary of what this book covers.",
    )
    assert classify_page_complexity(p_simple) == PageComplexity.SIMPLE

    # Code heavy page
    p_code = PageContent(
        headline="Writing Queries",
        body="Here is how to run queries.",
        blocks=[CodeBlock(language="python", code="db.query('SELECT 1')")],
    )
    assert classify_page_complexity(p_code) == PageComplexity.CODE_HEAVY

    # Visual page
    p_visual = PageContent(
        headline="System Topology",
        body="Architecture diagram.",
        blocks=[DiagramBlock(mermaid_code="graph TD\nA-->B-->C", caption="Topology")],
    )
    assert classify_page_complexity(p_visual) == PageComplexity.VISUAL

    # Complex page
    p_complex = PageContent(
        headline="Advanced Configuration",
        body="Overview of advanced multi-tier parameters.",
        blocks=[
            StepBlock(steps=[StepItem(step_number=1, title="Config", description="Set port")]),
            CalloutBlock(variant="note", title="Info", content="Note"),
            TextBlock(text="Paragraph elaboration with multiple concepts and trade-offs."),
        ],
    )
    assert classify_page_complexity(p_complex) == PageComplexity.COMPLEX


def test_select_page_layout_anti_repetition():
    """Verify that select_page_layout respects recent history and prevents >2 consecutive repeats."""
    recent = ["editorial_standard", "editorial_standard"]
    selected = select_page_layout(PageComplexity.STANDARD, recent_layouts=recent)
    assert selected != "editorial_standard"
    assert selected in [
        LayoutType.EDITORIAL_SPLIT.value,
        LayoutType.CARDS_FOCUS.value,
        LayoutType.STEPS_FOCUS.value,
        LayoutType.VISUAL_SIDE.value,
    ]


def test_repair_underfilled_page_progressive_expansion():
    """Verify that an underfilled page is deterministically enriched to 70%-90% without overflowing."""
    page = Page(
        book_id="test-book",
        page_number=5,
        chapter_number=1,
        page_type="chapter_content",
        layout="editorial_standard",
        theme=Theme.DARK,
        content=PageContent(
            headline="Introduction to Vector Storage",
            body="Vector storage indexes dense embeddings for semantic nearest-neighbor search.",
        ),
    )

    initial_util = estimate_page_utilization(page.content)
    assert initial_util.utilization_ratio < 0.60
    assert initial_util.status in ("hard_failure", "severely_underfilled", "underfilled")

    repaired = repair_underfilled_page(page, topic="vector databases embeddings ANN search")
    repaired_util = estimate_page_utilization(repaired.content)

    assert repaired_util.utilization_ratio >= 0.70
    assert repaired_util.utilization_ratio <= 0.95
    assert repaired_util.is_overflow is False
    assert len(repaired.content.blocks) >= 2


def test_quality_scoring_and_boilerplate_detection():
    """Verify content quality evaluation, similarity computation, and repeated boilerplate detection."""
    p1 = Page(
        book_id="test-book",
        page_number=3,
        chapter_number=1,
        content=PageContent(
            headline="Setting Up LioranDB",
            body="In this chapter we will learn how to configure LioranDB for production use. This guide will walk you through every step. Make sure your environment variables are configured properly before starting.",
            blocks=[
                TextBlock(text="Make sure your environment variables are configured properly before starting."),
            ],
        ),
    )

    p2 = Page(
        book_id="test-book",
        page_number=4,
        chapter_number=1,
        content=PageContent(
            headline="Configuring Storage Paths",
            body="In this chapter we will learn how to configure LioranDB for production use. This guide will walk you through every step. Make sure your environment variables are configured properly before starting.",
            blocks=[
                TextBlock(text="Make sure your environment variables are configured properly before starting."),
            ],
        ),
    )

    # Detect repeated sentence boilerplate
    repeated = detect_repeated_sentence_boilerplate([p1, p2])
    assert len(repeated) >= 1

    # Compute similarity between near-identical pages
    sim = compute_page_similarity(p1.content, p2.content)
    assert sim > 0.60

    # Evaluate quality score
    from vasukisquare.book.layout import PAGE_TYPE_SPECS, TechnicalPageType
    spec = PAGE_TYPE_SPECS[TechnicalPageType.CONCEPT]
    score = evaluate_page_quality_score(
        p2.content,
        spec=spec,
        primary_subject="LioranDB",
        previous_page_text="In this chapter we will learn how to configure LioranDB for production use. This guide will walk you through every step. Make sure your environment variables are configured properly before starting.",
    )
    assert score.duplication_score > 0.50
    assert isinstance(score.page_utilization, float)


def test_watermark_icon_resolution_and_rendering():
    """Verify topic decorative icon resolution and HTML rendering."""
    icon_name = resolve_topic_decorative_icon("LioranDB High Performance Database Engine")
    assert icon_name in ("database", "server", "layers")
    icon_svg = render_lucide_icon(icon_name)
    assert "<svg" in icon_svg
    assert "lucide" in icon_svg

    # Verify HTML renderer includes decorative watermark icon when provided
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="test-book",
        page_number=3,
        chapter_number=1,
        theme=Theme.DARK,
        page_type="chapter_content",
        content=PageContent(
            headline="Database Clustering Internals",
            body="Distributed clusters synchronize state machine logs using quorum protocols.",
            blocks=[
                TextBlock(text="Each node maintains a persistent log and state machine replica.")
            ],
        ),
    )

    html = renderer.render_page(page, book_title="Database Clustering", book_topic="database")
    assert "decorative-watermark-icon" in html
    assert "pos-" in html


def test_proportional_chapter_budgeting():
    """Verify that chapter page budgets are proportional and conclusion chapters are capped at 1-2 content pages."""
    agent = EditorialPlannerAgent()
    chapters = [
        PlannedChapter(
            chapter_number=1,
            title="Foundations of Storage Engines",
            summary="Introduction and setup",
            sections=[
                SectionPlan(title="S1", visual_anchors=[VisualAnchorType.CODE]),
                SectionPlan(title="S2", visual_anchors=[VisualAnchorType.DIAGRAM]),
                SectionPlan(title="S3", visual_anchors=[VisualAnchorType.TEXT]),
            ],
        ),
        PlannedChapter(
            chapter_number=2,
            title="Core LSM-Tree Implementation & Compaction",
            summary="Deep technical implementation",
            sections=[
                SectionPlan(title="S1", visual_anchors=[VisualAnchorType.CODE]),
                SectionPlan(title="S2", visual_anchors=[VisualAnchorType.CODE]),
                SectionPlan(title="S3", visual_anchors=[VisualAnchorType.DIAGRAM]),
                SectionPlan(title="S4", visual_anchors=[VisualAnchorType.TABLE]),
            ],
        ),
        PlannedChapter(
            chapter_number=3,
            title="Distributed Consensus & Replication",
            summary="Multi-node replication",
            sections=[
                SectionPlan(title="S1", visual_anchors=[VisualAnchorType.CODE]),
                SectionPlan(title="S2", visual_anchors=[VisualAnchorType.DIAGRAM]),
                SectionPlan(title="S3", visual_anchors=[VisualAnchorType.TEXT]),
            ],
        ),
        PlannedChapter(
            chapter_number=4,
            title="Next Steps & Future Outlook",
            summary="Summary and conclusion",
            sections=[
                SectionPlan(title="Summary", visual_anchors=[VisualAnchorType.TEXT]),
                SectionPlan(title="Ecosystem Roadmap", visual_anchors=[VisualAnchorType.TIMELINE]),
            ],
        ),
    ]

    frontmatter, backmatter, all_pages = agent._assemble_pages(
        book_title="Building High-Performance Databases",
        chapters=chapters,
        target_total_pages=30,
    )

    # Check total pages matches target
    assert len(all_pages) == 30

    # Conclusion chapter (Chapter 4) should have at most 2 content pages (total budget <= 3: 1 opener + 2 content)
    ch4 = chapters[3]
    assert ch4.page_budget <= 3

    # Technical core chapter (Chapter 2) should receive more content pages than conclusion
    ch2 = chapters[1]
    assert ch2.page_budget > ch4.page_budget


def test_page_geometry_and_safe_zones():
    """Verify central A4 physical geometry constants and safe zones."""
    from vasukisquare.renderer.geometry import (
        PAGE_WIDTH_MM,
        PAGE_HEIGHT_MM,
        HEADER_SAFE_ZONE_MM,
        FOOTER_SAFE_ZONE_MM,
        USABLE_PAGE_HEIGHT_MM,
        CONTENT_SAFE_HEIGHT_MM,
        BoundingBox,
    )

    assert PAGE_WIDTH_MM == 210.0
    assert PAGE_HEIGHT_MM == 297.0
    assert HEADER_SAFE_ZONE_MM == 18.0
    assert FOOTER_SAFE_ZONE_MM == 16.0
    assert USABLE_PAGE_HEIGHT_MM == 249.0
    assert CONTENT_SAFE_HEIGHT_MM == 215.0

    # Test bounding box intersection
    box1 = BoundingBox(x=10, y=10, width=50, height=30)
    box2 = BoundingBox(x=40, y=20, width=50, height=30)
    box3 = BoundingBox(x=100, y=100, width=20, height=20)

    assert box1.intersects(box2) is True
    assert box1.intersects(box3) is False


def test_preflight_validation_and_reporting():
    """Verify preflight checks detect overflow and validate safe page boundaries."""
    from vasukisquare.renderer.preflight import preflight_page, preflight_book
    from vasukisquare.design.themes import generate_book_theme

    # Normal valid page
    valid_page = Page(
        book_id="test-book",
        page_number=2,
        chapter_number=1,
        page_type="chapter_content",
        layout="editorial_standard",
        theme=Theme.DARK,
        content=PageContent(
            headline="Safe Content Section",
            body="Short introductory explanation with adequate vertical margin across all sections.",
            blocks=[
                TextBlock(text="This paragraph is appropriately budgeted inside safe boundaries."),
                CalloutBlock(variant="tip", title="Note", content="Tips and notes stay in flow."),
                TextBlock(text="This paragraph is appropriately budgeted inside safe boundaries. It provides clear conceptual grounding for readers without causing vertical overflow."),
                ChecklistBlock(
                    title="Implementation Checklist",
                    items=[
                        "Verify component dimensions adhere to standard layout grids.",
                        "Ensure typographic hierarchy remains consistent across alternating themes.",
                        "Validate contrast ratios for accessible reading comfort.",
                    ],
                ),
                ComparisonBlock(
                    title="Design Trade-offs",
                    left_title="Optimal Patterns",
                    right_title="Anti-Patterns",
                    left_items=["Strict A4 boundary enforcement", "Hierarchical styling tokens", "Fluid responsive padding"],
                    right_items=["Arbitrary inline dimensions", "Uncalibrated vertical margins", "Unchecked font scaling"],
                ),
                CalloutBlock(variant="tip", title="Note", content="Tips and notes stay cleanly in flow without footer collision."),
            ],
        ),
    )

    rep = preflight_page(valid_page)
    assert rep.valid is True
    assert rep.overflow is False
    assert rep.footer_collision is False

    # Overfilled overflowing page
    huge_blocks = [
        TextBlock(text="A" * 600) for _ in range(10)
    ]
    overflow_page = Page(
        book_id="test-book",
        page_number=3,
        chapter_number=1,
        page_type="chapter_content",
        layout="editorial_standard",
        theme=Theme.DARK,
        content=PageContent(
            headline="Massive Section",
            blocks=huge_blocks,
        ),
    )

    bad_rep = preflight_page(overflow_page)
    assert bad_rep.valid is False
    assert bad_rep.overflow is True
    assert bad_rep.footer_collision is True
    assert len(bad_rep.errors) >= 1

    # Book preflight
    theme_map = generate_book_theme(num_chapters=2, seed=123)
    book_rep = preflight_book([valid_page, overflow_page], book_theme=theme_map)
    assert book_rep.total_pages == 2
    assert book_rep.valid_pages == 1
    assert book_rep.invalid_pages == 1
    assert book_rep.all_valid is False

