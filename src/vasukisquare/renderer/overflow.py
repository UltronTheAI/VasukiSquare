"""Overflow detection, density estimation, and controlled page repair for physical A4 layout constraints."""

import re
from typing import List, Optional, Tuple, Dict, Any
from vasukisquare.book.models import Page, PageContent, generate_id
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.components import (
    CalloutBlock,
    ChartBlock,
    CodeBlock,
    DiagramBlock,
    HeadingBlock,
    QuoteBlock,
    SourceBlock,
    StatisticBlock,
    TableBlock,
    TerminalBlock,
    TextBlock,
    ContentBlock,
)

# Maximum content thresholds for an individual A4 page with safe padding
MAX_PAGE_CHARACTERS = 2800
MAX_CODE_LINES = 38
MAX_BODY_PARAGRAPHS = 6
USABLE_PAGE_HEIGHT_MM = 249.0  # 297mm - 48mm (top/bottom 24mm margins)


class DensityEstimator:
    """Estimates vertical fill percentage of content on an A4 page."""

    @staticmethod
    def estimate_block_height_mm(block: ContentBlock) -> float:
        """Estimate the physical height in mm of a given component block."""
        if isinstance(block, TextBlock):
            # ~60 chars per line in standard body font, ~5.5mm per line including line-height and margin
            lines = max(1, len(block.text) // 60 + 1)
            return lines * 5.5 + 4.0
        elif isinstance(block, HeadingBlock):
            return 14.0 if block.level == 1 else (11.0 if block.level == 2 else 9.0)
        elif isinstance(block, CodeBlock):
            code_lines = len(block.code.split("\n"))
            header_h = 10.0 if block.filename or block.language else 0.0
            return header_h + (code_lines * 4.8) + 12.0
        elif isinstance(block, TerminalBlock):
            term_lines = len(block.lines)
            return 10.0 + (term_lines * 4.8) + 12.0
        elif isinstance(block, TableBlock):
            row_count = len(block.rows) + 1
            caption_h = 8.0 if block.caption else 0.0
            return caption_h + (row_count * 9.5) + 8.0
        elif isinstance(block, ChartBlock):
            return 65.0
        elif isinstance(block, DiagramBlock):
            return 70.0
        elif isinstance(block, CalloutBlock):
            lines = max(1, len(block.content) // 55 + 1)
            return 12.0 + (lines * 5.5) + 8.0
        elif isinstance(block, StatisticBlock):
            return 45.0
        elif isinstance(block, QuoteBlock):
            lines = max(1, len(block.quote) // 50 + 1)
            return (lines * 6.5) + 16.0
        elif isinstance(block, SourceBlock):
            return 28.0
        return 15.0

    @classmethod
    def estimate_page_density(cls, page: Page) -> float:
        """Calculate the estimated fill fraction (0.0 to 1.0+) of usable A4 height."""
        # Opener, cover, toc, thank you have dedicated fixed spatial layouts
        if page.layout_type in {LayoutType.CHAPTER_OPENER, LayoutType.COVER, LayoutType.TOC, LayoutType.THANK_YOU, LayoutType.COPYRIGHT}:
            return 0.75

        total_height_mm = 0.0

        # Headline
        if page.content and page.content.headline:
            total_height_mm += 14.0

        # Blocks
        if page.content and page.content.blocks:
            for b in page.content.blocks:
                total_height_mm += cls.estimate_block_height_mm(b)
        elif page.content and page.content.body:
            lines = max(1, len(page.content.body) // 60 + 1)
            total_height_mm += lines * 5.5
        elif page.html:
            lines = max(1, len(page.html) // 80 + 1)
            total_height_mm += lines * 5.0

        # Key points or callouts metadata
        if page.content and page.content.key_points:
            total_height_mm += len(page.content.key_points) * 6.0

        density = total_height_mm / USABLE_PAGE_HEIGHT_MM
        return density


class OverflowDetector:
    """Inspects Page content models for capacity limits and overflow risks."""

    def __init__(self, density_estimator: Optional[DensityEstimator] = None):
        self.density_estimator = density_estimator or DensityEstimator()

    def is_overflowing(self, page: Page) -> bool:
        """Evaluate whether page content exceeds safe A4 layout thresholds."""
        if page.layout_type in {LayoutType.CHAPTER_OPENER, LayoutType.COVER, LayoutType.TOC, LayoutType.THANK_YOU, LayoutType.COPYRIGHT}:
            return False

        # Check estimated density (> 0.98 is high risk of overflow)
        density = self.density_estimator.estimate_page_density(page)
        if density > 0.98:
            return True

        # Character count of extracted body or HTML
        total_chars = len(page.html) or len(page.content.body or "") or 0
        if total_chars > MAX_PAGE_CHARACTERS:
            return True

        # Check code snippet lines
        if page.content and page.content.blocks:
            for b in page.content.blocks:
                if isinstance(b, CodeBlock) and len(b.code.split("\n")) > MAX_CODE_LINES:
                    return True

        for snippet in page.content.code_snippets:
            lines = snippet.get("code", "").split("\n")
            if len(lines) > MAX_CODE_LINES:
                return True

        return False

    def detect_overflow_metrics(self, page: Page) -> dict:
        """Return diagnostic metrics on page content density."""
        density = self.density_estimator.estimate_page_density(page)
        body_text = page.content.body or ""
        total_chars = len(body_text) or len(page.html)
        return {
            "total_chars": total_chars,
            "max_allowed_chars": MAX_PAGE_CHARACTERS,
            "density_fraction": round(density, 3),
            "is_overflow": self.is_overflowing(page),
            "code_snippets_count": len(page.content.code_snippets),
        }


class ContentSplitter:
    """Splits long text, paragraphs, or code blocks cleanly at natural sentence/statement boundaries."""

    @staticmethod
    def split_body_text(text: str, max_chars: int = 2000) -> Tuple[str, str]:
        """Split text cleanly into two portions avoiding mid-sentence cuts."""
        if len(text) <= max_chars:
            return text, ""

        paragraphs = text.split("\n\n")
        first_part: List[str] = []
        curr_len = 0

        for para in paragraphs:
            if curr_len + len(para) + 2 <= max_chars or not first_part:
                first_part.append(para)
                curr_len += len(para) + 2
            else:
                break

        part1 = "\n\n".join(first_part)
        part2 = text[len(part1):].strip()
        if not part2 and len(text) > max_chars:
            sentences = re.split(r"(?<=[.!?])\s+", text)
            s_part1: List[str] = []
            s_len = 0
            for s in sentences:
                if s_len + len(s) + 1 <= max_chars or not s_part1:
                    s_part1.append(s)
                    s_len += len(s) + 1
                else:
                    break
            part1 = " ".join(s_part1)
            part2 = text[len(part1):].strip()

        return part1, part2


class PageRepairEngine:
    """Applies controlled page splitting and re-links adjacent page pointers."""

    def __init__(self, detector: Optional[OverflowDetector] = None, splitter: Optional[ContentSplitter] = None):
        self.detector = detector or OverflowDetector()
        self.splitter = splitter or ContentSplitter()

    def repair_pages(self, pages: List[Page]) -> List[Page]:
        """Inspect all pages in a book, splitting overflowing pages and updating graph links."""
        repaired_pages: List[Page] = []

        for page in pages:
            if not self.detector.is_overflowing(page):
                repaired_pages.append(page)
                continue

            # Check if page has structured blocks
            if page.content and page.content.blocks and len(page.content.blocks) > 1:
                # Split blocks across pages preserving atomic blocks
                mid = len(page.content.blocks) // 2
                blocks_1 = page.content.blocks[:mid]
                blocks_2 = page.content.blocks[mid:]

                page.content.blocks = blocks_1
                page.validation["repaired_overflow"] = True
                repaired_pages.append(page)

                continuation_page = Page(
                    id=generate_id(),
                    book_id=page.book_id,
                    page_number=page.page_number + 1,
                    page_type=page.page_type,
                    chapter_number=page.chapter_number,
                    chapter_name=page.chapter_name,
                    theme=page.theme,
                    layout=page.layout,
                    content=PageContent(
                        headline=f"{page.content.headline or 'Section'} (Cont.)",
                        blocks=blocks_2,
                    ),
                    previous_page_id=page.id,
                    next_page_id=page.next_page_id,
                )
                repaired_pages.append(continuation_page)
                continue

            # Controlled Repair: Split body content across two pages
            body = page.content.body or ""
            part1, part2 = self.splitter.split_body_text(body, max_chars=1800)

            # Update first page
            page.content.body = part1
            if not page.content.blocks:
                page.html = f"<p>{part1}</p>"
            page.validation["repaired_overflow"] = True
            repaired_pages.append(page)

            if part2:
                # Create continuation page
                continuation_page = Page(
                    id=generate_id(),
                    book_id=page.book_id,
                    page_number=page.page_number + 1,
                    page_type=page.page_type,
                    chapter_number=page.chapter_number,
                    chapter_name=page.chapter_name,
                    theme=page.theme,
                    layout=page.layout,
                    content=PageContent(
                        headline=f"{page.content.headline or 'Section'} (Cont.)",
                        body=part2,
                        key_points=page.content.key_points,
                    ),
                    html=f"<p>{part2}</p>",
                    previous_page_id=page.id,
                    next_page_id=page.next_page_id,
                )
                repaired_pages.append(continuation_page)

        # Re-number and re-link the entire chain sequentially
        for i, p in enumerate(repaired_pages):
            p.page_number = i + 1
            p.previous_page_id = repaired_pages[i - 1].id if i > 0 else None
            p.next_page_id = repaired_pages[i + 1].id if i < len(repaired_pages) - 1 else None

        return repaired_pages

