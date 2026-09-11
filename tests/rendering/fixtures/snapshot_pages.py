"""Snapshot page fixtures for the 10 core layouts specified in TESTS.md."""

from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import Page, PageContent, PageStyle, SourceCitation
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

    # 7. Code Page
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
            code_snippets=[{
                "language": "python",
                "code": "async def append_entries(request: AppendEntriesRequest) -> AppendEntriesResponse:\n    if request.term < current_term:\n        return AppendEntriesResponse(success=False)\n    return AppendEntriesResponse(success=True)",
            }],
        ),
        html="<pre><code class=\"language-python\">async def append_entries(request: AppendEntriesRequest) -> AppendEntriesResponse:\n    if request.term < current_term:\n        return AppendEntriesResponse(success=False)\n    return AppendEntriesResponse(success=True)</code></pre>",
    )

    # 8. Comparison Page
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
        ),
        html="""<div class="comparison-grid">
          <div class="card-box"><h3>HNSW</h3><p>Higher memory usage, sub-millisecond search latency, graph-based navigation.</p></div>
          <div class="card-box"><h3>IVF-PQ</h3><p>Compressed memory footprint, vector quantization, inverted file clustering.</p></div>
        </div>""",
    )

    # 9. References Page
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
        html="<ul><li>Ongaro, D., & Ousterhout, J. (2014). In Search of an Understandable Consensus Algorithm. USENIX ATC.</li></ul>",
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

