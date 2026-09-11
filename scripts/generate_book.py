#!/usr/bin/env python3
"""CLI script to generate an AI-powered technical ebook from topic or prompt."""

import argparse
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
logger = logging.getLogger("vasukisquare.cli")


def parse_args():
    parser = argparse.ArgumentParser(
        description="VasukiSquare: AI-powered research, editorial, HTML layout, and PDF ebook engine.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="The topic or detailed description of the ebook to generate.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=60,
        help="Target page count for the ebook (default: 60).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Directory where generated book files and PDF will be saved.",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF compilation and only output HTML and assets.",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip persisting records to MongoDB.",
    )
    return parser.parse_args()


async def main_async():
    args = parse_args()
    settings = get_settings()

    pipeline = EbookGenerationPipeline(settings=settings)
    out_dir = Path(args.output_dir)

    print(f"\n==========================================")
    print(f" VasukiSquare Ebook Generation Engine")
    print(f" Topic: {args.topic}")
    print(f" Target Pages: {args.pages}")
    print(f" Output Directory: {out_dir.resolve()}")
    print(f"==========================================\n")

    state = await pipeline.run(
        topic=args.topic,
        target_pages=args.pages,
        output_dir=out_dir,
        generate_pdf=not args.no_pdf,
        persist_db=not args.no_db,
    )

    print(f"\n==========================================")
    print(f" Generation Completed Successfully!")
    print(f" Title: {state.book_plan.title if state.book_plan else 'N/A'}")
    print(f" Total Pages: {len(state.pages)}")
    print(f" Artifacts:")
    for k, v in state.artifacts.items():
        print(f"   - {k}: {v}")
    if state.errors:
        print(f" Warnings / Non-fatal Errors:")
        for err in state.errors:
            print(f"   ! {err}")
    print(f"==========================================\n")


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nGeneration cancelled by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()

