#!/usr/bin/env python3
"""Command-line interface (CLI) for VasukiSquare AI ebook generation engine."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

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
from vasukisquare.database.connection import DatabaseManager
from vasukisquare.database.repository import BookIdeaRepository
from vasukisquare.pipeline.orchestrator import EbookGenerationPipeline
from vasukisquare.research.models import IdeaStatus

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
        default=None,
        help="The core topic or subject of the ebook to generate (required in manual mode).",
    )
    parser.add_argument(
        "--from-queue",
        action="store_true",
        help="Claim and generate the next ready book idea from MongoDB queue.",
    )
    parser.add_argument(
        "--idea-id",
        type=str,
        default=None,
        help="Target a specific idea ID from the queue (must be in ready or retryable state).",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Optional domain category filter when claiming an idea from the queue.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Claim idea, validate parameters, and simulate queue workflow without running full generation.",
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
        default=None,
        help="Target page count for the ebook (default: 60 for manual, or from claimed idea).",
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

    if not parsed_args.from_queue and not parsed_args.idea_id and not parsed_args.topic:
        parser.error("The following argument is required: --topic (or use --from-queue / --idea-id)")

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

    is_queue_mode = parsed_args.from_queue or bool(parsed_args.idea_id)
    idea = None
    idea_repo = None

    if is_queue_mode:
        db_manager = DatabaseManager(settings)
        db = db_manager.get_database()
        idea_repo = BookIdeaRepository(db, collection_name=settings.idea_collection)

        idea = idea_repo.claim_next_ready_idea(
            category=parsed_args.category,
            idea_id=parsed_args.idea_id,
            stale_timeout_minutes=settings.idea_processing_timeout_minutes,
            max_attempts=settings.idea_max_attempts,
        )
        if not idea:
            logger.info("No ready book ideas available. Nothing to generate.")
            print("\n[QUEUE] No ready book ideas available in queue. Nothing to generate.\n")
            return None

        # Validate target page bounds (strictly 40-100 pages)
        target_pages = parsed_args.pages or idea.pages
        if target_pages < 40 or target_pages > 100:
            reason = f"Idea target pages ({target_pages}) outside allowed 40-100 range."
            logger.error(f"Rejecting idea {idea.id}: {reason}")
            idea_repo.mark_rejected(idea.id, reason=reason)
            print(f"\n[QUEUE ERROR] {reason} Idea marked as REJECTED.\n", file=sys.stderr)
            return None

        if parsed_args.dry_run:
            idea_repo.update_status(idea.id, IdeaStatus.READY)
            print("\n==========================================")
            print(" DRY-RUN: Claimed Idea from Queue")
            print(f" ID: {idea.id}")
            print(f" Title: {idea.title}")
            print(f" Topic: {idea.topic}")
            print(f" Pages: {target_pages}")
            print(f" Category: {idea.category}")
            print(f" Prompt: {idea.prompt[:120] if idea.prompt else 'N/A'}")
            print(" Status reverted to READY (No generation performed)")
            print("==========================================\n")
            return None

        topic = idea.topic
        title = parsed_args.title or idea.title
        prompt_text = prompt_text or idea.prompt
        idea_id = idea.id
    else:
        topic = parsed_args.topic
        title = parsed_args.title
        target_pages = parsed_args.pages if parsed_args.pages is not None else settings.default_target_pages
        idea_id = None

    pipeline = EbookGenerationPipeline(settings=settings)
    out_dir = Path(parsed_args.output_dir)

    print("\n==========================================")
    print(f" {app_config.branding.engine_name}")
    print(f" Publisher: {app_config.branding.publication_name}")
    if is_queue_mode and idea:
        print(f" Queue Mode: ACTIVE (Idea ID: {idea.id})")
    print(f" Topic: {topic}")
    if title:
        print(f" Title: {title}")
    print(f" Target Pages: {target_pages}")
    if prompt_text:
        preview = prompt_text[:120] + "..." if len(prompt_text) > 120 else prompt_text
        print(f" Editorial Brief: {preview}")
    print(f" Output Directory: {out_dir.resolve()}")
    if parsed_args.resume:
        print(" Mode: RESUME from checkpoints")
    print("==========================================\n")

    try:
        state = await pipeline.run(
            topic=topic,
            title=title,
            prompt=prompt_text,
            target_pages=target_pages,
            output_dir=out_dir,
            generate_pdf=not parsed_args.no_pdf,
            persist_db=not parsed_args.no_db,
            resume=parsed_args.resume,
            idea_id=idea_id,
        )

        if is_queue_mode and idea_repo and idea:
            book_id = state.book.id if state.book else "generated"
            out_path = state.artifacts.get("book_html") or state.artifacts.get("book_manifest_json") or str(out_dir)
            idea_repo.mark_completed(idea.id, book_id=book_id, output_path=out_path)
            logger.info(f"Idea {idea.id} successfully marked COMPLETED (book_id={book_id})")

    except Exception as e:
        if is_queue_mode and idea_repo and idea:
            idea_repo.mark_failed(idea.id, error=str(e), max_attempts=settings.idea_max_attempts)
            logger.error(f"Idea {idea.id} marked FAILED (or REJECTED): {e}")
        raise

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
