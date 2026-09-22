#!/usr/bin/env python3
"""CLI script to run automated ebook promotion campaigns across developer platforms."""

import argparse
import asyncio
import logging
import sys

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
from vasukisquare.promotion.service import PromotionService


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for ebook promotion."""
    parser = argparse.ArgumentParser(
        prog="promotion",
        description="VasukiSquare: Automated AI Ebook Promotion and Multi-Platform Publication Engine.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of eligible ebooks to select and promote (default: from config, usually 3).",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="devto",
        choices=["devto"],
        help="Target promotion platform (default: devto).",
    )
    parser.add_argument(
        "--book",
        type=str,
        default=None,
        help="Optional specific book ID or slug to promote instead of auto-selection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate promotion: query books, generate articles, persist to MongoDB, but do NOT publish to DEV/Forem API.",
    )
    parser.add_argument(
        "--campaign-id",
        type=str,
        default=None,
        help="Optional explicit campaign run identifier for tracking or idempotency testing.",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="Optional file path to export campaign summary as formatted JSON (e.g. artifacts/promotion_summary.json).",
    )
    parser.add_argument(
        "--github-summary",
        type=str,
        default=None,
        help="Optional file path to output GitHub Action step summary markdown (defaults to GITHUB_STEP_SUMMARY env var).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )
    return parser


def write_github_step_summary(summary, summary_path=None):
    """Append structured markdown summary to GitHub Actions step summary file."""
    import os
    path = summary_path or os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        md = [
            "## 🚀 VasukiSquare Daily Promotion Summary\n",
            f"- **Campaign Run ID**: `{summary.campaign_run_id}`",
            f"- **Platform**: `{summary.platform.upper()}`",
            f"- **Mode**: {'`DRY-RUN` (Simulated)' if summary.dry_run else '`LIVE` (Published)'}",
            f"- **Books Selected**: `{summary.selected_count}`",
            f"- **Articles Generated**: `{summary.generated_count}`",
            f"- **Articles Published**: `{summary.published_count}`",
            f"- **Failures**: `{summary.failed_count}`\n",
        ]
        if summary.posts:
            md.append("### Articles Processed\n")
            md.append("| Status | Title | Book Slug | External Link / Target |")
            md.append("|---|---|---|---|")
            for p in summary.posts:
                status_str = str(p.status).lower()
                if status_str == "published":
                    status_icon = "✅ Published"
                    link_str = f"[View on DEV]({p.external_url})" if p.external_url else "-"
                elif status_str == "generated":
                    status_icon = "📝 Generated (Dry-Run)"
                    link_str = f"[{p.canonical_url}]({p.canonical_url})"
                elif status_str == "failed":
                    status_icon = "❌ Failed"
                    link_str = f"`{p.last_error or 'Error'}`"
                else:
                    status_icon = f"⏳ {p.status}"
                    link_str = "-"
                # Escape pipe chars in title
                clean_title = p.title.replace("|", "-")
                md.append(f"| {status_icon} | {clean_title} | `{p.book_slug}` | {link_str} |")
            md.append("")
        if summary.failures:
            md.append("### ⚠️ Campaign Failures\n")
            for f in summary.failures:
                md.append(f"- **{f.get('book_slug') or f.get('book_id')}**: `{f.get('error')}`")
            md.append("")

        with open(path, "a", encoding="utf-8") as fp:
            fp.write("\n".join(md) + "\n")
    except Exception as e:
        logging.getLogger("vasukisquare.promotion").warning(f"Failed to write to GITHUB_STEP_SUMMARY: {e}")


def main(args=None) -> int:
    """CLI entry point for ebook promotion campaigns."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    log_level = logging.DEBUG if parsed_args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = get_settings()

    print("\n==========================================")
    print(" VasukiSquare Automated Ebook Promotion")
    print("==========================================")
    print(f" Platform:     {parsed_args.platform}")
    print(f" Target Count: {parsed_args.count or settings.promotion_posts_per_run}")
    if parsed_args.book:
        print(f" Target Book:  {parsed_args.book}")
    if parsed_args.dry_run or settings.promotion_dry_run:
        print(" Mode:         DRY-RUN (Generated articles stored in DB, no external publication)")
    else:
        print(" Mode:         LIVE PUBLISHING")
    print(f" Canonical URL Base: {settings.publication_base_url}")
    print("==========================================\n")

    service = PromotionService(settings=settings)

    try:
        summary = asyncio.run(
            service.run_campaign(
                count=parsed_args.count,
                platform=parsed_args.platform,
                dry_run=parsed_args.dry_run if parsed_args.dry_run else None,
                book_id_or_slug=parsed_args.book,
                campaign_run_id=parsed_args.campaign_id,
            )
        )

        print("\n==========================================")
        print(" CAMPAIGN EXECUTION SUMMARY")
        print("==========================================")
        print(f" Campaign ID:      {summary.campaign_run_id}")
        print(f" Platform:         {summary.platform}")
        print(f" Mode:             {'DRY-RUN' if summary.dry_run else 'LIVE'}")
        print(f" Books Selected:   {summary.selected_count}")
        print(f" Posts Generated:  {summary.generated_count}")
        print(f" Posts Published:  {summary.published_count}")
        print(f" Failures:         {summary.failed_count}")
        print("------------------------------------------")

        if summary.posts:
            print("\nGenerated / Published Posts:")
            for p in summary.posts:
                status_badge = f"[{p.status.upper()}]"
                ext_info = f" -> {p.external_url}" if p.external_url else ""
                print(f" - {status_badge} '{p.title}' (slug: {p.book_slug}){ext_info}")

        if summary.failures:
            print("\nCampaign Failures:")
            for f in summary.failures:
                print(f" - [ERROR] Book: {f.get('book_slug') or f.get('book_id')}: {f.get('error')}")

        print("==========================================\n")

        # Export JSON if requested
        if parsed_args.export_json:
            import json
            from pathlib import Path
            p = Path(parsed_args.export_json)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(summary.model_dump_json(indent=2))
            print(f"[EXPORT] Campaign summary exported to: {parsed_args.export_json}")

        # Write to GITHUB_STEP_SUMMARY if available
        write_github_step_summary(summary, summary_path=parsed_args.github_summary)

        return 0 if summary.failed_count == 0 else 1

    except KeyboardInterrupt:
        print("\n[PROMOTION] Campaign aborted by user.")
        return 130
    except Exception as e:
        print(f"\n[PROMOTION FATAL] Campaign failed with unexpected error: {e}")
        logging.exception("Promotion campaign failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

