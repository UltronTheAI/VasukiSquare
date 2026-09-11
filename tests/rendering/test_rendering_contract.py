"""Rendering contract and regression fixture verification tests specified in TESTS.md."""

from pathlib import Path
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.renderer.overflow import OverflowDetector, PageRepairEngine, MAX_PAGE_CHARACTERS
from vasukisquare.book.models import Page, PageContent
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.theme import Theme
from tests.rendering.fixtures.snapshot_pages import (
    get_regression_fixture_pages,
    get_technical_component_fixture_pages,
)


def test_rendering_contract_a4_dimensions_and_css():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=1,
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.LIGHT,
        html="<p>Standard text page.</p>",
    )
    html = renderer.render_page(page)
    # Check page size A4 in CSS (210mm x 297mm) and @page rule
    assert "size: A4;" in html
    assert "margin: 0;" in html
    assert "210mm" in html
    assert "297mm" in html
    assert "class=\"page" in html
    assert "page-safe-content" in html


def test_rendering_semantic_text_contrast_tokens():
    renderer = HtmlPageRenderer()
    page_light = Page(
        book_id="b-render",
        page_number=2,
        chapter_number=2,
        chapter_name="Light Chapter",
        theme=Theme.LIGHT,
        html="<p>Light content</p>",
    )
    html_light = renderer.render_page(page_light)
    # Light theme contrast tokens
    assert "--text-primary: #001e2b;" in html_light
    assert "--text-secondary: #3d4f5b;" in html_light
    assert "--text-muted: #5c6c7a;" in html_light
    assert "--text-subtle: #7c8c9a;" in html_light

    page_dark = Page(
        book_id="b-render",
        page_number=1,
        chapter_number=1,
        chapter_name="Dark Chapter",
        theme=Theme.DARK,
        html="<p>Dark content</p>",
    )
    html_dark = renderer.render_page(page_dark)
    # Dark theme contrast tokens
    assert "--text-primary-dark: #ffffff;" in html_dark
    assert "--text-secondary-dark: #e1e5e8;" in html_dark
    assert "--text-muted-dark: #c1ccd6;" in html_dark
    assert "--text-subtle-dark: #a8b3bc;" in html_dark


def test_rendering_all_10_regression_fixtures():
    renderer = HtmlPageRenderer()
    fixtures = get_regression_fixture_pages()
    assert len(fixtures) == 10

    # Test full book assembly containing all 10 fixtures
    book_html = renderer.render_book(
        pages=fixtures,
        book_title="High Scalability Architecture",
        book_topic="Distributed Systems",
    )

    assert "<!DOCTYPE html>" in book_html
    assert "class=\"book-document\"" in book_html

    # Verify each fixture has rendered correctly inside book_html
    assert "layout-cover" in book_html
    assert "layout-copyright" in book_html
    assert "VasukiSquare AI" in book_html
    assert "layout-toc" in book_html
    assert "Table of Contents" in book_html
    assert "theme-dark layout-chapter_opener" in book_html
    assert "Deep Distributed Protocols" in book_html
    assert "theme-light layout-chapter_opener" in book_html
    assert "Modern Vector Indices" in book_html
    assert "Consensus State Machines" in book_html
    assert "append_entries" in book_html
    assert "HNSW" in book_html
    assert "layout-references" in book_html
    assert "Ongaro, D." in book_html or "understandable" in book_html.lower()
    assert "layout-thank_you" in book_html
    assert "Thank You for Reading" in book_html


def test_rendering_chapter_opener_centered_and_minimal():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-render",
        page_number=4,
        chapter_number=1,
        chapter_name="Neural Foundations and Core Concepts",
        page_type=LayoutType.CHAPTER_OPENER.value,
        layout=LayoutType.CHAPTER_OPENER.value,
        theme=Theme.DARK,
        icon="cpu",
    )
    html = renderer.render_page(page)

    assert "Chapter 1" in html
    assert "Neural Foundations" in html
    assert "lucide-cpu" in html
    assert "chapter-opener-block" in html
    # Opener must be centered without body text
    assert "<p>" not in html


def test_rendering_all_14_technical_components():
    renderer = HtmlPageRenderer()
    components = get_technical_component_fixture_pages()
    assert len(components) == 14

    # 1. Light Editorial Page
    html_1 = renderer.render_page(components["light_editorial"])
    assert "theme-light" in html_1
    assert "Storage Engine Concurrency" in html_1
    assert "component-callout callout-note" in html_1

    # 2. Dark Editorial Page
    html_2 = renderer.render_page(components["dark_editorial"])
    assert "theme-dark" in html_2
    assert "Log Replication Protocol" in html_2
    assert "component-callout callout-important" in html_2

    # 3. Dark Opener
    html_3 = renderer.render_page(components["dark_chapter_opener"])
    assert "Chapter 1" in html_3
    assert "lucide-sparkles" in html_3

    # 4. Light Opener
    html_4 = renderer.render_page(components["light_chapter_opener"])
    assert "Chapter 2" in html_4
    assert "lucide-database" in html_4

    # 5. Python Code Block
    html_5 = renderer.render_page(components["python_code"])
    assert "component-code-block" in html_5
    assert "PYTHON" in html_5
    assert "consensus/rpc.py" in html_5
    assert "class" in html_5

    # 6. Rust Code Block
    html_6 = renderer.render_page(components["rust_code"])
    assert "component-code-block" in html_6
    assert "RUST" in html_6
    assert "storage/wal.rs" in html_6
    assert "WalRecord" in html_6

    # 7. Terminal Block
    html_7 = renderer.render_page(components["terminal"])
    assert "component-terminal-window" in html_7
    assert "terminal-prompt" in html_7
    assert "vasuki --start" in html_7

    # 8. Table Block
    html_8 = renderer.render_page(components["table"])
    assert "component-table" in html_8
    assert "Engine" in html_8
    assert "B-Tree" in html_8

    # 9. Source Links
    html_9 = renderer.render_page(components["source"])
    assert "component-source-card" in html_9
    assert "PostgreSQL WAL Architecture" in html_9
    assert "https://postgresql.org/docs/wal" in html_9

    # 10. Callout
    html_10 = renderer.render_page(components["callout"])
    assert "component-callout callout-important" in html_10
    assert "Safety Guarantee" in html_10

    # 11. Bar Chart
    html_11 = renderer.render_page(components["bar_chart"])
    assert "component-chart-container" in html_11
    assert "chart-svg" in html_11
    assert "Batch Size vs Ops/Sec" in html_11

    # 12. Line Chart
    html_12 = renderer.render_page(components["line_chart"])
    assert "component-chart-container" in html_12
    assert "chart-svg" in html_12
    assert "p99 Latency under Load" in html_12

    # 13. Mermaid Diagram
    html_13 = renderer.render_page(components["diagram"])
    assert "component-diagram-figure" in html_13
    assert "mermaid" in html_13
    assert "Write Path Architecture" in html_13

    # 14. Multi-Component Page
    html_14 = renderer.render_page(components["multi_component"])
    assert "component-code-block" in html_14
    assert "component-callout" in html_14
    assert "component-source-card" in html_14


def test_theme_alternation_contract():
    renderer = HtmlPageRenderer()
    p_odd = Page(
        book_id="b-render",
        page_number=10,
        chapter_number=1,
        chapter_name="Dark Chapter",
        layout=LayoutType.EDITORIAL.value,
    )
    assert p_odd.theme == Theme.DARK
    html_odd = renderer.render_page(p_odd)
    assert "theme-dark" in html_odd

    p_even = Page(
        book_id="b-render",
        page_number=20,
        chapter_number=2,
        chapter_name="Light Chapter",
        layout=LayoutType.EDITORIAL.value,
    )
    assert p_even.theme == Theme.LIGHT
    html_even = renderer.render_page(p_even)
    assert "theme-light" in html_even


def test_overflow_detection_and_repair():
    detector = OverflowDetector()
    repair_engine = PageRepairEngine(detector=detector)

    # Normal page: not overflowing
    normal_page = Page(
        book_id="b1",
        page_number=1,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(body="Short manageable paragraph that fits cleanly within A4 limits."),
    )
    assert detector.is_overflowing(normal_page) is False

    # Massive overflowing page (> MAX_PAGE_CHARACTERS)
    huge_text = "This is an extensive technical dissertation on asynchronous IO event loops and kernel epoll implementations. " * 40
    overflow_page = Page(
        book_id="b1",
        page_number=2,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(headline="Async Internals", body=huge_text),
    )
    assert detector.is_overflowing(overflow_page) is True

    # Run controlled repair
    repaired = repair_engine.repair_pages([normal_page, overflow_page])

    # Should have split into 3 pages (Page 1 normal, Page 2 first part, Page 3 continuation)
    assert len(repaired) == 3
    assert repaired[0].page_number == 1
    assert repaired[1].page_number == 2
    assert repaired[2].page_number == 3
    assert repaired[1].next_page_id == repaired[2].id
    assert repaired[2].previous_page_id == repaired[1].id
    assert "Cont." in repaired[2].content.headline


def test_lucide_svg_loaded_in_html():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b1",
        page_number=1,
        chapter_number=1,
        chapter_name="Introduction",
        layout=LayoutType.CHAPTER_OPENER.value,
        icon="sparkles",
    )
    html = renderer.render_page(page)
    assert "<svg xmlns=\"http://www.w3.org/2000/svg\"" in html
    assert "lucide-sparkles" in html
    assert "stroke=\"#00ed64\"" in html  # Brand green token in dark chapter


def test_content_validator_rejects_placeholders():
    from vasukisquare.renderer.validator import ContentValidator
    bad_page = Page(
        book_id="b-test",
        page_number=5,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(
            headline="Content for section 'Storage Engine' focusing on code.",
            body="Here is some placeholder text for the chapter.",
        ),
    )
    errors = ContentValidator.validate_page_content(bad_page)
    assert len(errors) >= 2
    assert any("content for section" in err.lower() for err in errors)
    assert any("placeholder text" in err.lower() for err in errors)


def test_density_estimator_calculation():
    from vasukisquare.renderer.overflow import DensityEstimator
    from vasukisquare.book.components import TextBlock, CodeBlock, CalloutBlock

    dense_page = Page(
        book_id="b-test",
        page_number=6,
        layout=LayoutType.CODE_FOCUS.value,
        content=PageContent(
            headline="Distributed Invariants",
            blocks=[
                TextBlock(text="Paragraph 1 with extensive architectural explanations for distributed cluster state machines."),
                CodeBlock(language="rust", code="fn main() {\n    println!(\"hello\");\n}\n"),
                CalloutBlock(variant="tip", title="Tip", content="Persistence note."),
                TextBlock(text="Paragraph 2 evaluating partition tolerances and quorum commit properties."),
            ],
        ),
    )
    density = DensityEstimator.estimate_page_density(dense_page)
    # Density should be within reasonable usable page bounds (0.25 to 0.85)
    assert 0.25 <= density <= 0.85


def test_running_title_in_header_and_footer():
    renderer = HtmlPageRenderer()
    page = Page(
        book_id="b-test",
        page_number=3,
        chapter_number=1,
        chapter_name="Consensus Invariants",
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.DARK,
        content=PageContent(headline="Raft Protocol Core", body="Text content here."),
    )
    html = renderer.render_page(
        page,
        book_title="High Scalability Architecture: Distributed Systems in Practice",
        running_title="High Scalability Architecture",
    )
    assert "High Scalability Architecture" in html
    assert "Chapter 1: Consensus Invariants" in html
    assert "class=\"header-topic\"" in html
    assert "class=\"footer-title\"" in html


def test_cover_solid_minimal_layout():
    from vasukisquare.agents.cover import CoverPlan
    from vasukisquare.renderer.cover import CoverRenderer

    renderer = CoverRenderer()
    plan = CoverPlan(
        title="Modern Distributed Systems",
        subtitle="Architectural Principles & Real-World Patterns",
        category="Technical Deep Dive",
        tone="Authoritative",
        audience="Principal Engineers",
        accent_color="#00ed64",
        background_color="#001e2b",
        layout_style="minimal",
        hero_icon="server",
    )
    artwork_html = renderer.render_source_artwork(plan)
    assert "radial-gradient" not in artwork_html
    assert "#001e2b" in artwork_html
    assert "VASUKISQUARE" in artwork_html
    assert "Modern Distributed Systems" in artwork_html

    a4_cover = renderer.render_a4_cover_page(plan, book_id="modern-dist-sys")
    assert "radial-gradient" not in a4_cover.html
    assert "cover-hero-solid" in a4_cover.html
    assert "Modern Distributed Systems" in a4_cover.html


def test_rich_text_formatting_renders_proper_html_tags():
    from vasukisquare.renderer.richtext import RichTextRenderer, RichTextParser

    text = "The **B-Tree** index provides *O(log N)* lookup, `sync_all()` guarantees durability, and [ACM Paper](https://acm.org/paper) explains concurrency. Also ~~deprecated~~ and ==highlighted== plus <kbd>Ctrl+C</kbd>."
    parsed = RichTextParser.parse_inline_formatting(text)
    html = RichTextRenderer.render_spans(parsed)

    assert "<strong>B-Tree</strong>" in html
    assert "<em>O(log N)</em>" in html
    assert "<code class=\"rich-code\">sync_all()</code>" in html
    assert "href=\"https://acm.org/paper\"" in html
    assert "class=\"rich-link\"" in html
    assert "<s>deprecated</s>" in html

    assert "<mark class=\"rich-highlight\">highlighted</mark>" in html
    assert "<kbd class=\"rich-kbd\">Ctrl+C</kbd>" in html


def test_rich_text_sanitizes_unsafe_schemes():
    from vasukisquare.renderer.richtext import RichTextRenderer, RichSpan

    unsafe_spans = [
        RichSpan(text="Click me", href="javascript:alert(1)"),
        RichSpan(text="Safe link", href="https://vasukisquare.org/docs"),
    ]
    html = RichTextRenderer.render_spans(unsafe_spans)
    assert "javascript:" not in html
    assert "<a class=\"rich-link\" href=\"#\"" in html
    assert "<a class=\"rich-link\" href=\"https://vasukisquare.org/docs\"" in html


def test_url_normalizer_cleans_search_query_artifacts():
    from vasukisquare.renderer.url_normalizer import UrlNormalizer

    raw_url = "https://www.google.com/search?q=The+Engineering+Behind+Modern+Databases%3A+B-Trees%2C+WAL%2C+MVCC"
    raw_title = "The Engineering Behind Modern Databases%3A B-Trees%2C WAL%2C MVCC"

    norm = UrlNormalizer.normalize_source(
        url=raw_url,
        title=raw_title,
        publisher="Search Engine",
    )

    assert "q=" not in norm.url
    assert "%3A" not in norm.display_title
    assert "%2C" not in norm.display_title
    assert "%20" not in norm.display_title
    assert "B-Trees" in norm.display_title
    assert norm.publisher != "Search Engine"



def test_normal_page_lucide_heading_and_callout_icons():
    from vasukisquare.book.components import HeadingBlock, CalloutBlock, TextBlock

    page = Page(
        book_id="b-test",
        page_number=3,
        chapter_number=1,
        chapter_name="Storage Fundamentals",
        layout=LayoutType.EDITORIAL.value,
        theme=Theme.DARK,
        content=PageContent(
            blocks=[
                HeadingBlock(level=2, text="Write-Ahead Logging Protocols", icon="shield-check", eyebrow="Durability Layer"),
                CalloutBlock(variant="tip", title="Zero-Copy Architecture", icon="zap", content="Direct I/O bypasses OS page cache."),
            ]
        ),
    )
    renderer = HtmlPageRenderer()
    html = renderer.render_page(page)

    assert "lucide-shield-check" in html
    assert "lucide-zap" in html
    assert "heading-eyebrow" in html
    assert "DURABILITY LAYER" in html or "Durability Layer" in html


def test_python_and_rust_syntax_highlighting_tokens():
    from vasukisquare.book.components import CodeBlock

    py_block = CodeBlock(
        language="python",
        code="async def commit_tx(session: AsyncSession) -> bool:\n    return await session.commit()\n",
        filename="db/session.py",
    )
    rust_block = CodeBlock(
        language="rust",
        code="pub struct WalEntry {\n    pub lsn: u64,\n    pub payload: Vec<u8>,\n}\n",
        filename="engine/wal.rs",
    )

    page = Page(
        book_id="b-test",
        page_number=4,
        chapter_number=2,
        chapter_name="Engine Internals",
        layout=LayoutType.CODE_FOCUS.value,
        theme=Theme.LIGHT,
        content=PageContent(blocks=[py_block, rust_block]),
    )
    renderer = HtmlPageRenderer()
    html = renderer.render_page(page)

    assert "hl-k" in html  # Keyword
    assert "hl-nf" in html or "hl-nc" in html or "hl-p" in html  # Function/Class/Punctuation
    assert "async def" in html or "async" in html
    assert "pub struct" in html or "struct" in html


def test_semantic_terminal_line_types():
    from vasukisquare.book.components import TerminalBlock, TerminalLine

    term = TerminalBlock(
        title="bash - Vasuki Cluster Init",
        lines=[
            TerminalLine(type="command", text="vasuki cluster init --nodes=3", prompt="$"),
            TerminalLine(type="comment", text="# Provisioning 3-node Raft consensus group"),
            TerminalLine(type="success", text="[OK] Quorum established across node-1, node-2, node-3"),
            TerminalLine(type="warning", text="[WARN] Node-3 clock skew: +12ms"),
            TerminalLine(type="error", text="[ERR] Disk write latency elevated on /var/data"),
        ],
    )
    page = Page(
        book_id="b-test",
        page_number=5,
        chapter_number=1,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(blocks=[term]),
    )
    renderer = HtmlPageRenderer()
    html = renderer.render_page(page)

    assert "is-command" in html
    assert "is-comment" in html
    assert "is-success" in html
    assert "is-warning" in html
    assert "is-error" in html
    assert "vasuki cluster init" in html


def test_comparison_table_formatting_and_icons():
    from vasukisquare.book.components import TableBlock

    tbl = TableBlock(
        headers=["Feature", "B-Tree", "LSM-Tree"],
        rows=[
            ["**Write Latency**", "O(log N) random I/O", "`O(1)` sequential append"],
            ["**Read Amplification**", "Low (~1-3 I/Os)", "High (SSTable compaction)"],
            ["**Space Amplification**", "Moderate (~1.3x)", "Low (~1.1x)"],
        ],
        header_icons=["layers", "hard-drive", "zap"],
        source_note="Source: Database Internals (Petrov, 2019)",
    )
    page = Page(
        book_id="b-test",
        page_number=6,
        chapter_number=2,
        layout=LayoutType.COMPARISON.value,
        content=PageContent(blocks=[tbl]),
    )
    renderer = HtmlPageRenderer()
    html = renderer.render_page(page)

    assert "lucide-layers" in html
    assert "lucide-hard-drive" in html
    assert "lucide-zap" in html
    assert "<strong>Write Latency</strong>" in html
    assert "<code class=\"rich-code\">O(1)</code>" in html
    assert "Database Internals" in html


def test_copyright_acknowledgement_and_thank_you_layouts():
    from vasukisquare.book.components import CopyrightBlock, AcknowledgementBlock

    cop_page = Page(
        book_id="b-test",
        page_number=2,
        layout=LayoutType.COPYRIGHT.value,
        theme=Theme.LIGHT,
        content=PageContent(
            blocks=[
                CopyrightBlock(
                    book_title="High-Performance Database Systems",
                    author="VasukiSquare AI Systems",
                    year="2026",
                    isbn="978-1-954123-01-2",
                    edition="First Edition",
                    publisher="VasukiSquare Architectural Press",
                    disclaimer="All rights reserved. No part of this publication may be reproduced...",
                    ordering_info="For bulk or educational orders, contact press@vasukisquare.org",
                )
            ]
        ),
    )

    ack_page = Page(
        book_id="b-test",
        page_number=14,
        layout=LayoutType.ACKNOWLEDGEMENT.value,
        theme=Theme.LIGHT,
        content=PageContent(
            headline="Acknowledgements & Open Source Credits",
            blocks=[
                AcknowledgementBlock(
                    paragraphs=[
                        "This volume was authored and structured by the VasukiSquare AI Editorial System.",
                        "We extend sincere appreciation to the authors of SQLite, PostgreSQL, and RocksDB.",
                    ],
                    contributors=[
                        "Google DeepMind Research",
                        "PostgreSQL Global Development Group",
                        "Meta RocksDB Engineering",
                        "The Rust Language Foundation",
                    ],
                )
            ],
        ),
    )

    thank_page = Page(
        book_id="b-test",
        page_number=15,
        layout=LayoutType.THANK_YOU.value,
        theme=Theme.DARK,
        content=PageContent(
            headline="Thank You for Reading",
            body="We hope this architectural guide deepens your understanding of modern distributed storage.",
        ),
    )

    renderer = HtmlPageRenderer()
    html_cop = renderer.render_page(cop_page)
    html_ack = renderer.render_page(ack_page)
    html_thank = renderer.render_page(thank_page)

    assert "layout-copyright" in html_cop
    assert "978-1-954123-01-2" in html_cop
    assert "All rights reserved" in html_cop

    assert "layout-acknowledgement" in html_ack
    assert "Google DeepMind Research" in html_ack
    assert "The Rust Language Foundation" in html_ack

    assert "layout-thank_you" in html_thank
    assert "Thank You for Reading" in html_thank


def test_validator_detects_query_and_encoding_artifacts():
    from vasukisquare.renderer.validator import ContentValidator

    dirty_page = Page(
        book_id="b-test",
        page_number=7,
        layout=LayoutType.EDITORIAL.value,
        content=PageContent(
            headline="Search Results: q=Distributed%20Consensus%20Protocols",
            body="Here is data from https://google.com/search?q=wal%20engine&utm_source=feed",
        ),
    )
    errors = ContentValidator.validate_page_content(dirty_page)
    assert len(errors) > 0
    assert any("query/encoding artifact" in err for err in errors)

