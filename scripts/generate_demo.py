#!/usr/bin/env python3
"""Offline, deterministic demo generation script for VasukiSquare.

Generates the complete VasukiSquare demo ebook (HTML, A4 PDF, high-res Cover PNG,
and JSON artifacts) using 100% pre-written, hardcoded local demo content fixtures.

STRICT GUARANTEES:
- ZERO LLM calls (Groq, Ollama, OpenAI, etc.).
- ZERO LangChain agents, chains, or prompt templates.
- ZERO web search, SearXNG, or internet research queries.
- ZERO external HTTP/API network requests.
- ZERO API keys required.
- Fast, fully deterministic execution exercising the production rendering & PDF engine.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import List

# Ensure src and root directories are in Python module search path
_ROOT_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _ROOT_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from scripts.demo_content import (
    DEMO_TITLE,
    DEMO_TOPIC,
    get_demo_book_plan,
    get_demo_cover_plan,
    get_demo_intent,
    get_demo_raw_pages,
    get_demo_research_corpus,
)
from vasukisquare.book.components import SourceBlock, TocBlock, TocEntry
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import Page
from vasukisquare.design.theme import Theme
from vasukisquare.design.themes import generate_book_theme
from vasukisquare.renderer.cover import CoverRenderer, CoverService
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.renderer.overflow import PageRepairEngine
from vasukisquare.renderer.pdf import PdfRenderer
from vasukisquare.renderer.preflight import preflight_book

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vasukisquare.demo")


async def run_demo(output_dir: Path = Path("./output/demo")) -> None:
    """Execute the end-to-end offline rendering pipeline for the VasukiSquare demo book."""
    start_time = time.perf_counter()
    output_dir = output_dir.resolve()
    pages_dir = output_dir / "pages"
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(" VasukiSquare Deterministic Offline Demo Generation")
    print(f" Title:  {DEMO_TITLE}")
    print(f" Topic:  {DEMO_TOPIC}")
    print(f" Output: {output_dir}")
    print(" Mode:   100% Offline (Zero LLM / Zero Network / Fast Deterministic)")
    print("=" * 70 + "\n")

    # -------------------------------------------------------------------------
    # 1. Load Hardcoded Demo Content Fixtures
    # -------------------------------------------------------------------------
    logger.info("Loading deterministic demo content fixtures...")
    intent = get_demo_intent()
    cover_plan = get_demo_cover_plan()
    research_corpus = get_demo_research_corpus()
    book_plan = get_demo_book_plan()
    raw_pages: List[Page] = get_demo_raw_pages()

    # -------------------------------------------------------------------------
    # 2. Render High-Resolution Cover & A4 Cover Page
    # -------------------------------------------------------------------------
    logger.info("Rendering 1600x2560 source cover artwork and A4 printable cover...")
    cover_renderer = CoverRenderer()
    cover_html = cover_renderer.render_source_artwork(cover_plan)
    (output_dir / "cover.html").write_text(cover_html, encoding="utf-8")

    a4_cover_page = cover_renderer.render_a4_cover_page(cover_plan, book_id="demo-distributed-systems")
    if a4_cover_page and a4_cover_page.html:
        # Replace placeholder page 1 with the rendered A4 cover page
        a4_cover_page.id = raw_pages[0].id
        a4_cover_page.page_number = 1
        raw_pages[0] = a4_cover_page

    # -------------------------------------------------------------------------
    # 3. Dynamic Book Theme Generation & Harmonization
    # -------------------------------------------------------------------------
    logger.info("Generating harmonized book theme palette...")
    book_theme = generate_book_theme(
        num_chapters=len(book_plan.chapters),
        seed=cover_plan.cover_seed or 42,
    )

    # Apply section and chapter theme styles to raw pages
    for p in raw_pages:
        ch_num = p.chapter_number
        if ch_num and ch_num in book_theme.chapters:
            sec_theme = book_theme.chapters[ch_num]
        elif p.page_type in (LayoutType.REFERENCES.value, LayoutType.ACKNOWLEDGEMENT.value, LayoutType.THANK_YOU.value):
            sec_theme = book_theme.backmatter
        else:
            sec_theme = book_theme.frontmatter

        theme_enum = Theme(sec_theme.mode.lower()) if hasattr(sec_theme, "mode") and sec_theme.mode else Theme.LIGHT
        p.theme = theme_enum
        p.style.theme = theme_enum
        p.style.background_color = sec_theme.background_color
        p.style.text_color = sec_theme.text_color
        p.style.text_muted = sec_theme.text_muted
        p.style.border_color = sec_theme.border_color
        p.style.accent_color = sec_theme.accent_color

        if ch_num and p.page_type == LayoutType.CHAPTER_OPENER.value:
            opener_styles = [
                "minimal_centered", "left_accent_banner", "split_contrast",
                "editorial_classic", "technical_blueprint", "icon_heroic"
            ]
            p.style.opener_template = opener_styles[(ch_num - 1) % len(opener_styles)]

    # -------------------------------------------------------------------------
    # 4. Overflow Safe-Area Validation & Pagination Repair
    # -------------------------------------------------------------------------
    logger.info("Running PageRepairEngine safe-area boundary validation...")
    repair_engine = PageRepairEngine()
    repaired_pages = repair_engine.repair_pages(raw_pages)

    # -------------------------------------------------------------------------
    # 5. Dynamically Resolve Table of Contents & References
    # -------------------------------------------------------------------------
    logger.info("Resolving dynamic Table of Contents and cited bibliography...")
    chapter_start_pages: dict[int, int] = {}
    for p in repaired_pages:
        if (p.page_type == LayoutType.CHAPTER_OPENER.value or p.layout == LayoutType.CHAPTER_OPENER.value) and p.chapter_number is not None:
            if p.chapter_number not in chapter_start_pages:
                chapter_start_pages[p.chapter_number] = p.page_number

    for p in repaired_pages:
        if p.page_type == LayoutType.TOC.value or p.layout == LayoutType.TOC.value:
            toc_entries = []
            for ch in book_plan.chapters:
                resolved_pnum = chapter_start_pages.get(ch.chapter_number, 3 + (ch.chapter_number - 1) * 3)
                toc_entries.append(
                    TocEntry(
                        chapter_number=ch.chapter_number,
                        title=ch.title,
                        page_number=resolved_pnum,
                        icon=ch.icon,
                    )
                )
            # Add backmatter entries
            for back_p in repaired_pages:
                if back_p.page_type == LayoutType.REFERENCES.value:
                    toc_entries.append(
                        TocEntry(
                            chapter_number=None,
                            title="Cited Bibliography & Authoritative References",
                            page_number=back_p.page_number,
                            icon="book-open",
                        )
                    )
                elif back_p.page_type == LayoutType.ACKNOWLEDGEMENT.value:
                    toc_entries.append(
                        TocEntry(
                            chapter_number=None,
                            title="Acknowledgements & Publishing Imprint",
                            page_number=back_p.page_number,
                            icon="sparkles",
                        )
                    )
            p.content.blocks = [
                TocBlock(
                    title="Table of Contents",
                    subtitle=f"Structural Blueprint for {book_plan.title}",
                    entries=toc_entries,
                )
            ]

        elif p.page_type == LayoutType.REFERENCES.value or p.layout == LayoutType.REFERENCES.value:
            if research_corpus and research_corpus.documents:
                ref_blocks = []
                for idx, doc in enumerate(research_corpus.documents[:6], start=1):
                    ref_blocks.append(
                        SourceBlock(
                            title=doc.title or "Authoritative Domain Specification",
                            publisher=doc.domain or doc.publisher or "Primary Source",
                            url=doc.url,
                            mode="card",
                            source_number=idx,
                        )
                    )
                if ref_blocks:
                    p.content.blocks = ref_blocks

    # -------------------------------------------------------------------------
    # 6. Establish Bidirectional Linked-List Page Pointers
    # -------------------------------------------------------------------------
    logger.info("Establishing bidirectional page graph linking...")
    num_pages = len(repaired_pages)
    for i, page in enumerate(repaired_pages):
        page.page_number = i + 1
        page.previous_page_id = repaired_pages[i - 1].id if i > 0 else None
        page.next_page_id = repaired_pages[i + 1].id if i < num_pages - 1 else None

    # -------------------------------------------------------------------------
    # 7. Render Individual Canonical HTML Pages
    # -------------------------------------------------------------------------
    logger.info("Rendering canonical HTML for all pages...")
    html_renderer = HtmlPageRenderer()
    for p in repaired_pages:
        if p.layout != LayoutType.COVER.value or not p.html:
            p.html = html_renderer.render_page(
                p,
                book_plan.title,
                intent.topic,
                running_title=book_plan.running_title,
            )
        p_file = pages_dir / f"page_{p.page_number:03d}.html"
        p_file.write_text(p.html, encoding="utf-8")

    # -------------------------------------------------------------------------
    # 8. Preflight Quality & Boundary Audit
    # -------------------------------------------------------------------------
    logger.info("Executing preflight quality & contract audit...")
    preflight_report = preflight_book(repaired_pages, book_theme=book_theme)
    (output_dir / "preflight_report.json").write_text(
        preflight_report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # 9. Assembled Book HTML
    # -------------------------------------------------------------------------
    logger.info("Assembling consolidated book.html...")
    assembled_html = html_renderer.render_book(
        pages=repaired_pages,
        book_title=book_plan.title,
        book_topic=intent.topic,
        running_title=book_plan.running_title,
        auto_repair=False,
    )
    (output_dir / "book.html").write_text(assembled_html, encoding="utf-8")

    # -------------------------------------------------------------------------
    # 10. PDF Export & High-Resolution Raster Cover
    # -------------------------------------------------------------------------
    logger.info("Exporting A4 PDF and raster Cover PNG via Playwright...")
    pdf_renderer = PdfRenderer()
    pdf_file = output_dir / "book.pdf"
    try:
        await pdf_renderer.render_pdf_from_html(assembled_html, pdf_file)
    except Exception as e:
        logger.warning(f"PDF rendering encountered error: {e}")

    cover_service = CoverService(renderer=cover_renderer)
    cover_png = output_dir / "cover.png"
    try:
        await cover_service.save_raster(cover_html, cover_png)
    except Exception as e:
        logger.warning(f"Cover raster screenshot encountered error: {e}")

    # -------------------------------------------------------------------------
    # 11. Write Metadata Artifacts (book_plan.json, research.json, cover_plan.json)
    # -------------------------------------------------------------------------
    (output_dir / "book_plan.json").write_text(
        book_plan.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "research.json").write_text(
        research_corpus.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "cover_plan.json").write_text(
        cover_plan.model_dump_json(indent=2),
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - start_time

    # -------------------------------------------------------------------------
    # 12. Invariant Verification & Output Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(" Verifying Linked Page Graph & Artifact Invariants")
    print("=" * 70)

    # Check Required Files
    required_files = [
        output_dir / "book.html",
        output_dir / "research.json",
        output_dir / "book_plan.json",
        output_dir / "cover.html",
        output_dir / "cover_plan.json",
        output_dir / "preflight_report.json",
    ]
    for rf in required_files:
        if rf.exists():
            print(f"  [OK] Artifact: {rf.name} ({rf.stat().st_size:,} bytes)")
        else:
            print(f"  [MISSING] Artifact not found: {rf}")

    page_files = sorted(pages_dir.glob("page_*.html"))
    print(f"  [OK] Individual Page HTML files: {len(page_files)} pages in {pages_dir.name}/")

    # Check Page Linked-List Graph Invariants
    print(f"\n  Checking Page Linked-List Graph across {len(repaired_pages)} pages:")
    assert repaired_pages[0].previous_page_id is None, "Page 1 previous_page_id must be None"
    print("  [OK] Page 1: previous_page_id is None")

    assert repaired_pages[-1].next_page_id is None, "Last page next_page_id must be None"
    print(f"  [OK] Page {len(repaired_pages)}: next_page_id is None")

    for i in range(1, len(repaired_pages) - 1):
        assert repaired_pages[i].previous_page_id == repaired_pages[i - 1].id, (
            f"Page {i+1} broken previous link: {repaired_pages[i].previous_page_id} != {repaired_pages[i-1].id}"
        )
        assert repaired_pages[i].next_page_id == repaired_pages[i + 1].id, (
            f"Page {i+1} broken next link: {repaired_pages[i].next_page_id} != {repaired_pages[i+1].id}"
        )
    print("  [OK] All intermediate pages are bidirectionally linked in graph sequence")

    # Check PDF & Cover PNG
    if pdf_file.exists():
        print(f"  [OK] A4 PDF Generated: {pdf_file.name} ({pdf_file.stat().st_size:,} bytes)")
    else:
        print("  [WARN] PDF file not generated.")

    if cover_png.exists():
        print(f"  [OK] High-Res Cover PNG: {cover_png.name} ({cover_png.stat().st_size:,} bytes)")
    else:
        print("  [WARN] Cover PNG not generated.")

    print("\n" + "=" * 70)
    print(f" VasukiSquare Demo Complete in {elapsed:.2f}s!")
    print("=" * 70 + "\n")


def main():
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\nDemo generation interrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
