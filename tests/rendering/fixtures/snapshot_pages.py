"""Snapshot page fixtures for the core layouts and technical components specified in TESTS.md."""

from vasukisquare.book.layout import LayoutType
from vasukisquare.book.components import (
    CalloutBlock,
    ChartBlock,
    CodeBlock,
    DiagramBlock,
    SourceBlock,
    TableBlock,
    TerminalBlock,
    TextBlock,
)
from vasukisquare.book.models import Page, PageContent, SourceCitation
from vasukisquare.design.theme import Theme


def get_regression_fixture_pages() -> list[Page]:
    """Return an ordered sequence of 10 pages covering all mandatory regression fixtures."""
    book_id = "book-regression-fixture"

    # 1. Cover
    p1 = Page(
        id="fixture-1-cover",
        book_id=book_id,
        page_number=1,
        page_type=LayoutType.COVER.value,
        layout=LayoutType.COVER.value,
        theme=Theme.DARK,
    )

    # 2. Copyright Page
    p2 = Page(
        id="fixture-2-copyright",
        book_id=book_id,
        page_number=2,
        page_type=LayoutType.COPYRIGHT.value,
        layout=LayoutType.COPYRIGHT.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Copyright & Publishing Notice",
            body="© 2026 VasukiSquare AI. All rights reserved. First Edition.",
        ),
    )

    # 3. Table of Contents (TOC)
    p3 = Page(
        id="fixture-3-toc",
        book_id=book_id,
        page_number=3,
        page_type=LayoutType.TOC.value,
        layout=LayoutType.TOC.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Table of Contents",
            key_points=[
                "Chapter 1: Deep Distributed Protocols ....... 4",
                "Chapter 2: Modern Vector Indices ............. 12",
                "References & Bibliography ................... 20",
            ],
        ),
    )

    # 4. Dark Chapter Opener (Odd chapter: 1)
    p4 = Page(
        id="fixture-4-dark-opener",
        book_id=book_id,
        page_number=4,
        chapter_number=1,
        chapter_name="Deep Distributed Protocols",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="sparkles",
    )

    # 5. Light Chapter Opener (Even chapter: 2)
    p5 = Page(
        id="fixture-5-light-opener",
        book_id=book_id,
        page_number=5,
        chapter_number=2,
        chapter_name="Modern Vector Indices",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.LIGHT,
        icon="cpu",
    )

    # 6. Text-Heavy Page (Editorial)
    p6 = Page(
        id="fixture-6-text-heavy",
        book_id=book_id,
        page_number=6,
        chapter_number=1,
        chapter_name="Deep Distributed Protocols",
        page_type=LayoutType.EDITORIAL.value,
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.DARK,
        content=PageContent(
            headline="Consensus State Machines",
            body="Distributed consensus protocols ensure that multiple nodes in a distributed system agree on state transitions.",
            key_points=["Raft Term Elections", "Log Entry Replication", "Safety Invariants"],
        ),
    )

    # 7. Code Page (with structured CodeBlock)
    p7 = Page(
        id="fixture-7-code",
        book_id=book_id,
        page_number=7,
        chapter_number=1,
        chapter_name="Deep Distributed Protocols",
        page_type=LayoutType.CODE_FOCUS.value,
        layout=LayoutType.CODE_FOCUS.value,
        theme=Theme.DARK,
        content=PageContent(
            headline="Replication RPC Handler",
            blocks=[
                CodeBlock(
                    language="python",
                    filename="consensus/rpc.py",
                    code="async def append_entries(request: AppendEntriesRequest) -> AppendEntriesResponse:\n    if request.term < current_term:\n        return AppendEntriesResponse(success=False)\n    return AppendEntriesResponse(success=True)",
                    caption="Listing 1.1: RPC Handler for term validation.",
                )
            ],
        ),
    )

    # 8. Comparison Page (with structured TableBlock)
    p8 = Page(
        id="fixture-8-comparison",
        book_id=book_id,
        page_number=8,
        chapter_number=2,
        chapter_name="Modern Vector Indices",
        page_type=LayoutType.COMPARISON.value,
        layout=LayoutType.COMPARISON.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="HNSW vs IVF-PQ Performance Comparison",
            blocks=[
                TableBlock(
                    caption="Index Performance Summary",
                    columns=["Index Type", "Recall@10", "Search Latency", "Build Time"],
                    rows=[
                        ["HNSW (M=16)", "98.4%", "0.45 ms", "14.2 min"],
                        ["IVF-PQ (nlist=1024)", "91.2%", "1.12 ms", "3.8 min"],
                    ],
                )
            ],
        ),
    )

    # 9. References Page (with structured SourceBlock)
    p9 = Page(
        id="fixture-9-references",
        book_id=book_id,
        page_number=9,
        page_type=LayoutType.REFERENCES.value,
        layout=LayoutType.REFERENCES.value,
        theme=Theme.LIGHT,
        sources=[
            SourceCitation(
                url="https://raft.github.io/raft.pdf",
                title="In Search of an Understandable Consensus Algorithm",
                claim="Raft provides equivalent safety to Paxos.",
                page_number=1,
            )
        ],
        content=PageContent(
            headline="References & Primary Sources",
            blocks=[
                SourceBlock(
                    title="In Search of an Understandable Consensus Algorithm",
                    publisher="USENIX ATC",
                    url="https://raft.github.io/raft.pdf",
                    accessed_at="2026-09-11",
                )
            ],
        ),
    )

    # 10. Thank-You Page
    p10 = Page(
        id="fixture-10-thank-you",
        book_id=book_id,
        page_number=10,
        page_type=LayoutType.THANK_YOU.value,
        layout=LayoutType.THANK_YOU.value,
        theme=Theme.DARK,
        icon="sparkles",
        content=PageContent(
            headline="Thank You for Reading",
            body="Generated with architectural precision by VasukiSquare.",
        ),
    )

    # Establish link chain
    pages = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10]
    for i, p in enumerate(pages):
        p.previous_page_id = pages[i - 1].id if i > 0 else None
        p.next_page_id = pages[i + 1].id if i < len(pages) - 1 else None

    return pages


def get_technical_component_fixture_pages() -> dict[str, Page]:
    """Return dictionary of individual test fixture pages covering all required technical components."""
    book_id = "test-tech-components"

    # 1. Light Editorial Page
    p_light_editorial = Page(
        id="test-light-editorial",
        book_id=book_id,
        page_number=2,
        chapter_number=2,
        chapter_name="Storage Internals",
        theme=Theme.LIGHT,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(
            headline="Storage Engine Concurrency",
            blocks=[
                TextBlock(text="Multi-Version Concurrency Control (MVCC) isolates active transactions."),
                CalloutBlock(variant="note", title="Isolation Level", content="Snapshot isolation prevents dirty reads."),
            ],
        ),
    )

    # 2. Dark Editorial Page
    p_dark_editorial = Page(
        id="test-dark-editorial",
        book_id=book_id,
        page_number=3,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        theme=Theme.DARK,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(
            headline="Log Replication Protocol",
            blocks=[
                TextBlock(text="Follower nodes append entries sent by the leader after verifying term constraints."),
                CalloutBlock(variant="important", title="Quorum Requirement", content="Strict majority required."),
            ],
        ),
    )

    # 3. Dark Chapter Opener
    p_dark_opener = Page(
        id="test-dark-opener",
        book_id=book_id,
        page_number=1,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="sparkles",
    )

    # 4. Light Chapter Opener
    p_light_opener = Page(
        id="test-light-opener",
        book_id=book_id,
        page_number=10,
        chapter_number=2,
        chapter_name="Storage Internals",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.LIGHT,
        icon="database",
    )

    # 5. Python Code Block
    p_python_code = Page(
        id="test-python-code",
        book_id=book_id,
        page_number=11,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        theme=Theme.DARK,
        content=PageContent(
            headline="Python RPC Handler",
            blocks=[
                CodeBlock(
                    language="python",
                    filename="consensus/rpc.py",
                    code="class RaftNode:\n    def __init__(self, node_id: str):\n        self.term = 0\n        self.is_leader = False",
                    caption="Python RaftNode class definition.",
                )
            ],
        ),
    )

    # 6. Rust Code Block
    p_rust_code = Page(
        id="test-rust-code",
        book_id=book_id,
        page_number=12,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        theme=Theme.DARK,
        content=PageContent(
            headline="Rust Storage Driver",
            blocks=[
                CodeBlock(
                    language="rust",
                    filename="storage/wal.rs",
                    code="pub struct WalRecord {\n    pub lsn: u64,\n    pub payload: Vec<u8>,\n}",
                    caption="Rust WalRecord struct.",
                )
            ],
        ),
    )

    # 7. Terminal Block
    p_terminal = Page(
        id="test-terminal",
        book_id=book_id,
        page_number=13,
        chapter_number=2,
        chapter_name="Storage Internals",
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Command Execution",
            blocks=[
                TerminalBlock(
                    title="Console",
                    shell="bash",
                    lines=["$ ./vasuki --start", "[info] Cluster initialized", "[success] Ready on port 27018"],
                )
            ],
        ),
    )

    # 8. Table Block
    p_table = Page(
        id="test-table",
        book_id=book_id,
        page_number=14,
        chapter_number=2,
        chapter_name="Storage Internals",
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Engine Matrix",
            blocks=[
                TableBlock(
                    caption="Engine Characteristics",
                    columns=["Engine", "Read IO", "Write IO"],
                    rows=[["B-Tree", "Low", "High"], ["LSM-Tree", "Medium", "Low"]],
                )
            ],
        ),
    )

    # 9. Source Links
    p_source = Page(
        id="test-source",
        book_id=book_id,
        page_number=15,
        chapter_number=2,
        chapter_name="Storage Internals",
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Primary Citations",
            blocks=[
                SourceBlock(
                    title="PostgreSQL WAL Architecture",
                    publisher="PostgreSQL Global",
                    url="https://postgresql.org/docs/wal",
                    accessed_at="2026-09-11",
                    mode="card",
                )
            ],
        ),
    )

    # 10. Callout
    p_callout = Page(
        id="test-callout",
        book_id=book_id,
        page_number=16,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        theme=Theme.DARK,
        content=PageContent(
            headline="Important Principle",
            blocks=[
                CalloutBlock(
                    variant="important",
                    title="Safety Guarantee",
                    content="Never acknowledge a write before quorum persistence.",
                )
            ],
        ),
    )

    # 11. Bar Chart
    p_barchart = Page(
        id="test-barchart",
        book_id=book_id,
        page_number=17,
        chapter_number=2,
        chapter_name="Storage Internals",
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Throughput Analysis",
            blocks=[
                ChartBlock(
                    chart_type="bar",
                    title="Batch Size vs Ops/Sec",
                    labels=["1", "10", "100"],
                    series=[{"name": "Ops", "values": [1000, 8000, 45000]}],
                )
            ],
        ),
    )

    # 12. Line Chart
    p_linechart = Page(
        id="test-linechart",
        book_id=book_id,
        page_number=18,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        theme=Theme.DARK,
        content=PageContent(
            headline="Latency Degradation",
            blocks=[
                ChartBlock(
                    chart_type="line",
                    title="p99 Latency under Load",
                    labels=["1k", "5k", "10k"],
                    series=[{"name": "ms", "values": [2, 5, 14]}],
                )
            ],
        ),
    )

    # 13. Mermaid Diagram
    p_diagram = Page(
        id="test-diagram",
        book_id=book_id,
        page_number=19,
        chapter_number=1,
        chapter_name="Distributed Consensus",
        theme=Theme.DARK,
        content=PageContent(
            headline="Architecture Pipeline",
            blocks=[
                DiagramBlock(
                    code="graph TD\n  Client --> WAL\n  WAL --> MemTable",
                    caption="Write Path Architecture",
                )
            ],
        ),
    )

    # 14. Multi-Component Technical Page
    p_multi = Page(
        id="test-multi-component",
        book_id=book_id,
        page_number=20,
        chapter_number=2,
        chapter_name="Storage Internals",
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Comprehensive Storage Page",
            blocks=[
                TextBlock(text="LSM Storage combines append-only WAL logs with leveled SSTables."),
                CodeBlock(language="rust", filename="lsm.rs", code="struct LSMTree { memtable: MemTable }"),
                CalloutBlock(variant="tip", title="Performance Tip", content="Tune bloom filter bit depth."),
                SourceBlock(title="LSM Paper", publisher="ACM", url="https://acm.org/lsm.pdf", mode="card"),
            ],
        ),
    )

    return {
        "light_editorial": p_light_editorial,
        "dark_editorial": p_dark_editorial,
        "dark_chapter_opener": p_dark_opener,
        "light_chapter_opener": p_light_opener,
        "python_code": p_python_code,
        "rust_code": p_rust_code,
        "terminal": p_terminal,
        "table": p_table,
        "source": p_source,
        "callout": p_callout,
        "bar_chart": p_barchart,
        "line_chart": p_linechart,
        "diagram": p_diagram,
        "multi_component": p_multi,
    }
