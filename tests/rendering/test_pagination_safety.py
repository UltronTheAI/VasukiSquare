"""Comprehensive pagination and safe-area layout regression tests covering pathological stress cases A through O."""

import pytest
from vasukisquare.book.components import (
    CalloutBlock,
    ChecklistBlock,
    ChecklistItem,
    CodeBlock,
    ComparisonBlock,
    HeadingBlock,
    ImageBlock,
    StepBlock,
    StepItem,
    TableBlock,
    TerminalBlock,
    TerminalLine,
    TextBlock,
    TocBlock,
    TocEntry,
)
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import (
    Page,
    PageContent,
    PageStyle,
)
from vasukisquare.design.theme import Theme
from vasukisquare.renderer.geometry import (
    PAGE_HEIGHT_MM,
    PAGE_WIDTH_MM,
    CONTENT_BOTTOM_MM,
    CONTENT_TOP_MM,
    AVAILABLE_CONTENT_HEIGHT_MM,
    BOTTOM_SAFETY_GAP_MM,
    SAFE_BOTTOM_EPSILON_MM,
)
from vasukisquare.renderer.overflow import (
    DensityEstimator,
    DynamicPaginator,
    OverflowDetector,
    PagePaginator,
    PageRepairEngine,
    estimate_page_utilization,
    find_safe_page_split,
)
from vasukisquare.renderer.preflight import preflight_book, preflight_page
from vasukisquare.renderer.html import HtmlPageRenderer


def _create_base_page(page_num: int = 4, chapter_num: int = 1, theme: Theme = Theme.LIGHT, blocks=None, headline="Test Section") -> Page:
    return Page(
        book_id="book-test-safety",
        page_number=page_num,
        chapter_number=chapter_num,
        chapter_name=f"Chapter {chapter_num}",
        page_type="chapter_content",
        layout=LayoutType.EDITORIAL.value,
        theme=theme,
        content=PageContent(
            headline=headline,
            blocks=blocks or [],
        ),
    )


# Case A: Many normal paragraphs that nearly fill a page
def test_case_a_many_normal_paragraphs_nearly_fill_page():
    paras = [
        "In modern distributed systems, consensus engines coordinate state replication across volatile networks. Each node maintains an append-only write-ahead log to record transactions sequentially before broadcasting state transitions across peers. This deterministic ordering guarantees that non-byzantine replica nodes transition through identical intermediate states.",
        "Leader election protocol transitions ensure exactly one active primary receives client write requests per term. Periodic heartbeat intervals prevent split-brain scenarios and maintain cluster lease consistency across geographical availability zones.",
        "Linearizability guarantees that once a write completes, all subsequent reads observe either that value or a later committed state. This invariant is enforced using commit index thresholds and quorum acknowledgements from a strict majority of cluster nodes.",
        "Disk synchronization via fsync barriers guarantees crash-recovery durability without corrupting state machine indices. Modern storage hardware utilizes non-volatile dual-ported memory to minimize commit overhead while preserving deterministic recovery points.",
        "Batching optimizations group consecutive client operations into consolidated pipelined log frames. This maximizes disk throughput by converting fragmented random write requests into continuous sequential storage streams.",
    ]
    page = _create_base_page(headline="Distributed Log Replication", blocks=[TextBlock(paragraphs=paras)])
    util = estimate_page_utilization(page)
    assert 0.70 <= util.estimated_ratio <= 0.98
    assert not util.is_overflow

    rep = preflight_page(page)
    assert rep.valid is True
    assert rep.footer_collision is False


# Case B: Callout/card when only ~25% of required space remains
def test_case_b_callout_when_25_percent_space_remains():
    # Preceding paragraphs take up ~180mm of available height
    paras = [
        f"Paragraph #{i}: In modern distributed storage engines, log-structured merge trees balance write amplification against read latency using LSM-tree structures. Memtables buffer incoming mutations in RAM before flushing SSTables to persistent NVMe blocks."
        for i in range(1, 7)
    ]
    # Card requiring ~45mm (only ~15mm remains -> total ~220mm > 207mm)
    card = CalloutBlock(
        variant="important",
        title="Practical Scenario & Daily Application",
        icon="shield-check",
        content="When designing high-throughput ingestion pipelines, calibrate memtable write buffer sizes to prevent write stalls during heavy burst workloads. Monitor compaction backlog gauges closely to avoid read tail amplification.",
    )
    overloaded_page = _create_base_page(blocks=[TextBlock(paragraphs=paras), card])
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([overloaded_page])
    
    # Must move the atomic card to next page cleanly instead of clipping it at bottom
    assert len(repaired) == 2
    assert len(repaired[0].content.blocks) == 1  # Text block
    assert len(repaired[1].content.blocks) == 1  # Callout card intact on next page
    assert repaired[1].content.blocks[0].title == "Practical Scenario & Daily Application"
    
    for p in repaired:
        rep = preflight_page(p)
        assert rep.valid is True
        assert rep.footer_collision is False


# Case C: Callout/card when only ~5% of required space remains
def test_case_c_callout_when_5_percent_space_remains():
    # Page is ~94% full (~195mm used)
    paras = [
        f"Paragraph #{i}: Distributed consensus protocols guarantee state consistency across network partition failures. Each node maintains a write-ahead log to record transactions sequentially before broadcasting state transitions across cluster peers."
        for i in range(1, 7)
    ]
    # Card placed when almost zero space remains
    card = CalloutBlock(
        variant="tip",
        title="Quorum Configuration Tip",
        icon="zap",
        content="Deploy an odd number of voting replicas (3 or 5) across distinct availability zones to maximize fault tolerance while minimizing quorum round-trip latency.",
    )
    overloaded_page = _create_base_page(blocks=[TextBlock(paragraphs=paras), card])
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([overloaded_page])
    
    assert len(repaired) == 2
    assert repaired[0].content.blocks[0].type == "text"
    assert repaired[1].content.blocks[0].title == "Quorum Configuration Tip"
    
    for p in repaired:
        rep = preflight_page(p)
        assert rep.valid is True


# Case D: Very long terminal code
def test_case_d_very_long_terminal_code():
    # Terminal session with 35 lines (exceeds single page budget)
    lines = [
        TerminalLine(kind="command", text=f"vasuki node start --id=node-{i} --cluster=prod-alpha --port={8000+i}", prompt="$")
        if i % 3 == 0 else
        TerminalLine(kind="stdout", text=f"[INFO] Node-{i} initialized, listening on 0.0.0.0:{8000+i}, peer count: {i}")
        for i in range(1, 36)
    ]
    term = TerminalBlock(title="Cluster Provisioning Log", lines=lines, shell="bash")
    page = _create_base_page(blocks=[term])
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([page])
    
    # Must split cleanly across page boundaries without clipping or character-truncation
    assert len(repaired) >= 2
    total_repaired_lines = sum(len(p.content.blocks[0].lines) for p in repaired)
    assert total_repaired_lines == 35
    assert "(Cont.)" in repaired[1].content.blocks[0].title
    
    for p in repaired:
        rep = preflight_page(p)
        assert rep.valid is True
        assert rep.footer_collision is False


# Case E: One extremely long shell command with long paths
def test_case_e_extremely_long_shell_command():
    long_cmd = (
        "kubectl exec -it vasuki-distributed-storage-controller-0 -n production-infrastructure-us-east-1 "
        "-- /usr/local/bin/vasuki-cli admin cluster verify-quorum --config-file=/etc/vasuki/storage/v2/production-cluster-topology.yaml "
        "--output-format=json-stream --strict-linearizability --timeout=45s --audit-log-path=/var/log/vasuki/audit/quorum-verification-2026.log"
    )
    lines = [
        TerminalLine(kind="command", text=long_cmd, prompt="PS> "),
        TerminalLine(kind="success", text="[SUCCESS] All 5 replicas confirmed linearizable state machine matching commit index LSN: 482910481."),
        TerminalLine(kind="stdout", text="[INFO] Quorum latency: 2.14ms. Zero dropped packet frames detected during sync window."),
    ]
    term = TerminalBlock(title="Quorum Verification", lines=lines, shell="powershell")
    page = _create_base_page(blocks=[
        TextBlock(paragraphs=[
            "Administrative auditing tools verify linearizable state consistency across all running storage engine pods.",
            "The following command triggers end-to-end verification and streams cryptographic checksum logs to disk.",
        ]),
        term,
    ])
    
    # Height estimator must account for long command line wrapping (~4 wrapped lines)
    h = DensityEstimator.estimate_block_height_mm(term)
    assert h > 45.0  # Accounts for 4+ wrapped lines + overhead
    
    rep = preflight_page(page)
    assert rep.valid is True
    assert rep.footer_collision is False


# Case F: Large comparison table
def test_case_f_large_comparison_table():
    headers = ["Feature Metric", "B-Tree Storage Engine", "LSM-Tree Storage Engine", "Vector HNSW Index"]
    rows = [
        [f"Benchmark Category #{i}", f"O(log N) random seek ({i*10}ms)", f"O(1) append + compaction ({i*2}ms)", f"Approximate O(log N) ({i*5}ms)"]
        for i in range(1, 18)
    ]
    table = TableBlock(
        caption="Comparative Engine Characteristics",
        columns=headers,
        rows=rows,
        source_note="Source: Database Engine Internals (2026)",
    )
    page = _create_base_page(blocks=[table])
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([page])
    
    assert len(repaired) >= 2
    # Table headers must be preserved on second chunk with (Cont.) caption
    t1 = repaired[0].content.blocks[0]
    t2 = repaired[1].content.blocks[0]
    assert len(t1.rows) + len(t2.rows) == 17
    assert t1.columns == headers
    assert t2.columns == headers
    assert "(Cont.)" in t2.caption
    
    for p in repaired:
        rep = preflight_page(p)
        assert rep.valid is True


# Case G: Large checklist
def test_case_g_large_checklist():
    items = [
        ChecklistItem(text=f"Production Rule {i}: Validate boundary invariants and memory safety for cluster node {i}.", checked=True)
        for i in range(1, 25)
    ]
    checklist = ChecklistBlock(title="Production Readiness Verification", items=items)
    page = _create_base_page(blocks=[checklist])
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([page])
    
    assert len(repaired) >= 2
    c1 = repaired[0].content.blocks[0]
    c2 = repaired[1].content.blocks[0]
    assert len(c1.items) + len(c2.items) == 24
    assert "(Cont.)" in c2.title
    
    for p in repaired:
        rep = preflight_page(p)
        assert rep.valid is True


# Case H: Image + caption near page bottom
def test_case_h_image_caption_near_page_bottom():
    paras = [
        "Network topologies in modern cloud data centers utilize spine-leaf architectures to guarantee bisection bandwidth.",
        "Equal-cost multi-path (ECMP) routing hashes traffic across parallel uplinks to prevent link saturation.",
        "Hardware packet switches forward ethernet frames at wire speed using cut-through switching ASICs.",
    ]
    img = ImageBlock(
        src="https://images.unsplash.com/photo-1558494949-ef010cbdcc31",
        alt="Data Center Spine-Leaf",
        caption="Figure 3.2: 3-stage Clos spine-leaf network topology with ECMP routing paths.",
    )
    page = _create_base_page(blocks=[TextBlock(paragraphs=paras), img])
    
    rep = preflight_page(page)
    assert rep.valid is True
    assert rep.footer_collision is False


# Case I: Heading near bottom with insufficient room for following paragraph
def test_case_i_heading_near_bottom_moves_cleanly():
    paras = [
        f"Paragraph #{i}: Storage hierarchies separate volatile caches from durable storage tiers. Direct IO eliminates duplicate kernel page cache overhead during high-concurrency read queries."
        for i in range(1, 8)
    ]
    heading = HeadingBlock(level=2, text="Advanced Lock-Free Queuing Protocols", icon="cpu", eyebrow="Concurrency Layer")
    para2 = TextBlock(paragraphs=[
        "Lock-free bounded queues utilize atomic compare-and-swap (CAS) ring buffers to pass memory pointers between thread pools without kernel mutex contention.",
        "Producer and consumer threads coordinate cache-line sequences using acquire-release memory orderings to prevent instruction reordering hazards.",
    ])
    
    page = _create_base_page(blocks=[TextBlock(paragraphs=paras), heading, para2])
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([page])
    
    # Heading + following text must move together to next page rather than orphaning the heading alone at bottom
    assert len(repaired) == 2
    h_on_p2 = any(isinstance(b, HeadingBlock) for b in repaired[1].content.blocks)
    assert h_on_p2 is True


# Case J: Several compact components whose cumulative margins trigger overflow
def test_case_j_cumulative_compact_components():
    # 10 compact callouts / cards
    blocks = [
        CalloutBlock(variant="tip", title=f"Micro Best Practice #{i}", icon="zap", content=f"Micro invariant rule #{i} for bounded buffer concurrency in high-throughput engines.")
        for i in range(1, 11)
    ]
    page = _create_base_page(blocks=blocks)
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([page])
    
    # Cumulative gaps and margins must be accounted for
    assert len(repaired) >= 2
    for p in repaired:
        rep = preflight_page(p)
        assert rep.valid is True
        assert rep.footer_collision is False


# Case K: Long generated text with unpredictable wrapping
def test_case_k_long_text_unpredictable_wrapping():
    long_para = (
        "Distributed consensus mechanisms guarantee that a cluster of independent nodes can agree on a shared sequence of state machine operations even in the presence of unreliable networks, asymmetric message delays, transient packet loss, and abrupt node crashes. "
        "By enforcing strict term monotonicity, raft leaders prevent stale commands from superseding verified quorums. Every transaction must be persisted to non-volatile storage via synchronized write-ahead logging before acknowledgment frames are transmitted across client connections. "
        "When a leader failure is detected via elapsed election timers, candidate nodes increment the term counter, cast votes for themselves, and broadcast RequestVote remote procedure calls to all peers. "
        "The node that secures a majority quorum transitions to leader status and immediately begins dispatching heartbeat frames to assert authoritative dominance over the cluster topology."
    )
    page = _create_base_page(blocks=[TextBlock(paragraphs=[long_para, long_para])])
    
    util = estimate_page_utilization(page)
    assert util.total_content_height_mm <= AVAILABLE_CONTENT_HEIGHT_MM + SAFE_BOTTOM_EPSILON_MM
    rep = preflight_page(page)
    assert rep.valid is True


# Case L: Maximum-length code block spanning multiple pages
def test_case_l_max_length_code_spanning_multiple_pages():
    code_lines = [f"    pub fn process_event_batch_{i}(&mut self, batch: &[EventRecord]) -> Result<usize, EngineError> {{" for i in range(1, 41)]
    full_code = "impl StorageEngine {\n" + "\n        // Process records\n        Ok(batch.len())\n    }\n\n".join(code_lines) + "\n}"
    
    code_block = CodeBlock(
        language="rust",
        filename="engine/batch_processor.rs",
        code=full_code,
        caption="Listing 4.1: Production Event Batch Processing Pipeline",
    )
    page = _create_base_page(blocks=[code_block])
    
    paginator = DynamicPaginator()
    repaired = paginator.repair_pages([page])
    
    assert len(repaired) >= 2
    # Preserves 100% of lines across split
    all_code = "".join(b.code for p in repaired for b in p.content.blocks if isinstance(b, CodeBlock))
    assert "process_event_batch_1" in all_code
    assert "process_event_batch_40" in all_code
    
    for p in repaired:
        rep = preflight_page(p)
        assert rep.valid is True


# Case M: Mixed page: paragraph + table + code + callout + paragraph
def test_case_m_mixed_rich_page():
    blocks = [
        TextBlock(text="Storage engines enforce atomic durability guarantees through structured write paths."),
        TableBlock(
            caption="I/O Operations Overview",
            columns=["Operation", "Latency", "Durability"],
            rows=[
                ["Memtable Append", "< 1 µs", "Volatile RAM"],
                ["WAL Flush", "50-100 µs", "Durable Disk"],
            ],
        ),
        CodeBlock(
            language="python",
            filename="storage/wal.py",
            code="def append_wal(entry: bytes) -> int:\n    return file.write(entry)\n",
        ),
        CalloutBlock(variant="warning", title="Data Integrity Note", content="Always issue fsync after transaction commits."),
        TextBlock(text="Subsequent read requests resolve against in-memory buffers before traversing SSTable block caches."),
    ]
    page = _create_base_page(blocks=blocks)
    
    rep = preflight_page(page)
    assert rep.valid is True
    assert rep.footer_collision is False


# Case N: Both light and dark themes
def test_case_n_light_and_dark_theme_safety():
    blocks = [
        HeadingBlock(level=2, text="Consistency Invariants", icon="layers"),
        TextBlock(paragraphs=[
            "Consistency guarantees that state machine updates satisfy cluster-wide integrity constraints.",
            "Linearizable ordering ensures that once a value is committed, subsequent reads never return stale records.",
            "Quorum intersection rules mathematically prevent conflicting writes from taking effect concurrently.",
        ]),
        CalloutBlock(variant="tip", title="Protocol Insight", content="Quorum size of 3 nodes tolerates 1 node failure while maintaining linearizability."),
    ]
    
    page_light = _create_base_page(page_num=4, chapter_num=2, theme=Theme.LIGHT, blocks=blocks)
    page_dark = _create_base_page(page_num=3, chapter_num=1, theme=Theme.DARK, blocks=blocks)
    
    rep_light = preflight_page(page_light)
    rep_dark = preflight_page(page_dark)
    
    assert rep_light.valid is True
    assert rep_dark.valid is True


# Case O: 40+ page synthetic document to expose cumulative rounding drift
def test_case_o_40_page_synthetic_document_rounding_drift():
    pages = []
    
    # 1. Cover
    pages.append(Page(
        book_id="b-40",
        page_number=1,
        page_type=LayoutType.COVER.value,
        layout=LayoutType.COVER.value,
    ))
    
    # 2. Table of Contents
    toc_entries = [TocEntry(chapter_number=c, title=f"Chapter {c} Architecture", page_number=3 + (c-1)*8) for c in range(1, 6)]
    pages.append(Page(
        book_id="b-40",
        page_number=2,
        page_type=LayoutType.TOC.value,
        layout=LayoutType.TOC.value,
        content=PageContent(headline="Table of Contents", blocks=[TocBlock(entries=toc_entries)]),
    ))
    
    # 3-42: 5 chapters with 8 pages each (Opener + 7 content pages with diverse blocks)
    curr_pnum = 3
    for ch in range(1, 6):
        ch_theme = Theme.DARK if (ch % 2 == 1) else Theme.LIGHT
        # Chapter opener
        pages.append(Page(
            book_id="b-40",
            page_number=curr_pnum,
            chapter_number=ch,
            chapter_name=f"Deep Architecture {ch}",
            page_type=LayoutType.CHAPTER_OPENER.value,
            layout=LayoutType.CHAPTER_OPENER.value,
            theme=ch_theme,
            icon="layers",
        ))
        curr_pnum += 1
        
        # 7 content pages per chapter
        for p in range(1, 8):
            blocks = [
                HeadingBlock(level=2, text=f"Section {ch}.{p}: System Architecture Invariants", icon="cpu"),
                TextBlock(paragraphs=[
                    f"Chapter {ch} Page {p} explains distributed consensus, storage memory hierarchy, and bounded queue algorithms.",
                    "Production reliability demands deterministic resource bounds, zero-allocation fast paths, and proactive monitoring.",
                ]),
                CalloutBlock(
                    variant="tip" if p % 2 == 0 else "important",
                    title=f"Practical Scenario {ch}.{p}",
                    content=f"Always verify disk sync barriers and monitor p99 tail latency under saturated queue conditions.",
                ),
            ]
            if p % 2 == 0:
                blocks.append(CodeBlock(
                    language="python",
                    filename=f"module_{ch}_{p}.py",
                    code=f"async def execute_task_{p}(ctx):\n    return await ctx.dispatch({p})\n",
                    caption=f"Listing {ch}.{p}: Asynchronous Dispatch Pipeline",
                ))
            else:
                blocks.append(ComparisonBlock(
                    title="Implementation Trade-offs",
                    left_title="Recommended Pattern",
                    left_items=["Linearizable commit paths", "Bounded channel buffers"],
                    right_title="Anti-Pattern",
                    right_items=["Unsynchronized writes", "Unbounded queues"],
                ))
                
            pages.append(Page(
                book_id="b-40",
                page_number=curr_pnum,
                chapter_number=ch,
                chapter_name=f"Deep Architecture {ch}",
                page_type="chapter_content",
                layout=LayoutType.EDITORIAL.value,
                theme=ch_theme,
                content=PageContent(headline=f"Chapter {ch} Invariants Part {p}", blocks=blocks),
            ))
            curr_pnum += 1
            
    # Run dynamic repair
    paginator = DynamicPaginator()
    repaired_pages = paginator.repair_pages(pages)
    
    assert len(repaired_pages) >= 42
    
    # Preflight the entire 42+ page book
    report = preflight_book(repaired_pages)
    assert report.all_valid is True
    assert report.invalid_pages == 0
    
    # Assert that NO content block in any page exceeds CONTENT_SAFE_HEIGHT_MM
    for page in repaired_pages:
        if page.page_type not in ("cover", "chapter_opener", "toc", "thank_you", "copyright"):
            util = estimate_page_utilization(page)
            assert util.total_content_height_mm <= (AVAILABLE_CONTENT_HEIGHT_MM + SAFE_BOTTOM_EPSILON_MM)
