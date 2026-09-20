"""Unit and integration tests for Dynamic Page Insertion and Semantic Overflow Pagination."""

from vasukisquare.book.components import (
    CalloutBlock,
    ChecklistBlock,
    ChecklistItem,
    CodeBlock,
    ComparisonBlock,
    StepBlock,
    StepItem,
    TableBlock,
    TextBlock,
    TocBlock,
    TocEntry,
)
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import (
    Page,
    PageContent,
)
from vasukisquare.design.theme import Theme
from vasukisquare.renderer.overflow import (
    DynamicPaginator,
    OverflowDetector,
    USABLE_PAGE_HEIGHT_MM,
    estimate_page_utilization,
    regenerate_toc_pages,
    split_checklist_block,
    split_step_block,
    split_table_block,
)
from vasukisquare.renderer.preflight import preflight_book, preflight_page
from vasukisquare.renderer.html import HtmlPageRenderer


def test_overloaded_habit_challenge_splits_into_continuation_page():
    """Verify that an overloaded page with multiple heavy components splits cleanly into 2 physical pages."""
    book_id = "book-habits-challenge"

    # Overloaded blocks exceeding safe A4 usable height
    overloaded_blocks = [
        TextBlock(
            text="The 7-Day Habit Challenge is structured to bridge the intention-behavior gap through micro-commitments, visual feedback loops, and daily friction elimination. Small daily actions create systemic momentum over time across complex personal workflows.",
            paragraphs=[
                "The 7-Day Habit Challenge is structured to bridge the intention-behavior gap through micro-commitments, visual feedback loops, and daily friction elimination. Small daily actions create systemic momentum over time across complex personal workflows.",
                "Behavioral architecture relies on environmental priming: preparing tools the night before, placing cues along natural transit paths, and eliminating cognitive friction before action.",
            ],
        ),
        CalloutBlock(
            variant="important",
            title="Daily Action Contract",
            icon="shield-check",
            content="Commit to performing your chosen target habit at the exact same anchor time each day. Never break the chain twice in a row, regardless of schedule disruptions or travel friction.",
        ),
        ComparisonBlock(
            title="High-Leverage Execution Strategy",
            left_title="Proven Success Patterns",
            left_items=[
                "Environment priming before sleep",
                "Explicit 2-minute entry rule",
                "Visual habit tracker placed at eye level",
                "Immediate positive feedback loops",
            ],
            right_title="Common Friction Points",
            right_items=[
                "Relying solely on willpower during fatigue",
                "Overly ambitious initial scope",
                "Ambiguous execution timing without anchor triggers",
                "Delayed reward structures",
            ],
        ),
        ChecklistBlock(
            title="Daily Implementation Checklist",
            items=[
                ChecklistItem(text="Day 1: Audit friction points and prep work surfaces.", checked=True),
                ChecklistItem(text="Day 2: Implement 2-minute entry ritual before session.", checked=True),
                ChecklistItem(text="Day 3: Pair habit with existing daily coffee routine.", checked=True),
                ChecklistItem(text="Day 4: Review friction log and eliminate one barrier.", checked=True),
                ChecklistItem(text="Day 5: Complete mid-week milestone assessment.", checked=True),
                ChecklistItem(text="Day 6: Prepare emergency contingency protocol.", checked=True),
                ChecklistItem(text="Day 7: Consolidate weekly progress and set next cycle.", checked=True),
            ],
        ),
        CalloutBlock(
            variant="insight",
            title="Psychological Milestone",
            icon="sparkles",
            content="By day 4, neural automaticity begins reducing cognitive resistance, shifting the action from conscious effort to default behavior across daily execution loops.",
        ),
        CalloutBlock(
            variant="tip",
            title="Sustained Momentum Protocol",
            icon="zap",
            content="Maintain visual cue anchors in high-traffic zones to sustain baseline momentum throughout the critical second week.",
        ),
    ]

    overloaded_page = Page(
        id="page-habit-challenge",
        book_id=book_id,
        page_number=13,
        chapter_number=2,
        chapter_name="Building Consistency",
        page_type="chapter_content",
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Your 7-Day Habit Challenge",
            blocks=overloaded_blocks,
        ),
    )

    # Initial page should exceed safe layout bounds or trigger overflow detector
    detector = OverflowDetector()
    initial_util = estimate_page_utilization(overloaded_page)
    assert initial_util.total_content_height_mm > USABLE_PAGE_HEIGHT_MM or detector.is_overflowing(overloaded_page)

    # Run dynamic pagination
    paginator = DynamicPaginator(detector=detector)
    result_pages = paginator.repair_pages([overloaded_page])

    # Must produce exactly 2 physical pages
    assert len(result_pages) == 2
    p1 = result_pages[0]
    p2 = result_pages[1]

    # Verify physical page numbering and linked list pointers
    assert p1.page_number == 1
    assert p2.page_number == 2
    assert p1.next_page_id == p2.id
    assert p2.previous_page_id == p1.id

    # Verify continuation headline
    assert p1.content.headline == "Your 7-Day Habit Challenge"
    assert p2.content.headline == "Your 7-Day Habit Challenge (Cont.)"

    # Verify metadata inheritance
    assert p2.chapter_number == 2
    assert p2.chapter_name == "Building Consistency"
    assert p2.theme == Theme.LIGHT

    # Verify no content was deleted
    total_blocks_initial = len(overloaded_blocks)
    total_blocks_paginated = len(p1.content.blocks) + len(p2.content.blocks)
    assert total_blocks_paginated >= total_blocks_initial

    # Verify both pages fit comfortably within safe physical A4 height
    rep1 = preflight_page(p1)
    rep2 = preflight_page(p2)
    assert rep1.valid is True
    assert rep1.footer_collision is False
    assert rep2.valid is True
    assert rep2.footer_collision is False


def test_recursive_multi_page_splitting():
    """Verify that a massive logical page (e.g. 3x page height) recursively splits into 3 physical pages."""
    book_id = "book-recursive-test"

    # Create 11 distinct heavy blocks that exceed 2 full pages (~415mm total)
    heavy_blocks = []
    for i in range(1, 12):
        heavy_blocks.append(
            CalloutBlock(
                variant="note" if i % 2 == 0 else "tip",
                title=f"Architectural Invariant #{i}",
                icon="layers",
                content=f"Detailed invariant specification #{i}: Nodes must maintain consistent linearizable order across all state transitions and persist state before broadcast across distributed consensus channels.",
            )
        )

    massive_page = Page(
        id="page-massive",
        book_id=book_id,
        page_number=6,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        page_type="chapter_content",
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.DARK,
        content=PageContent(
            headline="Comprehensive Cluster Invariants",
            blocks=heavy_blocks,
        ),
    )

    paginator = DynamicPaginator()
    result_pages = paginator.repair_pages([massive_page])

    # Should recursively split into 3 physical pages
    assert len(result_pages) == 3
    assert result_pages[0].page_number == 1
    assert result_pages[1].page_number == 2
    assert result_pages[2].page_number == 3

    assert result_pages[0].content.headline == "Comprehensive Cluster Invariants"
    assert result_pages[1].content.headline == "Comprehensive Cluster Invariants (Cont.)"
    assert result_pages[2].content.headline == "Comprehensive Cluster Invariants (Cont. 2)"

    # Sequential pointers
    assert result_pages[0].next_page_id == result_pages[1].id
    assert result_pages[1].previous_page_id == result_pages[0].id
    assert result_pages[1].next_page_id == result_pages[2].id
    assert result_pages[2].previous_page_id == result_pages[1].id
    assert result_pages[2].next_page_id is None

    # Verify all 3 physical pages pass preflight
    for p in result_pages:
        rep = preflight_page(p)
        assert rep.valid is True
        assert rep.footer_collision is False


def test_large_table_component_sub_splitting():
    """Verify that a large TableBlock with many rows splits across pages with repeated headers."""
    headers = ["Metric", "SQLite", "PostgreSQL", "RocksDB", "LioranDB"]
    rows = [
        [f"Benchmark Test #{i}", f"{i*10} ops", f"{i*50} ops", f"{i*120} ops", f"{i*200} ops"]
        for i in range(1, 13)
    ]
    table = TableBlock(
        caption="Comprehensive Database Benchmarks",
        columns=headers,
        rows=rows,
        source_note="Source: Internal Architectural Benchmark Suite 2026",
    )

    t1, t2 = split_table_block(table, max_rows=6)

    assert len(t1.rows) == 6
    assert len(t2.rows) == 6
    assert t1.columns == headers
    assert t2.columns == headers
    assert t1.caption == "Comprehensive Database Benchmarks"
    assert t2.caption == "Comprehensive Database Benchmarks (Cont.)"
    assert t2.source_note == "Source: Internal Architectural Benchmark Suite 2026"


def test_large_checklist_and_step_sub_splitting():
    """Verify that large checklist and step components sub-split cleanly."""
    checklist = ChecklistBlock(
        title="Production Deployment Audit",
        items=[ChecklistItem(text=f"Check item {i}", checked=True) for i in range(1, 11)],
    )
    c1, c2 = split_checklist_block(checklist, max_items=5)
    assert len(c1.items) == 5
    assert len(c2.items) == 5
    assert c1.title == "Production Deployment Audit"
    assert c2.title == "Production Deployment Audit (Cont.)"

    steps = StepBlock(
        title="Zero-Downtime Migration Procedure",
        steps=[StepItem(step_number=i, title=f"Step {i}", description=f"Execute phase {i}") for i in range(1, 9)],
    )
    s1, s2 = split_step_block(steps, max_steps=4)
    assert len(s1.steps) == 4
    assert len(s2.steps) == 4
    assert s1.title == "Zero-Downtime Migration Procedure"
    assert s2.title == "Zero-Downtime Migration Procedure (Cont.)"


def test_table_of_contents_dynamic_page_shift():
    """Verify that TOC page numbers automatically shift when continuation pages are inserted in earlier chapters."""
    book_id = "book-toc-shift-test"

    # Create a 4-page sequence:
    # Page 1: Cover
    # Page 2: Table of Contents
    # Page 3: Chapter 1 Opener
    # Page 4: Chapter 1 Content (MASSIVE OVERFLOW -> will split into 2 pages)
    # Page 5: Chapter 2 Opener (originally Page 5, should shift to Page 6)
    # Page 6: Chapter 2 Content (originally Page 6, should shift to Page 7)

    p1_cover = Page(
        id="p1-cover",
        book_id=book_id,
        page_number=1,
        page_type=LayoutType.COVER.value,
        layout=LayoutType.COVER.value,
    )

    toc_entries = [
        TocEntry(chapter_number=1, title="Foundations of Storage", page_number=3, icon="layers"),
        TocEntry(chapter_number=2, title="Advanced Replication", page_number=5, icon="database"),
    ]
    p2_toc = Page(
        id="p2-toc",
        book_id=book_id,
        page_number=2,
        page_type=LayoutType.TOC.value,
        layout=LayoutType.TOC.value,
        content=PageContent(
            headline="Table of Contents",
            blocks=[
                TocBlock(
                    title="Table of Contents",
                    subtitle="Book Structural Blueprint",
                    entries=toc_entries,
                )
            ],
        ),
    )

    p3_ch1_opener = Page(
        id="p3-ch1-opener",
        book_id=book_id,
        page_number=3,
        chapter_number=1,
        chapter_name="Foundations of Storage",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="layers",
    )

    # Overloaded Chapter 1 Content
    p4_ch1_content = Page(
        id="p4-ch1-content",
        book_id=book_id,
        page_number=4,
        chapter_number=1,
        chapter_name="Foundations of Storage",
        page_type="chapter_content",
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.DARK,
        content=PageContent(
            headline="Storage Hierarchy & WAL Protocols",
            blocks=[
                TextBlock(text="Paragraph explaining memory hierarchy and disk page caching trade-offs in modern storage engines."),
                CalloutBlock(variant="tip", title="Caching Protocol", icon="zap", content="Direct I/O bypasses OS page cache."),
                ComparisonBlock(
                    title="Storage Media Comparison",
                    left_title="NVMe Storage",
                    left_items=["Microsecond latency", "High random IOPS", "Direct PCI-e bus access"],
                    right_title="Spinning Disk",
                    right_items=["Millisecond seeks", "Low random throughput", "SATA controller bottleneck"],
                ),
                ChecklistBlock(
                    title="Storage Configuration Rules",
                    items=[
                        ChecklistItem(text="Rule 1: Pre-allocate WAL files to prevent fragmentation.", checked=True),
                        ChecklistItem(text="Rule 2: Align record sizes with 4KB sector boundaries.", checked=True),
                        ChecklistItem(text="Rule 3: Use io_uring for non-blocking asynchronous batches.", checked=True),
                        ChecklistItem(text="Rule 4: Enable CRC32 checksumming on every frame.", checked=True),
                        ChecklistItem(text="Rule 5: Maintain double buffering for high-throughput write streams.", checked=True),
                        ChecklistItem(text="Rule 6: Enforce fsync barriers after epoch boundaries.", checked=True),
                    ],
                ),
                CodeBlock(
                    language="python",
                    filename="storage/wal_sync.py",
                    code="async def flush_wal_buffer(buffer: bytes, lsn: int) -> bool:\n    async with direct_io_writer() as writer:\n        return await writer.write_and_sync(buffer, offset=lsn)\n",
                    caption="Listing 2.1: Non-blocking Direct I/O WAL synchronization.",
                ),
                CalloutBlock(variant="warning", title="Data Integrity Note", icon="alert-triangle", content="Always sync write buffers before acknowledging client RPC requests."),
                CalloutBlock(variant="insight", title="Performance Trade-off", icon="sparkles", content="Batching fsync calls amortizes physical disk write latency across multiple transactions."),
            ],
        ),
    )

    p5_ch2_opener = Page(
        id="p5-ch2-opener",
        book_id=book_id,
        page_number=5,
        chapter_number=2,
        chapter_name="Advanced Replication",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.LIGHT,
        icon="database",
    )

    p6_ch2_content = Page(
        id="p6-ch2-content",
        book_id=book_id,
        page_number=6,
        chapter_number=2,
        chapter_name="Advanced Replication",
        page_type="chapter_content",
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Quorum Replication Protocols",
            blocks=[
                TextBlock(
                    text="Quorum replication protocols coordinate multi-node consensus across volatile network topologies, guaranteeing linearizable read and write safety.",
                    paragraphs=[
                        "Quorum replication protocols coordinate multi-node consensus across volatile network topologies, guaranteeing linearizable read and write safety.",
                        "Leader election transitions ensure only one node accepts mutate requests at any given epoch or term boundary.",
                    ],
                ),
                CalloutBlock(
                    variant="important",
                    title="Quorum Boundary Rule",
                    icon="shield-check",
                    content="A quorum of Q = floor(N/2) + 1 active nodes is required to accept and persist transactions before committing entries to disk.",
                ),
                ChecklistBlock(
                    title="Replication Verification Checklist",
                    items=[
                        ChecklistItem(text="Verify term match before appending log entries.", checked=True),
                        ChecklistItem(text="Reject stale heartbeat frames from demoted leaders.", checked=True),
                        ChecklistItem(text="Replicate log entries across independent availability zones.", checked=True),
                    ],
                ),
                CalloutBlock(
                    variant="tip",
                    title="Optimization Insight",
                    icon="zap",
                    content="Pipelining log entries without waiting for preceding acknowledgments maximizes network channel utilization.",
                ),
            ],
        ),
    )

    raw_pages = [p1_cover, p2_toc, p3_ch1_opener, p4_ch1_content, p5_ch2_opener, p6_ch2_content]

    # Render book with automatic repair and dynamic TOC regeneration
    renderer = HtmlPageRenderer()
    book_html = renderer.render_book(raw_pages, auto_repair=True)

    # Dynamic pagination should have split p4 into 2 physical pages, shifting total pages from 6 to 7
    paginated_pages = renderer.repair_engine.repair_pages(raw_pages)
    resolved_pages = regenerate_toc_pages(paginated_pages)

    assert len(resolved_pages) == 7

    # Verify page sequence:
    # 1: Cover
    # 2: TOC
    # 3: Ch1 Opener
    # 4: Ch1 Content Part 1
    # 5: Ch1 Content Continuation (Inserted!)
    # 6: Ch2 Opener (Shifted from 5 to 6!)
    # 7: Ch2 Content (Shifted from 6 to 7!)
    assert resolved_pages[0].page_number == 1
    assert resolved_pages[1].page_number == 2
    assert resolved_pages[2].page_number == 3
    assert resolved_pages[3].page_number == 4
    assert resolved_pages[4].page_number == 5
    assert resolved_pages[5].page_number == 6
    assert resolved_pages[6].page_number == 7

    assert resolved_pages[4].content.headline == "Storage Hierarchy & WAL Protocols (Cont.)"
    assert resolved_pages[5].page_type == LayoutType.CHAPTER_OPENER.value
    assert resolved_pages[5].chapter_number == 2

    # Verify TOC block entries in the TOC page reflect the exact shifted page number (Chapter 2 -> Page 6)
    toc_page = resolved_pages[1]
    toc_block = toc_page.content.blocks[0]
    assert isinstance(toc_block, TocBlock)
    ch1_entry = next(e for e in toc_block.entries if e.chapter_number == 1)
    ch2_entry = next(e for e in toc_block.entries if e.chapter_number == 2)

    assert ch1_entry.page_number == 3
    assert ch2_entry.page_number == 6  # Successfully shifted from 5 to 6!

    # Verify book-level preflight passes with 0 invalid pages
    preflight_rep = preflight_book(resolved_pages)
    assert preflight_rep.all_valid is True
    assert preflight_rep.invalid_pages == 0
