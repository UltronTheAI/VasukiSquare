#!/usr/bin/env python3
"""CLI script to research trending book topics, deduplicate against MongoDB, and formulate structured book ideas."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Ensure standard streams handle UTF-8 safely across Windows and legacy consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from vasukisquare.config import get_settings
from vasukisquare.research.idea_researcher import IdeaResearchService


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for book idea research."""
    parser = argparse.ArgumentParser(
        prog="research_ideas",
        description="VasukiSquare: AI-powered trending book topic research, deduplication, and idea generation engine.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Target number of accepted, production-ready book ideas to generate (default: 5).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.70,
        help="Minimum composite bookworthiness score threshold (default: 0.70).",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Optional domain category filter (e.g. 'Technology', 'Productivity', 'Leadership').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate research, deduplication, and scoring without writing records to MongoDB.",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="Optional file path to export generated book ideas as formatted JSON (e.g. artifacts/research_ideas.json).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default=None,
        choices=["groq", "ollama", "auto"],
        help="Specify LLM provider ('groq', 'ollama', or 'auto').",
    )
    parser.add_argument(
        "--ollama-model",
        type=str,
        default=None,
        help="Specify local Ollama model to use (e.g. qwen2.5:7b-instruct).",
    )
    return parser


def main(args=None):
    """CLI entry point for book idea research."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    log_level = logging.DEBUG if parsed_args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = get_settings()
    if parsed_args.llm_provider:
        settings.llm_provider = parsed_args.llm_provider
    if parsed_args.ollama_model:
        settings.ollama_model = parsed_args.ollama_model

    print("\n==========================================")
    print(" VasukiSquare Automated Idea Research")
    print("==========================================")
    print(f" Target Idea Count: {parsed_args.count}")
    print(f" Minimum Score: {parsed_args.min_score}")
    if parsed_args.category:
        print(f" Category: {parsed_args.category}")
    if parsed_args.dry_run:
        print(" Mode: DRY-RUN (No database writes)")
    if parsed_args.export_json:
        print(f" JSON Export Path: {parsed_args.export_json}")
    print("==========================================\n")

    service = IdeaResearchService(settings=settings)

    try:
        ideas = service.research_ideas(
            count=parsed_args.count,
            min_score=parsed_args.min_score,
            category=parsed_args.category,
            dry_run=parsed_args.dry_run,
        )

        print(f"\n[RESEARCH COMPLETE] Successfully researched {len(ideas)} ready book idea(s):\n")
        for idx, idea in enumerate(ideas, 1):
            print(f"--------------------------------------------------")
            print(f" #{idx} | {idea.title} ({idea.pages} pages)")
            print(f" Topic: {idea.topic}")
            print(f" Category: {idea.category} | Audience: {idea.audience}")
            print(f" Angle: {idea.angle}")
            print(f" Composite Score: {idea.scores.composite_score:.2f} (Bookworthiness: {idea.scores.bookworthiness:.2f}, Trend: {idea.scores.trend:.2f})")
            print(f" Status: {idea.status.value.upper()}")
            if idea.similar_to:
                print(f" Differentiated from: {', '.join(str(s) for s in idea.similar_to)}")

        print("--------------------------------------------------\n")

        if parsed_args.export_json:
            export_path = service.export_ideas_to_json(ideas, parsed_args.export_json)
            print(f"[EXPORT] Ideas exported to JSON at: {export_path}\n")

    except KeyboardInterrupt:
        print("\n[CANCELLED] Idea research cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Idea research failed: {e}", file=sys.stderr)
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

