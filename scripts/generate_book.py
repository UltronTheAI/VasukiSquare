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
    parser.add_argument(
        "--ollama-model",
        type=str,
        default=None,
        help="Specify the Ollama model to use for local generation.",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default=None,
        help="Specify LLM provider ('groq', 'ollama', or 'auto').",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume generation from latest stage/page checkpoints in output directory.",
    )
    args = parser.parse_args()

    # Validate mutual exclusivity between --prompt and --prompt-file
    if args.prompt and args.prompt_file:
        parser.error("Arguments --prompt and --prompt-file are mutually exclusive. Please provide only one.")

    return args


async def main_async():
    args = parse_args()
    try:
        from vasukisquare.config import load_config
        app_config = load_config()
    except Exception as e:
        print(f"\n[CONFIG ERROR] Failed to load configuration: {e}\n", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()

    if args.ollama_model:
        settings.ollama_model = args.ollama_model
    if args.llm_provider:
        settings.llm_provider = args.llm_provider

    # Resolve prompt text from --prompt-file if specified
    prompt_text = args.prompt
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            print(f"Error: Prompt file not found at: {prompt_path.resolve()}", file=sys.stderr)
            sys.exit(1)
        prompt_text = prompt_path.read_text(encoding="utf-8").strip()

    pipeline = EbookGenerationPipeline(settings=settings)
    out_dir = Path(args.output_dir)

    print(f"\n==========================================")
    print(f" {app_config.branding.engine_name}")
    print(f" Publisher: {app_config.branding.publication_name}")
    print(f" Topic: {args.topic}")
    if args.title:
        print(f" Title: {args.title}")
    print(f" Target Pages: {args.pages}")
    if prompt_text:
        preview = prompt_text[:120] + "..." if len(prompt_text) > 120 else prompt_text
        print(f" Editorial Brief: {preview}")
    print(f" Output Directory: {out_dir.resolve()}")
    if args.resume:
        print(f" Mode: RESUME from checkpoints")
    print(f"==========================================\n")

    state = await pipeline.run(
        topic=args.topic,
        title=args.title,
        prompt=prompt_text,
        target_pages=args.pages,
        output_dir=out_dir,
        generate_pdf=not args.no_pdf,
        persist_db=not args.no_db,
        resume=args.resume,
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
    except Exception as e:
        from vasukisquare.config import ConfigValidationError
        if isinstance(e, ConfigValidationError):
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()

