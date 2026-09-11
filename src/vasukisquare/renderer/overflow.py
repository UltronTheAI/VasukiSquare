"""Overflow detection and controlled page repair for physical A4 layout constraints."""

import re
from typing import List, Optional, Tuple
from vasukisquare.book.models import Page, PageContent, generate_id
from vasukisquare.book.layout import LayoutType

# Maximum content thresholds for an individual A4 page with safe padding
MAX_PAGE_CHARACTERS = 2800
MAX_CODE_LINES = 42
MAX_BODY_PARAGRAPHS = 6


class OverflowDetector:
    """Inspects Page content models for capacity limits and overflow risks."""

    def is_overflowing(self, page: Page) -> bool:
        """Evaluate whether page content exceeds safe A4 layout thresholds."""
        # Chapter opener, cover, toc, etc. have fixed bounded templates
        if page.layout_type in {LayoutType.CHAPTER_OPENER, LayoutType.COVER, LayoutType.TOC, LayoutType.THANK_YOU}:
            return False

        # Character count of extracted body or HTML
        total_chars = len(page.html) or len(page.content.body or "") or 0
        if total_chars > MAX_PAGE_CHARACTERS:
            return True

        # Check code snippet lines
        for snippet in page.content.code_snippets:
            lines = snippet.get("code", "").split("\n")
            if len(lines) > MAX_CODE_LINES:
                return True

        return False

    def detect_overflow_metrics(self, page: Page) -> dict:
        """Return diagnostic metrics on page content density."""
        body_text = page.content.body or ""
        total_chars = len(body_text) or len(page.html)
        return {
            "total_chars": total_chars,
            "max_allowed_chars": MAX_PAGE_CHARACTERS,
            "is_overflow": total_chars > MAX_PAGE_CHARACTERS,
            "code_snippets_count": len(page.content.code_snippets),
        }


class ContentSplitter:
    """Splits long text, paragraphs, or code blocks cleanly at natural sentence/statement boundaries."""

    @staticmethod
    def split_body_text(text: str, max_chars: int = 2000) -> Tuple[str, str]:
        """Split text cleanly into two portions avoiding mid-sentence cuts."""
        if len(text) <= max_chars:
            return text, ""

        # Try splitting at paragraph boundary
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
            # Fallback to sentence boundary split
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

            # Controlled Repair: Split body content across two pages
            body = page.content.body or ""
            part1, part2 = self.splitter.split_body_text(body, max_chars=2000)

            # Update first page
            page.content.body = part1
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

