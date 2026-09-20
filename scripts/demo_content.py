"""Predefined deterministic offline demo content fixtures for VasukiSquare.

Provides structured, high-quality technical ebook content, metadata, cover plan,
and page models exercising all supported PDF components, themes, and pagination edge cases
without calling any LLM, search engine, or network API.
"""

import sys
from pathlib import Path
from typing import List

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from vasukisquare.book.components import (
    AcknowledgementBlock,
    CalloutBlock,
    ChecklistBlock,
    ChecklistItem,
    CodeBlock,
    ComparisonBlock,
    HeadingBlock,
    SourceBlock,
    StepBlock,
    StepItem,
    TableBlock,
    TerminalBlock,
    TerminalLine,
    TextBlock,
    TocBlock,
    TocEntry,
)
from vasukisquare.book.layout import LayoutType, PublicationProfile
from vasukisquare.book.models import (
    BookIntent,
    BookPlan,
    CoverPlan,
    Page,
    PageContent,
    PageStyle,
    PlannedChapter,
    PlannedPage,
    SectionPlan,
    generate_id,
)
from vasukisquare.design.theme import Theme
from vasukisquare.design.tokens import ColorToken
from vasukisquare.research.models import ResearchCorpus, SourceDocument, SourceType


DEMO_TOPIC = "High-Performance Distributed Systems: Architecture, Consensus, and Resilient Storage"
DEMO_TITLE = "Distributed Systems Engineering"
DEMO_SUBTITLE = "Architecture, Consensus, and Resilient Storage"
DEMO_RUNNING_TITLE = "Distributed Systems Engineering"
DEMO_AUTHOR = "VasukiSquare Editorial Architecture Group"
DEMO_EDITION = "First Edition (2026)"


def get_demo_intent() -> BookIntent:
    """Return deterministic BookIntent metadata for the demo book."""
    return BookIntent(
        topic=DEMO_TOPIC,
        title=DEMO_TITLE,
        subtitle=DEMO_SUBTITLE,
        original_prompt="A comprehensive practical engineering guide to high-performance distributed systems, consensus engines, and storage internals.",
        book_type="technical_deep_dive",
        target_audience="Distributed Systems Engineers, Infrastructure Architects, and Platform Developers",
        purpose="Deliver an actionable, production-tested blueprint for distributed storage, Raft consensus, and chaos-resilient operational architectures.",
        tone="authoritative",
        technical_depth="advanced",
        approximate_length="standard",
        required_topics=[
            "LSM Trees and Memtables",
            "Write-Ahead Logging and fsync",
            "Raft Consensus and Term Monotonicity",
            "Leader Leases and Quorum Reads",
            "Network Partitioning and Chaos Engineering",
        ],
        is_technical=True,
        publication_profile=PublicationProfile.TECHNICAL,
        primary_programming_language="rust",
        domain_topic="distributed_systems",
        target_pages=12,
    )


def get_demo_cover_plan() -> CoverPlan:
    """Return deterministic CoverPlan for the demo book cover."""
    return CoverPlan(
        title=DEMO_TITLE,
        subtitle=DEMO_SUBTITLE,
        concept_name="Distributed Mesh & Storage Blueprint",
        cover_style="editorial_minimal",
        visual_subject="Network topology with distributed storage layers and consensus quorums",
        mood="precise",
        composition_style="asymmetric_left",
        background_style="solid_light",
        title_alignment="left",
        title_position="middle",
        subtitle_position="below_title",
        typography_style="modern_technical",
        accent_elements=["horizontal_rule", "subtle_badge"],
        icon_strategy="hero_top",
        hero_icon="layers",
        border_strategy="none",
        spacing_strategy="balanced_editorial",
        visual_density="moderate",
        contrast_mode="high_contrast_light",
        decorative_geometry="database_nodes",
        category_badge="TECHNICAL HANDBOOK",
        rationale="Modern technical handbook design with high-contrast editorial typography and geometric storage blueprint motifs.",
        palette_theme="deep_teal",
        accent_color=ColorToken.BRAND_GREEN.value,
        background_color=ColorToken.CANVAS.value,
        category="Distributed Systems",
        tone="authoritative",
        audience="Infrastructure Engineers and Distributed Systems Architects",
        author=DEMO_AUTHOR,
        edition=DEMO_EDITION,
        cover_seed=42,
    )


def get_demo_research_corpus() -> ResearchCorpus:
    """Return deterministic ResearchCorpus with authoritative technical citations."""
    docs = [
        SourceDocument(
            url="https://raft.github.io/raft.pdf",
            title="In Search of an Understandable Consensus Algorithm (Extended Version)",
            publisher="USENIX ATC",
            domain="raft.github.io",
            source_type=SourceType.ACADEMIC,
            extracted_text="Raft is a consensus algorithm for managing a replicated log that produces equivalent results to multi-Paxos.",
            summary="Foundational Raft consensus protocol specification covering leader election, log replication, and safety invariants.",
            reliability_score=1.0,
        ),
        SourceDocument(
            url="https://www.cs.umb.edu/~poneil/lsmtree.pdf",
            title="The Log-Structured Merge-Tree (LSM-Tree)",
            publisher="Acta Informatica",
            domain="cs.umb.edu",
            source_type=SourceType.ACADEMIC,
            extracted_text="The Log-Structured Merge-tree is a disk-based data structure designed for high-rate transaction ingestion.",
            summary="Classical paper detailing memtables, sequential append writes, and multi-tier merge compaction algorithms.",
            reliability_score=1.0,
        ),
        SourceDocument(
            url="https://research.google/pubs/spanner-googles-globally-distributed-database/",
            title="Spanner: Google's Globally-Distributed Database",
            publisher="ACM OSDI",
            domain="research.google",
            source_type=SourceType.ACADEMIC,
            extracted_text="Spanner provides externally consistent distributed transactions at global scale using TrueTime API.",
            summary="Groundbreaking architecture integrating synchronized atomic clocks, Paxos replication, and two-phase commit.",
            reliability_score=1.0,
        ),
        SourceDocument(
            url="https://www.oreilly.com/library/view/database-internals/9781492040330/",
            title="Database Internals: A Deep Dive into Distributed Data Storage",
            publisher="O'Reilly Media",
            domain="oreilly.com",
            source_type=SourceType.DOCUMENTATION,
            extracted_text="Comprehensive guide to storage engines, B-trees, WAL architectures, and consensus algorithms.",
            summary="Standard engineering reference for B-trees, LSM-trees, buffer pools, and distributed coordination.",
            reliability_score=1.0,
        ),
    ]
    return ResearchCorpus(
        topic=DEMO_TOPIC,
        documents=docs,
        queries_executed=[
            "distributed storage LSM-tree memtable write-ahead log",
            "Raft consensus term monotonicity quorum leases",
            "chaos engineering network partition fault injection",
        ],
        key_findings=[
            "Memtable buffering transforms random NVMe write cycles into sequential write-ahead log operations.",
            "Raft term monotonicity and quorum lease windows mathematically guarantee linearizable read index queries.",
            "Asymmetric network partitions must be tested proactively using automated kernel packet drop rules.",
        ],
    )


def get_demo_book_plan() -> BookPlan:
    """Return deterministic BookPlan defining the 3-chapter structure and page budget."""
    intent = get_demo_intent()
    chapters = [
        PlannedChapter(
            chapter_number=1,
            title="Storage Engine Internals & WAL Architecture",
            summary="Log-Structured Merge trees, in-memory memtable skiplists, write-ahead logging, and crash-recovery invariants.",
            icon="database",
            theme=Theme.DARK,
            page_budget=4,
            sections=[
                SectionPlan(title="Memory Hierarchy & LSM Trees", key_concepts=["Memtables", "SSTables", "Compaction"]),
                SectionPlan(title="Durability & Barrier Guarantees", key_concepts=["WAL", "fsync", "Write Amplification"]),
            ],
        ),
        PlannedChapter(
            chapter_number=2,
            title="Consensus Protocols, Raft & Quorum Leases",
            summary="Distributed state machine replication, leader election, term monotonicity, and linearizable read quorums.",
            icon="cpu",
            theme=Theme.LIGHT,
            page_budget=4,
            sections=[
                SectionPlan(title="Raft Protocol Invariants", key_concepts=["Leader Election", "Term Counters", "Quorum"]),
                SectionPlan(title="Automated Failover & Auditing", key_concepts=["Runbooks", "CLI Verification", "Quorum Health"]),
            ],
        ),
        PlannedChapter(
            chapter_number=3,
            title="Operational Runbooks, Performance & Chaos Engineering",
            summary="Production resilience drills, network partition simulations, and bounded buffer concurrency.",
            icon="activity",
            theme=Theme.DARK,
            page_budget=4,
            sections=[
                SectionPlan(title="Chaos Engineering Drills", key_concepts=["Fault Injection", "Iptables", "Partition Recovery"]),
                SectionPlan(title="Production Readiness", key_concepts=["Checklists", "Runbooks", "Metrics"]),
            ],
        ),
    ]

    all_pages = [
        PlannedPage(page_number=1, page_type=LayoutType.COVER.value, layout=LayoutType.COVER.value, brief="Cover Page"),
        PlannedPage(page_number=2, page_type=LayoutType.TOC.value, layout=LayoutType.TOC.value, brief="Table of Contents"),
        PlannedPage(page_number=3, page_type=LayoutType.CHAPTER_OPENER.value, layout=LayoutType.CHAPTER_OPENER.value, chapter_number=1, chapter_title=chapters[0].title, theme=Theme.DARK, icon="database", brief="Chapter 1 Opener"),
        PlannedPage(page_number=4, page_type="chapter_content", layout=LayoutType.EDITORIAL.value, chapter_number=1, chapter_title=chapters[0].title, theme=Theme.DARK, brief="LSM Trees & Memtables"),
        PlannedPage(page_number=5, page_type="chapter_content", layout=LayoutType.EDITORIAL.value, chapter_number=1, chapter_title=chapters[0].title, theme=Theme.DARK, brief="Durability & Storage Benchmarks"),
        PlannedPage(page_number=6, page_type=LayoutType.CHAPTER_OPENER.value, layout=LayoutType.CHAPTER_OPENER.value, chapter_number=2, chapter_title=chapters[1].title, theme=Theme.LIGHT, icon="cpu", brief="Chapter 2 Opener"),
        PlannedPage(page_number=7, page_type="chapter_content", layout=LayoutType.EDITORIAL.value, chapter_number=2, chapter_title=chapters[1].title, theme=Theme.LIGHT, brief="Raft Consensus & Invariants"),
        PlannedPage(page_number=8, page_type="chapter_content", layout=LayoutType.EDITORIAL.value, chapter_number=2, chapter_title=chapters[1].title, theme=Theme.LIGHT, brief="Failover & Quorum Auditing"),
        PlannedPage(page_number=9, page_type=LayoutType.CHAPTER_OPENER.value, layout=LayoutType.CHAPTER_OPENER.value, chapter_number=3, chapter_title=chapters[2].title, theme=Theme.DARK, icon="activity", brief="Chapter 3 Opener"),
        PlannedPage(page_number=10, page_type="chapter_content", layout=LayoutType.EDITORIAL.value, chapter_number=3, chapter_title=chapters[2].title, theme=Theme.DARK, brief="Chaos Drills & Resilience"),
        PlannedPage(page_number=11, page_type=LayoutType.REFERENCES.value, layout=LayoutType.REFERENCES.value, theme=Theme.DARK, brief="Cited Bibliography"),
        PlannedPage(page_number=12, page_type=LayoutType.ACKNOWLEDGEMENT.value, layout=LayoutType.ACKNOWLEDGEMENT.value, theme=Theme.LIGHT, brief="Acknowledgements & Imprint"),
    ]

    return BookPlan(
        title=DEMO_TITLE,
        subtitle=DEMO_SUBTITLE,
        running_title=DEMO_RUNNING_TITLE,
        description="A comprehensive practical engineering guide to high-performance distributed systems, consensus engines, and storage internals.",
        intent=intent,
        chapters=chapters,
        all_planned_pages=all_pages,
        total_pages=len(all_pages),
    )


def get_demo_raw_pages(book_id: str = "demo-distributed-systems") -> List[Page]:
    """Return complete, hardcoded, production-ready Page models covering all components and themes."""
    pages: List[Page] = []

    # -------------------------------------------------------------------------
    # Page 1: Cover Placeholder (filled by CoverRenderer in pipeline)
    # -------------------------------------------------------------------------
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=1,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.LIGHT,
            content=PageContent(headline=DEMO_TITLE),
        )
    )

    # -------------------------------------------------------------------------
    # Page 2: Table of Contents
    # -------------------------------------------------------------------------
    toc_entries = [
        TocEntry(chapter_number=1, title="Storage Engine Internals & WAL Architecture", page_number=3, icon="database"),
        TocEntry(chapter_number=2, title="Consensus Protocols, Raft & Quorum Leases", page_number=6, icon="cpu"),
        TocEntry(chapter_number=3, title="Operational Runbooks, Performance & Chaos Engineering", page_number=9, icon="activity"),
        TocEntry(chapter_number=None, title="Cited Bibliography & Authoritative References", page_number=11, icon="book-open"),
        TocEntry(chapter_number=None, title="Acknowledgements & Publishing Imprint", page_number=12, icon="sparkles"),
    ]
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=2,
            page_type=LayoutType.TOC.value,
            layout=LayoutType.TOC.value,
            theme=Theme.LIGHT,
            content=PageContent(
                headline="Table of Contents",
                blocks=[
                    TocBlock(
                        title="Table of Contents",
                        subtitle=f"Structural Blueprint for {DEMO_TITLE}",
                        entries=toc_entries,
                    )
                ],
            ),
        )
    )

    # -------------------------------------------------------------------------
    # Page 3: Chapter 1 Opener (Theme: DARK)
    # -------------------------------------------------------------------------
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=3,
            chapter_number=1,
            chapter_name="Storage Engine Internals & WAL Architecture",
            page_type=LayoutType.CHAPTER_OPENER.value,
            layout=LayoutType.CHAPTER_OPENER.value,
            theme=Theme.DARK,
            icon="database",
            style=PageStyle(theme=Theme.DARK, opener_template="minimal_centered"),
            content=PageContent(headline="Storage Engine Internals & WAL Architecture"),
        )
    )

    # -------------------------------------------------------------------------
    # Page 4: Chapter 1 Content - Storage Hierarchy & LSM Trees (Theme: DARK)
    # -------------------------------------------------------------------------
    ch1_p1_blocks = [
        HeadingBlock(
            level=2,
            text="Storage Memory Hierarchy & LSM Trees",
            icon="layers",
            eyebrow="Storage Architecture",
        ),
        TextBlock(
            paragraphs=[
                "High-throughput distributed databases balance write amplification against point-lookup latency by replacing in-place page updates with append-only Log-Structured Merge (LSM) trees. In this model, incoming write mutations are buffered directly in RAM using a concurrent skiplist memtable before being sequentially flushed to immutable SSTable blocks on non-volatile NVMe storage.",
                "Because random writes on solid-state drives trigger internal flash block erase cycles and premature wear, the append-only sequential write pattern maximizes physical storage bus saturation while minimizing I/O tail latency under sustained client concurrency.",
                "Background compaction threads periodically merge overlapping sorted runs, purge tombstoned keys, and reconstruct sparse index filters to bound multi-level read amplification across deep storage hierarchies.",
            ]
        ),
        CalloutBlock(
            variant="important",
            title="Production Memory Calibration",
            icon="shield-check",
            content="Calibrate active memtable write buffers to 256MB per shard with dual immutable flush queues. This prevents write stalls during heavy burst ingestion while maintaining bounded recovery replay times.",
        ),
        CodeBlock(
            language="rust",
            filename="storage/memtable.rs",
            caption="Listing 1.1: Lock-Free Skiplist Memtable Mutation Ingestion",
            line_numbers=True,
            code=(
                "pub struct MemTable {\n"
                "    arena: Arc<ArenaAllocator>,\n"
                "    skiplist: ConcurrentSkipList<KeyBytes, ValueBytes>,\n"
                "    wal_writer: Arc<Mutex<WalLogWriter>>,\n"
                "}\n\n"
                "impl MemTable {\n"
                "    pub fn put(&self, key: &[u8], value: &[u8], lsn: u64) -> Result<(), EngineError> {\n"
                "        // 1. Persist record to append-only WAL before memory mutation\n"
                "        let entry = WalRecord::new(lsn, key, value);\n"
                "        self.wal_writer.lock().append_record(&entry)?;\n\n"
                "        // 2. Insert into concurrent in-memory skiplist\n"
                "        self.skiplist.insert(key, value);\n"
                "        Ok(())\n"
                "    }\n"
                "}"
            ),
        ),
    ]
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=4,
            chapter_number=1,
            chapter_name="Storage Engine Internals & WAL Architecture",
            page_type="chapter_content",
            layout=LayoutType.EDITORIAL.value,
            theme=Theme.DARK,
            content=PageContent(headline="LSM Storage Hierarchy", blocks=ch1_p1_blocks),
        )
    )

    # -------------------------------------------------------------------------
    # Page 5: Chapter 1 Content - Durability, fsync & Benchmark Matrix (Theme: DARK)
    # -------------------------------------------------------------------------
    ch1_p2_blocks = [
        HeadingBlock(
            level=2,
            text="Comparative Storage Engine Benchmarks & Durability",
            icon="bar-chart-2",
            eyebrow="Performance Analysis",
        ),
        TextBlock(
            paragraphs=[
                "Durability in modern storage engines is enforced through strict write-ahead log (WAL) synchronization barriers. Operating system page caches buffer file mutations asynchronously in volatile kernel RAM; without explicit `fsync` barriers, an abrupt host crash or kernel panic causes uncommitted transaction loss.",
                "To optimize throughput without sacrificing crash consistency, high-performance engines implement group commit pipelines: multiple concurrent client transactions are batched into a unified log frame and flushed with a single disk synchronization barrier.",
            ]
        ),
        TableBlock(
            caption="Comparative Storage Engine Architectural Characteristics",
            columns=["Storage Architecture", "Write Amplification", "Point Read Latency", "Durability Barrier"],
            rows=[
                ["B+ Tree (In-Place Updates)", "High (10x-30x)", "Low: O(log N) Single Seek", "Periodic Checkpoint WAL"],
                ["LSM Tree (Append-Only)", "Low to Moderate (3x-8x)", "Moderate: Multi-SSTable Seek", "Sequential Append + fsync"],
                ["Fractal Tree (Buffered)", "Very Low (2x-4x)", "Low: O(log_B N) Seek", "Hierarchical Buffer Flush"],
                ["Vector HNSW Graph", "Moderate (5x-12x)", "Approximate O(log N)", "Vector Index Snapshotting"],
            ],
            highlight_first_column=True,
            source_note="Source: VasukiSquare Storage Benchmarks (2026)",
        ),
        CalloutBlock(
            variant="tip",
            title="Group Commit Pipelining",
            icon="zap",
            content="Amortize disk barrier overhead by buffering commit requests for up to 200 microseconds. This increases write throughput by up to 8x under saturated multi-threaded workloads.",
        ),
    ]
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=5,
            chapter_number=1,
            chapter_name="Storage Engine Internals & WAL Architecture",
            page_type="chapter_content",
            layout=LayoutType.EDITORIAL.value,
            theme=Theme.DARK,
            content=PageContent(headline="Storage Durability & Benchmarks", blocks=ch1_p2_blocks),
        )
    )

    # -------------------------------------------------------------------------
    # Page 6: Chapter 2 Opener (Theme: LIGHT)
    # -------------------------------------------------------------------------
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=6,
            chapter_number=2,
            chapter_name="Consensus Protocols, Raft & Quorum Leases",
            page_type=LayoutType.CHAPTER_OPENER.value,
            layout=LayoutType.CHAPTER_OPENER.value,
            theme=Theme.LIGHT,
            icon="cpu",
            style=PageStyle(theme=Theme.LIGHT, opener_template="minimal_centered"),
            content=PageContent(headline="Consensus Protocols, Raft & Quorum Leases"),
        )
    )

    # -------------------------------------------------------------------------
    # Page 7: Chapter 2 Content - Raft Term Monotonicity & Invariants (Theme: LIGHT)
    # -------------------------------------------------------------------------
    ch2_p1_blocks = [
        HeadingBlock(
            level=2,
            text="Raft Protocol Invariants & Term Monotonicity",
            icon="shield-check",
            eyebrow="Consensus Layer",
        ),
        TextBlock(
            paragraphs=[
                "Distributed consensus ensures that independent cluster nodes agree on a deterministic sequence of state machine operations despite unreliable networks and transient node failures. In the Raft protocol, time is divided into arbitrary terms identified by monotonically increasing integer counters.",
                "Term monotonicity acts as a logical clock: if a candidate or leader discovers its term is smaller than another node, it immediately steps down to follower status. This invariant guarantees that stale leaders isolated on network partitions cannot overwrite committed log entries.",
            ]
        ),
        ComparisonBlock(
            title="Consensus Implementation Patterns & Pitfalls",
            left_title="Recommended Production Pattern",
            left_items=[
                "Enforce strict monotonic term increments",
                "Randomize election timeouts (150ms-300ms)",
                "Use joint consensus for cluster reconfiguration",
                "Validate commit index quorums before client ACK",
            ],
            right_title="Anti-Pattern / Known Failure Mode",
            right_items=[
                "Fixed static heartbeat timers across all nodes",
                "Unsynchronized concurrent membership transitions",
                "Unpersisted term counters across sudden reboots",
                "Serving stale reads without leader lease verification",
            ],
        ),
        CalloutBlock(
            variant="note",
            title="Quorum Intersection Invariant",
            icon="info",
            content="For any cluster of N voting replicas, any two quorums of size ceil((N+1)/2) must overlap in at least one node. This mathematical guarantee ensures committed entries remain durable.",
        ),
    ]
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=7,
            chapter_number=2,
            chapter_name="Consensus Protocols, Raft & Quorum Leases",
            page_type="chapter_content",
            layout=LayoutType.EDITORIAL.value,
            theme=Theme.LIGHT,
            content=PageContent(headline="Raft Protocol Invariants", blocks=ch2_p1_blocks),
        )
    )

    # -------------------------------------------------------------------------
    # Page 8: Chapter 2 Content - Automated Failover & Quorum Auditing (Theme: LIGHT)
    # -------------------------------------------------------------------------
    ch2_p2_blocks = [
        HeadingBlock(
            level=2,
            text="Automated Quorum Auditing & Failover Runbook",
            icon="terminal",
            eyebrow="Operational Runbook",
        ),
        TextBlock(
            paragraphs=[
                "Continuous automated quorum auditing ensures all voting peers participate in log replication. The following terminal session demonstrates verifying cluster topology and quorum health via the administrative CLI.",
            ]
        ),
        TerminalBlock(
            title="Quorum Verification & Replication Health",
            shell="bash",
            lines=[
                TerminalLine(kind="command", text="kubectl exec -it vasuki-node-0 -n prod -- vasuki-cli admin cluster verify-quorum --strict-linearizability", prompt="$ "),
                TerminalLine(kind="stdout", text="[INFO] Connecting to cluster topology: 5 replicas across us-east-1a, us-east-1b, us-east-1c..."),
                TerminalLine(kind="stdout", text="[INFO] Node-1 (Leader): Term 42, Commit LSN 984120, lease valid for 1840ms"),
                TerminalLine(kind="stdout", text="[INFO] Node-2 (Follower): Term 42, Match LSN 984120, replication lag 0.32ms"),
                TerminalLine(kind="stdout", text="[INFO] Node-3 (Follower): Term 42, Match LSN 984120, replication lag 0.41ms"),
                TerminalLine(kind="stdout", text="[INFO] Node-4 (Follower): Term 42, Match LSN 984119, replication lag 0.58ms"),
                TerminalLine(kind="stdout", text="[INFO] Node-5 (Follower): Term 42, Match LSN 984120, replication lag 0.35ms"),
                TerminalLine(kind="success", text="[SUCCESS] Majority quorum verified (5/5 active nodes). Zero dropped packet frames detected."),
            ],
        ),
        ChecklistBlock(
            title="Production Failover Verification Checklist",
            items=[
                ChecklistItem(text="Confirm leader lease expiration window exceeds maximum NTP clock drift.", checked=True),
                ChecklistItem(text="Verify election timeout jitter bounds are randomized between 150ms and 300ms.", checked=True),
                ChecklistItem(text="Ensure WAL storage volumes maintain at least 30% available NVMe headroom.", checked=True),
                ChecklistItem(text="Test automated failover recovery paths quarterly under synthetic packet loss.", checked=True),
            ],
        ),
    ]
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=8,
            chapter_number=2,
            chapter_name="Consensus Protocols, Raft & Quorum Leases",
            page_type="chapter_content",
            layout=LayoutType.EDITORIAL.value,
            theme=Theme.LIGHT,
            content=PageContent(headline="Quorum Auditing & Failover", blocks=ch2_p2_blocks),
        )
    )

    # -------------------------------------------------------------------------
    # Page 9: Chapter 3 Opener (Theme: DARK)
    # -------------------------------------------------------------------------
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=9,
            chapter_number=3,
            chapter_name="Operational Runbooks, Performance & Chaos Engineering",
            page_type=LayoutType.CHAPTER_OPENER.value,
            layout=LayoutType.CHAPTER_OPENER.value,
            theme=Theme.DARK,
            icon="activity",
            style=PageStyle(theme=Theme.DARK, opener_template="minimal_centered"),
            content=PageContent(headline="Operational Runbooks, Performance & Chaos Engineering"),
        )
    )

    # -------------------------------------------------------------------------
    # Page 10: Chapter 3 Content - Chaos Engineering & Resilience (Theme: DARK)
    # -------------------------------------------------------------------------
    ch3_p1_blocks = [
        HeadingBlock(
            level=2,
            text="Chaos Engineering & Network Partition Drills",
            icon="zap",
            eyebrow="Resilience Engineering",
        ),
        TextBlock(
            paragraphs=[
                "Resilience in distributed systems cannot be proven through theoretical proofs alone; it must be continuously tested via controlled fault injection. Chaos engineering systematically validates cluster self-healing by simulating network partitions, asymmetric latency spikes, and abrupt power failures.",
            ]
        ),
        StepBlock(
            title="Executing Automated Network Partition Chaos Drill",
            steps=[
                StepItem(
                    step_number=1,
                    title="Isolate Candidate Minority Node",
                    description="Inject iptables drop rules to sever bidirectional network traffic between target node and leader.",
                    code="iptables -A INPUT -s 10.0.1.15 -j DROP && iptables -A OUTPUT -d 10.0.1.15 -j DROP",
                    language="bash",
                ),
                StepItem(
                    step_number=2,
                    title="Monitor Election Transition & Quorum Stability",
                    description="Observe cluster metrics to ensure majority quorum remains healthy and rejects stale minority votes.",
                    code="vasuki-cli debug election --watch --timeout=15s",
                    language="bash",
                ),
                StepItem(
                    step_number=3,
                    title="Heal Network Partition & Reconcile Logs",
                    description="Flush kernel drop rules and verify the isolated node re-joins and syncs missing WAL frames.",
                    code="iptables -F INPUT && iptables -F OUTPUT && vasuki-cli admin cluster verify-quorum",
                    language="bash",
                ),
            ],
        ),
        CalloutBlock(
            variant="warning",
            title="Production Safety Warning",
            icon="alert-triangle",
            content="Never execute chaos partition injection drills during planned data migration windows or peak customer traffic hours.",
        ),
    ]
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=10,
            chapter_number=3,
            chapter_name="Operational Runbooks, Performance & Chaos Engineering",
            page_type="chapter_content",
            layout=LayoutType.EDITORIAL.value,
            theme=Theme.DARK,
            content=PageContent(headline="Chaos Engineering Drills", blocks=ch3_p1_blocks),
        )
    )

    # -------------------------------------------------------------------------
    # Page 11: References & Bibliography (Theme: DARK)
    # -------------------------------------------------------------------------
    ref_blocks = [
        SourceBlock(
            title="In Search of an Understandable Consensus Algorithm (Extended Version)",
            publisher="USENIX ATC",
            url="https://raft.github.io/raft.pdf",
            mode="card",
            source_number=1,
            accessed_at="2026-09-15",
        ),
        SourceBlock(
            title="The Log-Structured Merge-Tree (LSM-Tree)",
            publisher="Acta Informatica",
            url="https://www.cs.umb.edu/~poneil/lsmtree.pdf",
            mode="card",
            source_number=2,
            accessed_at="2026-09-15",
        ),
        SourceBlock(
            title="Spanner: Google's Globally-Distributed Database",
            publisher="ACM OSDI",
            url="https://research.google/pubs/spanner-googles-globally-distributed-database/",
            mode="card",
            source_number=3,
            accessed_at="2026-09-15",
        ),
        SourceBlock(
            title="Database Internals: A Deep Dive into Distributed Data Storage",
            publisher="O'Reilly Media",
            url="https://www.oreilly.com/library/view/database-internals/9781492040330/",
            mode="card",
            source_number=4,
            accessed_at="2026-09-15",
        ),
    ]
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=11,
            page_type=LayoutType.REFERENCES.value,
            layout=LayoutType.REFERENCES.value,
            theme=Theme.DARK,
            content=PageContent(headline="Cited Bibliography & Authoritative References", blocks=ref_blocks),
        )
    )

    # -------------------------------------------------------------------------
    # Page 12: Acknowledgements & Imprint (Theme: LIGHT)
    # -------------------------------------------------------------------------
    pages.append(
        Page(
            id=generate_id(),
            book_id=book_id,
            page_number=12,
            page_type=LayoutType.ACKNOWLEDGEMENT.value,
            layout=LayoutType.ACKNOWLEDGEMENT.value,
            theme=Theme.LIGHT,
            content=PageContent(
                headline="Acknowledgements & Publishing Imprint",
                blocks=[
                    AcknowledgementBlock(
                        title="Acknowledgements & Imprint",
                        lead="Crafted with precision by the VasukiSquare AI Editorial Engine.",
                        body=(
                            "This publication was compiled using VasukiSquare's deterministic A4 layout engine, "
                            "Playwright Chromium vector rasterizer, and geometric safe-area paginator. "
                            "All code samples, CLI sessions, and benchmark comparisons were formatted according to DESIGN.md tokens."
                        ),
                        signature="The VasukiSquare Editorial Architecture Group",
                        affiliation="VasukiSquare Autonomous Publishing Systems",
                    )
                ],
            ),
        )
    )

    return pages
