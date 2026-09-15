#!/usr/bin/env python3
"""Command-line interface (CLI) for VasukiSquare AI ebook generation engine."""

import argparse
import asyncio
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

from vasukisquare.config import get_settings, load_config, ConfigValidationError
from vasukisquare.pipeline.orchestrator import EbookGenerationPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vasukisquare.cli")


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for VasukiSquare."""
    parser = argparse.ArgumentParser(
        prog="vasukisquare",
        description="VasukiSquare: AI-powered research, editorial planning, HTML layout, and PDF ebook engine.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="The core topic or subject of the ebook to generate.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional explicit public-facing title (must be <= 50 characters).",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Editorial instructions/brief specifying audience, purpose, tone, required elements.",
    )
    parser.add_argument(
        "--prompt-file",
        type=str,
        default=None,
        help="Path to a text file containing the editorial brief (mutually exclusive with --prompt).",
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
        help="Directory where generated book files, assets, and PDF will be saved.",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF compilation and only output HTML, checkpoints, and json artifacts.",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip persisting book, pages, and cover records to MongoDB.",
    )
    parser.add_argument(
        "--ollama-model",
        type=str,
        default=None,
        help="Specify the Ollama model to use for local generation (e.g. qwen2.5:7b-instruct).",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default=None,
        choices=["groq", "ollama", "auto"],
        help="Specify LLM provider ('groq', 'ollama', or 'auto').",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume generation from latest stage/page checkpoints in output directory.",
    )
    return parser


def parse_args(args=None):
    """Parse and validate command-line arguments."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.prompt and parsed_args.prompt_file:
        parser.error("Arguments --prompt and --prompt-file are mutually exclusive. Please provide only one.")

    return parsed_args


async def main_async(args=None):
    """Asynchronous main entry point for ebook generation."""
    parsed_args = parse_args(args)

    try:
        app_config = load_config()
    except ConfigValidationError as e:
        print(f"\n[CONFIG ERROR] Failed to load configuration: {e.message}\n", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[CONFIG ERROR] Failed to load configuration: {e}\n", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()

    if parsed_args.ollama_model:
        settings.ollama_model = parsed_args.ollama_model
    if parsed_args.llm_provider:
        settings.llm_provider = parsed_args.llm_provider

    # Resolve prompt text from --prompt-file if specified
    prompt_text = parsed_args.prompt
    if parsed_args.prompt_file:
        prompt_path = Path(parsed_args.prompt_file)
        if not prompt_path.exists():
            print(f"Error: Prompt file not found at: {prompt_path.resolve()}", file=sys.stderr)
            sys.exit(1)
        prompt_text = prompt_path.read_text(encoding="utf-8").strip()

    pipeline = EbookGenerationPipeline(settings=settings)
    out_dir = Path(parsed_args.output_dir)

    print("\n==========================================")
    print(f" {app_config.branding.engine_name}")
    print(f" Publisher: {app_config.branding.publication_name}")
    print(f" Topic: {parsed_args.topic}")
    if parsed_args.title:
        print(f" Title: {parsed_args.title}")
    print(f" Target Pages: {parsed_args.pages}")
    if prompt_text:
        preview = prompt_text[:120] + "..." if len(prompt_text) > 120 else prompt_text
        print(f" Editorial Brief: {preview}")
    print(f" Output Directory: {out_dir.resolve()}")
    if parsed_args.resume:
        print(" Mode: RESUME from checkpoints")
    print("==========================================\n")

    state = await pipeline.run(
        topic=parsed_args.topic,
        title=parsed_args.title,
        prompt=prompt_text,
        target_pages=parsed_args.pages,
        output_dir=out_dir,
        generate_pdf=not parsed_args.no_pdf,
        persist_db=not parsed_args.no_db,
        resume=parsed_args.resume,
    )

    print("\n==========================================")
    print(" Generation Completed Successfully!")
    print(f" Title: {state.book_plan.title if state.book_plan else 'N/A'}")
    print(f" Total Pages: {len(state.pages)}")
    print(" Artifacts:")
    for k, v in state.artifacts.items():
        print(f"   - {k}: {v}")
    if state.errors:
        print(" Warnings / Non-fatal Errors:")
        for err in state.errors:
            try:
                print(f"   ! {err}")
            except Exception:
                safe_err = str(err).encode("ascii", "replace").decode("ascii")
                print(f"   ! {safe_err}")
    print("==========================================\n")
    return state


def main():
    """Synchronous CLI entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nGeneration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        if isinstance(e, ConfigValidationError):
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
