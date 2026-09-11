#!/usr/bin/env python3
"""Demo generation script producing full book.html, book.pdf, cover image, and research artifacts."""

import asyncio
import logging
import sys
from pathlib import Path
from vasukisquare.pipeline.orchestrator import EbookGenerationPipeline
from vasukisquare.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vasukisquare.demo")


async def run_demo():
    settings = get_settings()
    output_dir = Path("./output/demo")
    output_dir.mkdir(parents=True, exist_ok=True)

    demo_topic = "The Engineering Behind Modern Databases: B-Trees, WAL, MVCC and Distributed Storage"

    print("\n" + "=" * 60)
    print(" Running VasukiSquare End-to-End Demo Generation")
    print(f" Topic: {demo_topic}")
    print(f" Output: {output_dir.resolve()}")
    print("=" * 60 + "\n")

    pipeline = EbookGenerationPipeline(settings=settings)

    state = await pipeline.run(
        topic=demo_topic,
        target_pages=40,
        output_dir=output_dir,
        generate_pdf=True,
        save_raster_cover=True,
        persist_db=True,
    )

    print("\n" + "=" * 60)
    print(" Verifying Linked Page Graph & Artifact Invariants")
    print("=" * 60)

    # 1. Verify files exist
    required_files = [
        output_dir / "book.html",
        output_dir / "research.json",
        output_dir / "book_plan.json",
        output_dir / "cover.html",
    ]
    for rf in required_files:
        if rf.exists():
            print(f"  [OK] Found artifact: {rf.name} ({rf.stat().st_size:,} bytes)")
        else:
            print(f"  [MISSING] Required artifact not found: {rf}")

    # Check pages directory
    pages_dir = output_dir / "pages"
    page_files = list(pages_dir.glob("page_*.html"))
    print(f"  [OK] Generated {len(page_files)} individual page HTML files in {pages_dir.name}/")

    # 2. Verify Page Linking Graph Invariants
    pages = state.pages
    if pages:
        print(f"\n  Checking Page Linked-List Graph across {len(pages)} pages:")
        # Invariant 1: Page 1 previous_page_id is None
        assert pages[0].previous_page_id is None, "Page 1 previous_page_id must be None"
        print("  [OK] Page 1: previous_page_id is None")

        # Invariant 2: Page N next_page_id is None
        assert pages[-1].next_page_id is None, "Last page next_page_id must be None"
        print(f"  [OK] Page {len(pages)}: next_page_id is None")

        # Invariant 3: All intermediate pages are bidirectionally linked
        for i in range(1, len(pages) - 1):
            assert pages[i].previous_page_id == pages[i - 1].id, f"Page {i+1} broken previous link"
            assert pages[i].next_page_id == pages[i + 1].id, f"Page {i+1} broken next link"
        print("  [OK] All intermediate pages bidirectionally linked")

    # 3. Check PDF and Cover Raster
    pdf_file = output_dir / "book.pdf"
    if pdf_file.exists():
        print(f"  [OK] A4 PDF Generated: {pdf_file.name} ({pdf_file.stat().st_size:,} bytes)")
    else:
        print("  [INFO] PDF generation skipped or requires Playwright browser binary.")

    cover_png = output_dir / "cover.png"
    if cover_png.exists():
        print(f"  [OK] High-Res Cover PNG: {cover_png.name} ({cover_png.stat().st_size:,} bytes)")

    print("\n" + "=" * 60)
    print(" VasukiSquare Demo Complete!")
    print("=" * 60 + "\n")


def main():
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\nDemo interrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()

