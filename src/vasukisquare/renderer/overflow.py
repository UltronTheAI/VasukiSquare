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


from pydantic import BaseModel, Field


class PageUtilization(BaseModel):
    """Accurate physical A4 vertical layout utilization and educational density metrics."""

    estimated_ratio: float = Field(description="Estimated content height fraction of usable A4 height (0.0 to 1.0+)")
    status: str = Field(description="Utilization status: underfilled, optimal, or overflow_risk")
    block_breakdown: Dict[str, float] = Field(default_factory=dict, description="Estimated height in mm per component")
    usable_height_mm: float = Field(default=USABLE_PAGE_HEIGHT_MM)
    total_content_height_mm: float = Field(default=0.0)
    target_min_ratio: float = Field(default=0.70)
    target_max_ratio: float = Field(default=0.90)
    content_units: int = Field(default=0, description="Count of meaningful educational content units")
    is_underfilled: bool = Field(default=False, description="True if utilization is below the minimum threshold")
    is_hard_fail: bool = Field(default=False, description="True if content density is severely deficient (< 0.45 for normal pages)")

    @property
    def utilization_ratio(self) -> float:
        return self.estimated_ratio

    @property
    def estimated_height_mm(self) -> float:
        return self.total_content_height_mm

    @property
    def is_overflow(self) -> bool:
        return self.estimated_ratio > 0.95


class DensityEstimator:
    """Estimates vertical fill percentage and educational completeness of content on an A4 page."""

    @staticmethod
    def estimate_block_height_mm(block: Any) -> float:
        """Estimate the physical height in mm of a given component block."""
        b_type = getattr(block, "type", "")
        
        if isinstance(block, TextBlock) or b_type == "text":
            text = getattr(block, "text", "") or ""
            paragraphs = getattr(block, "paragraphs", [])
            if paragraphs:
                total_lines = sum(max(1, len(p) // 65 + 1) for p in paragraphs)
                return total_lines * 5.5 + len(paragraphs) * 3.5
            lines = max(1, len(text) // 65 + 1)
            return lines * 5.5 + 4.0

        elif isinstance(block, HeadingBlock) or b_type == "heading":
            lvl = getattr(block, "level", 2)
            return 14.0 if lvl == 1 else (11.0 if lvl == 2 else 9.0)

        elif isinstance(block, CodeBlock) or b_type == "code":
            code = getattr(block, "code", "") or ""
            code_lines = len(code.split("\n"))
            header_h = 10.0 if (getattr(block, "filename", None) or getattr(block, "language", None)) else 0.0
            caption_h = 7.0 if getattr(block, "caption", None) else 0.0
            return header_h + (code_lines * 4.8) + caption_h + 12.0

        elif b_type == "output":
            lines = (getattr(block, "content", "") or "").split("\n")
            return 12.0 + (len(lines) * 4.8) + 8.0

        elif b_type == "mistake":
            wrong = getattr(block, "wrong_code", "") or ""
            correct = getattr(block, "correct_code", "") or ""
            exp = getattr(block, "explanation", "") or ""
            w_lines = len(wrong.split("\n"))
            c_lines = len(correct.split("\n"))
            exp_lines = max(1, len(exp) // 60 + 1)
            return 16.0 + ((w_lines + c_lines) * 4.8) + (exp_lines * 5.0) + 10.0

        elif isinstance(block, TerminalBlock) or b_type == "terminal":
            lines = getattr(block, "lines", []) or []
            term_lines = len(lines) if lines else max(1, len((getattr(block, "command", "") or "").split("\n")))
            return 10.0 + (term_lines * 4.8) + 12.0

        elif isinstance(block, TableBlock) or b_type == "table":
            rows = getattr(block, "rows", []) or []
            row_count = len(rows) + 1
            caption_h = 8.0 if getattr(block, "caption", None) else 0.0
            return caption_h + (row_count * 9.5) + 8.0

        elif isinstance(block, ChartBlock) or b_type == "chart":
            return 65.0

        elif isinstance(block, DiagramBlock) or b_type == "diagram":
            return 70.0

        elif isinstance(block, CalloutBlock) or b_type in ("callout", "tip", "note", "warning", "important", "definition"):
            content = getattr(block, "content", "") or ""
            lines = max(1, len(content) // 55 + 1)
            return 12.0 + (lines * 5.5) + 8.0

        elif isinstance(block, StatisticBlock) or b_type == "statistic":
            return 45.0

        elif isinstance(block, QuoteBlock) or b_type == "quote":
            quote = getattr(block, "quote", "") or ""
            lines = max(1, len(quote) // 50 + 1)
            return (lines * 6.5) + 16.0

        elif isinstance(block, SourceBlock) or b_type == "source":
            return 28.0

        elif b_type == "step":
            steps = getattr(block, "steps", []) or []
            return 12.0 + (len(steps) * 11.0)

        elif b_type == "exercise":
            instructions = getattr(block, "instructions", []) or []
            return 30.0 + (len(instructions) * 7.5)

        elif b_type == "comparison":
            left_items = getattr(block, "left_items", []) or []
            right_items = getattr(block, "right_items", []) or []
            max_items = max(len(left_items), len(right_items), 1)
            return 18.0 + (max_items * 8.5)

        elif b_type == "checklist":
            items = getattr(block, "items", []) or []
            return 10.0 + (len(items) * 7.0)

        elif b_type == "timeline":
            items = getattr(block, "items", []) or []
            return 15.0 + (len(items) * 14.0)

        elif b_type == "icon_text":
            items = getattr(block, "items", []) or []
            return 12.0 + (len(items) * 14.0)

        elif b_type == "image":
            return 60.0

        return 15.0

    @classmethod
    def estimate_page_density(cls, page: Any) -> float:
        """Calculate the estimated fill fraction (0.0 to 1.0+) of usable A4 height."""
        util = cls.estimate_utilization(page)
        return util.estimated_ratio

    @classmethod
    def estimate_utilization(cls, page: Any, page_type: str = "chapter_content") -> PageUtilization:
        """Calculate complete physical layout utilization and component height breakdown."""
        p_type = getattr(page, "page_type", page_type) or page_type
        layout = getattr(page, "layout", "") or ""
        
        # Chapter Opener Page
        if p_type == "chapter_opener" or layout == "chapter_opener":
            return PageUtilization(
                estimated_ratio=0.45,
                status="optimal",
                block_breakdown={"chapter_opener_banner": 110.0},
                usable_height_mm=USABLE_PAGE_HEIGHT_MM,
                total_content_height_mm=110.0,
                target_min_ratio=0.25,
                target_max_ratio=0.60,
                content_units=2,
                is_underfilled=False,
                is_hard_fail=False,
            )

        # Full-page dedicated structural layouts
        if p_type in ("cover", "copyright", "toc", "thank_you", "imprint") or layout in ("cover", "copyright", "toc", "thank_you", "imprint"):
            return PageUtilization(
                estimated_ratio=0.80,
                status="optimal",
                block_breakdown={"structural_layout": 199.0},
                usable_height_mm=USABLE_PAGE_HEIGHT_MM,
                total_content_height_mm=199.0,
                target_min_ratio=0.70,
                target_max_ratio=0.90,
                content_units=3,
                is_underfilled=False,
                is_hard_fail=False,
            )

        total_height_mm = 0.0
        breakdown: Dict[str, float] = {}

        # Content object extraction
        content = getattr(page, "content", page)
        headline = getattr(content, "headline", None) if content else None

        # 1. Headline & Header Spacing
        content_units_count = 0
        if headline:
            total_height_mm += 14.0
            breakdown["headline"] = 14.0

        # 2. Content Blocks
        blocks = getattr(content, "blocks", []) if content else []
        for idx, b in enumerate(blocks):
            h = cls.estimate_block_height_mm(b)
            total_height_mm += h
            b_name = f"{getattr(b, 'type', 'block')}_{idx+1}"
            breakdown[b_name] = round(h, 1)
            content_units_count += 1

        # 3. Fallback Prose Body
        if not blocks and content and getattr(content, "body", None):
            body = content.body
            paras = [p for p in body.split("\n\n") if p.strip()]
            lines = sum(max(1, len(p) // 65 + 1) for p in paras) if paras else max(1, len(body) // 65 + 1)
            h = (lines * 5.5) + (len(paras) * 3.5 if paras else 0)
            total_height_mm += h
            breakdown["body_prose"] = round(h, 1)
            content_units_count += max(1, len(paras))

        # 4. Fallback HTML
        if not blocks and not (content and getattr(content, "body", None)) and getattr(page, "html", None):
            lines = max(1, len(page.html) // 80 + 1)
            h = lines * 5.0
            total_height_mm += h
            breakdown["html_content"] = round(h, 1)
            content_units_count += 1

        # 5. Key points
        if content and getattr(content, "key_points", None):
            kp_h = len(content.key_points) * 6.5
            total_height_mm += kp_h
            breakdown["key_points"] = round(kp_h, 1)
            content_units_count += 1

        ratio = round(total_height_mm / USABLE_PAGE_HEIGHT_MM, 3)

        # Target minimum ratios:
        # Diagram/visual: 0.60
        # Code/terminal: 0.65
        # Normal content/concept: 0.70
        has_code = any("code" in k or "terminal" in k for k in breakdown.keys())
        has_diagram = any("diagram" in k or "chart" in k for k in breakdown.keys())
        min_target = 0.60 if has_diagram else (0.65 if has_code else 0.70)

        is_underfilled = (ratio < min_target)
        is_hard_fail = (ratio < 0.45)

        if is_underfilled:
            status = "underfilled"
        elif ratio > 0.95:
            status = "overflow_risk"
        else:
            status = "optimal"

        return PageUtilization(
            estimated_ratio=ratio,
            status=status,
            block_breakdown=breakdown,
            usable_height_mm=USABLE_PAGE_HEIGHT_MM,
            total_content_height_mm=round(total_height_mm, 1),
            target_min_ratio=min_target,
            target_max_ratio=0.90,
            content_units=content_units_count,
            is_underfilled=is_underfilled,
            is_hard_fail=is_hard_fail,
        )


def estimate_page_utilization(page: Any, page_type: str = "chapter_content") -> PageUtilization:
    """Public helper to calculate page density and utilization metrics."""
    return DensityEstimator.estimate_utilization(page, page_type=page_type)


def estimate_page_utilization(page: Any, page_type: str = "chapter_content") -> PageUtilization:
    """Public helper to calculate page density and utilization metrics."""
    return DensityEstimator.estimate_utilization(page, page_type=page_type)


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

