import logging
import math
import re
from typing import List, Optional, Tuple, Dict, Any, Union
from pydantic import BaseModel, Field

from vasukisquare.book.layout import LayoutType, PublicationProfile
from vasukisquare.book.models import (
    Page,
    PageContent,
    PageStyle,
    PageCompletenessScore,
    generate_id,
)
from vasukisquare.book.components import (
    CalloutBlock,
    ChartBlock,
    ChecklistBlock,
    CodeBlock,
    ComparisonBlock,
    ContentBlock,
    DiagramBlock,
    HeadingBlock,
    QuoteBlock,
    SourceBlock,
    StatisticBlock,
    StepBlock,
    TableBlock,
    TerminalBlock,
    TextBlock,
    TocBlock,
)
from vasukisquare.renderer.geometry import (
    SAFE_BOTTOM_EPSILON_MM,
    CONTENT_TOP_MM,
    CONTENT_BOTTOM_MM,
    AVAILABLE_CONTENT_HEIGHT_MM,
    BLOCK_GAP_MM,
    PageGeometrySpec,
)

logger = logging.getLogger(__name__)

# Maximum content thresholds for an individual A4 page with safe padding
MAX_PAGE_CHARACTERS = 2400
MAX_CODE_LINES = 32
MAX_BODY_PARAGRAPHS = 6
USABLE_PAGE_HEIGHT_MM = AVAILABLE_CONTENT_HEIGHT_MM  # 183.0mm (safe content region strictly above bottom safety gap and footer)


class PageUtilization(BaseModel):
    """Accurate physical A4 vertical layout utilization and educational density metrics."""

    estimated_ratio: float = Field(description="Estimated content height fraction of usable A4 height (0.0 to 1.0+)")
    status: str = Field(description="Utilization status: hard_failure, severely_underfilled, underfilled, enrich_if_safe, healthy, dense, or overflow_risk")
    density_band: str = Field(default="healthy", description="Density band: HARD_FAILURE, SEVERELY_UNDERFILLED, UNDERFILLED, ENRICH_IF_SAFE, HEALTHY, DENSE, OVERFLOW_RISK")
    block_breakdown: Dict[str, float] = Field(default_factory=dict, description="Estimated height in mm per component")
    usable_height_mm: float = Field(default=AVAILABLE_CONTENT_HEIGHT_MM)
    total_content_height_mm: float = Field(default=0.0)
    target_min_ratio: float = Field(default=0.85)
    target_max_ratio: float = Field(default=0.95)
    hard_fail_ratio: float = Field(default=0.55)
    content_units: int = Field(default=0, description="Count of meaningful educational content units")
    is_underfilled: bool = Field(default=False, description="True if utilization is below the minimum threshold")
    is_hard_fail: bool = Field(default=False, description="True if content density is severely deficient (< 0.55 for normal pages)")
    publication_profile: Optional[PublicationProfile] = None
    completeness_score: Optional[PageCompletenessScore] = None

    @property
    def utilization_ratio(self) -> float:
        return self.estimated_ratio

    @property
    def estimated_height_mm(self) -> float:
        return self.total_content_height_mm

    @property
    def is_overflow(self) -> bool:
        return (
            self.estimated_ratio > 0.98
            or self.total_content_height_mm > (self.usable_height_mm + SAFE_BOTTOM_EPSILON_MM)
        )


class DensityEstimator:
    """Estimates physical vertical height in mm for content blocks on an A4 page."""

    @staticmethod
    def estimate_block_height_mm(block: Any) -> float:
        """Estimate the physical height in mm of a given component block including inner padding, borders, headers, and line-wrapping."""
        b_type = getattr(block, "type", "")

        if isinstance(block, TextBlock) or b_type == "text":
            text = getattr(block, "text", "") or ""
            paragraphs = getattr(block, "paragraphs", []) or []
            if paragraphs:
                total_h = 0.0
                for p in paragraphs:
                    # ~75 chars per line in full width (170mm at 14px font, line-height 1.55 ~ 5.74mm)
                    p_lines = max(1, math.ceil(len(p) / 75.0))
                    total_h += p_lines * 5.74 + 3.17  # 3.17mm = 12px margin-bottom
                return round(total_h, 2)
            lines = max(1, math.ceil(len(text) / 75.0))
            return round(lines * 5.74 + 3.17, 2)

        elif isinstance(block, HeadingBlock) or b_type == "heading":
            lvl = getattr(block, "level", 2)
            eyebrow = getattr(block, "eyebrow", None)
            eyebrow_h = 6.0 if eyebrow else 0.0
            icon_h = 2.0 if getattr(block, "icon", None) else 0.0
            txt = getattr(block, "text", "") or ""
            if lvl == 1:
                # 30px font + 1.20 line-height + margin
                wrap_lines = max(1, math.ceil(len(txt) / 45.0))
                return round(eyebrow_h + icon_h + (wrap_lines * 10.0) + 6.0, 2)
            elif lvl == 2:
                # 22px font + 1.25 line-height + margin
                wrap_lines = max(1, math.ceil(len(txt) / 55.0))
                return round(eyebrow_h + icon_h + (wrap_lines * 8.0) + 5.0, 2)
            elif lvl == 3:
                wrap_lines = max(1, math.ceil(len(txt) / 65.0))
                return round(eyebrow_h + (wrap_lines * 6.5) + 4.0, 2)
            else:
                return round(eyebrow_h + 8.0, 2)

        elif isinstance(block, CodeBlock) or b_type == "code":
            code = getattr(block, "code", "") or ""
            raw_lines = code.split("\n")
            # Calculate wrapped lines: JetBrains Mono 12.5px fits ~70 chars per line in code pre
            wrapped_line_count = 0
            for l in raw_lines:
                wrapped_line_count += max(1, math.ceil(len(l) / 70.0))
            
            # Header (filename or lang badge): 28px = 7.4mm
            header_h = 7.4 if (getattr(block, "filename", None) or getattr(block, "language", None)) else 0.0
            caption_h = 7.0 if getattr(block, "caption", None) else 0.0
            # Container padding (14px top + 14px bottom = 28px = 7.4mm) + border (1px) + figure margin (8px top/bottom = 4.23mm)
            overhead = header_h + caption_h + 7.4 + 4.23
            return round(overhead + (wrapped_line_count * 5.13), 2)

        elif b_type == "output":
            raw_out = getattr(block, "content", "") or getattr(block, "output", "") or ""
            raw_lines = raw_out.split("\n")
            wrapped_line_count = sum(max(1, math.ceil(len(l) / 72.0)) for l in raw_lines)
            caption_h = 6.0 if getattr(block, "caption", None) else 0.0
            return round(6.0 + 5.29 + 4.23 + caption_h + (wrapped_line_count * 4.8), 2)

        elif b_type == "mistake":
            wrong = getattr(block, "wrong_code", "") or getattr(block, "mistake_code", "") or ""
            correct = getattr(block, "correct_code", "") or getattr(block, "corrected_code", "") or ""
            exp = getattr(block, "explanation", "") or ""
            w_lines = sum(max(1, math.ceil(len(l) / 68.0)) for l in wrong.split("\n")) if wrong else 0
            c_lines = sum(max(1, math.ceil(len(l) / 68.0)) for l in correct.split("\n")) if correct else 0
            exp_lines = max(1, math.ceil(len(exp) / 70.0))
            # Header (8mm) + wrong box (padding 6mm + w_lines*4.8) + fixed box (padding 6mm + c_lines*4.8) + exp + margin
            return round(14.0 + ((w_lines + c_lines) * 4.8) + (exp_lines * 5.2) + 12.0, 2)

        elif isinstance(block, TerminalBlock) or b_type == "terminal":
            lines = getattr(block, "lines", []) or []
            wrapped_count = 0
            if lines:
                for l in lines:
                    txt = getattr(l, "text", str(l)) or ""
                    # Monospace 12px font fits ~72 chars per line inside terminal window
                    wrapped_count += max(1, math.ceil(len(txt) / 72.0))
            else:
                cmd = getattr(block, "command", "") or ""
                for l in cmd.split("\n"):
                    wrapped_count += max(1, math.ceil(len(l) / 72.0))
            
            # Terminal header (dots + title + shell) = 28px = 7.4mm
            # Body padding (14px top + 14px bottom) = 28px = 7.4mm
            # Window margin (8px top + 8px bottom) = 4.23mm
            # Each visual line: 12px font line-height 1.6 (5.08mm) + 4px margin-bottom (1.06mm) = 6.14mm
            overhead = 7.4 + 7.4 + 4.23
            return round(overhead + (wrapped_count * 6.14), 2)

        elif isinstance(block, TableBlock) or b_type == "table":
            rows = getattr(block, "rows", []) or []
            cols = getattr(block, "columns", []) or getattr(block, "headers", []) or []
            num_cols = max(1, len(cols) if cols else (len(rows[0]) if rows else 1))
            col_char_capacity = max(15, int(150 / num_cols))
            
            caption_h = 8.0 if getattr(block, "caption", None) else 0.0
            source_h = 6.0 if getattr(block, "source_note", None) else 0.0
            header_row_h = 10.0
            
            # Calculate row heights with multi-line cell wrapping
            rows_total_h = 0.0
            for r in rows:
                max_cell_lines = 1
                for cell in r:
                    c_str = str(cell)
                    lines = max(1, math.ceil(len(c_str) / float(col_char_capacity)))
                    if lines > max_cell_lines:
                        max_cell_lines = lines
                # Each row: 10px top + 10px bottom padding (5.29mm) + lines * 4.79mm + 1px border
                row_h = 5.29 + (max_cell_lines * 4.79) + 0.3
                rows_total_h += row_h

            margin_h = 4.23
            return round(caption_h + header_row_h + rows_total_h + source_h + margin_h, 2)

        elif isinstance(block, ChartBlock) or b_type == "chart":
            # Chart container: padding 32px (8.46mm) + title 8mm + subtitle 5mm + SVG max-height 240px (63.5mm) + axis 4mm + note 4mm
            return 72.0

        elif isinstance(block, DiagramBlock) or b_type == "diagram":
            # Frame padding 36px (9.5mm) + diagram min-height 200px (52.9mm) + caption 6mm + margin 4.23mm
            return 76.0

        elif isinstance(block, CalloutBlock) or b_type in ("callout", "tip", "note", "warning", "important", "definition"):
            content = getattr(block, "content", "") or ""
            title = getattr(block, "title", "") or ""
            # Header: icon (20px) + title = 8.0mm
            # Container padding (14px top + 14px bottom = 28px = 7.4mm) + border
            # Content lines: callout width is ~160mm (fits ~62 chars per line)
            content_lines = max(1, math.ceil(len(content) / 62.0))
            margin_h = 4.23
            return round(7.4 + 8.0 + (content_lines * 5.5) + margin_h, 2)

        elif b_type == "comparison":
            left_items = getattr(block, "left_items", []) or []
            right_items = getattr(block, "right_items", []) or []
            title = getattr(block, "title", "") or ""
            title_h = 8.0 if title else 0.0
            
            # 2 columns grid: each column is ~78mm (fits ~36 chars per line)
            num_rows = max(len(left_items), len(right_items), 1)
            rows_h = 0.0
            for i in range(num_rows):
                l_txt = str(left_items[i]) if i < len(left_items) else ""
                r_txt = str(right_items[i]) if i < len(right_items) else ""
                l_lines = max(1, math.ceil(len(l_txt) / 36.0)) if l_txt else 0
                r_lines = max(1, math.ceil(len(r_txt) / 36.0)) if r_txt else 0
                max_l = max(l_lines, r_lines, 1)
                rows_h += (max_l * 5.0) + 2.5  # gap between list items
            
            # Padding (16px top + 16px bottom = 32px = 8.46mm) + column headers (8.0mm) + margin (4.23mm)
            return round(title_h + 8.46 + 8.0 + rows_h + 4.23, 2)

        elif b_type == "checklist":
            items = getattr(block, "items", []) or []
            title = getattr(block, "title", "") or ""
            title_h = 8.0 if title else 0.0
            items_h = 0.0
            for it in items:
                txt = getattr(it, "text", str(it)) or ""
                lines = max(1, math.ceil(len(txt) / 65.0))
                items_h += (lines * 5.2) + 2.1
            # Padding 28px (7.4mm) + margin (4.23mm)
            return round(title_h + 7.4 + items_h + 4.23, 2)

        elif b_type == "step":
            steps = getattr(block, "steps", []) or []
            title = getattr(block, "title", "") or ""
            title_h = 8.0 if title else 0.0
            steps_h = 0.0
            for s in steps:
                desc = getattr(s, "description", "") or ""
                desc_lines = max(1, math.ceil(len(desc) / 60.0))
                code = getattr(s, "code", "") or ""
                code_h = (len(code.split("\n")) * 4.8 + 6.0) if code else 0.0
                # Step card padding (24px = 6.35mm) + badge/heading (6.0mm) + desc + code + step gap (3.0mm)
                steps_h += 6.35 + 6.0 + (desc_lines * 5.0) + code_h + 3.0
            return round(title_h + steps_h + 4.23, 2)

        elif b_type == "exercise":
            title = getattr(block, "title", "") or ""
            obj = getattr(block, "objective", "") or ""
            instrs = getattr(block, "instructions", []) or []
            obj_lines = max(1, math.ceil(len(obj) / 60.0)) if obj else 0
            instr_h = sum(max(1, math.ceil(len(str(i)) / 58.0)) * 5.2 + 1.5 for i in instrs)
            code = getattr(block, "starter_code", "") or ""
            code_h = (len(code.split("\n")) * 4.8 + 8.0) if code else 0.0
            hints = getattr(block, "hints", []) or []
            hints_h = (len(hints) * 5.0 + 6.0) if hints else 0.0
            # Card padding 32px (8.46mm) + header 10.0mm + obj + instrs + code + hints + margin 4.23mm
            return round(8.46 + 10.0 + (obj_lines * 5.0) + instr_h + code_h + hints_h + 4.23, 2)

        elif b_type == "definition":
            definition = getattr(block, "definition", "") or ""
            example = getattr(block, "example", "") or ""
            def_lines = max(1, math.ceil(len(definition) / 62.0))
            ex_lines = max(1, math.ceil(len(example) / 60.0)) if example else 0
            ex_h = (ex_lines * 5.0 + 4.0) if example else 0.0
            # Header 8.0mm + padding 28px (7.4mm) + def + ex + margin 4.23mm
            return round(8.0 + 7.4 + (def_lines * 5.5) + ex_h + 4.23, 2)

        elif b_type == "timeline":
            items = getattr(block, "items", []) or []
            title = getattr(block, "title", "") or ""
            title_h = 8.0 if title else 0.0
            items_h = 0.0
            for it in items:
                desc = (it.get("description", "") if isinstance(it, dict) else getattr(it, "description", "")) or ""
                d_lines = max(1, math.ceil(len(desc) / 58.0))
                items_h += 6.0 + (d_lines * 5.0) + 3.0
            return round(title_h + 7.4 + items_h + 4.23, 2)

        elif b_type == "icon_text":
            items = getattr(block, "items", []) or []
            title = getattr(block, "title", "") or ""
            title_h = 8.0 if title else 0.0
            items_h = 0.0
            for it in items:
                txt = (it.get("text", "") if isinstance(it, dict) else getattr(it, "text", "")) or ""
                t_lines = max(1, math.ceil(len(txt) / 60.0))
                items_h += 6.0 + (t_lines * 5.0) + 4.0
            return round(title_h + items_h + 4.23, 2)

        elif isinstance(block, StatisticBlock) or b_type == "statistic":
            desc = getattr(block, "description", "") or ""
            d_lines = max(1, math.ceil(len(desc) / 60.0)) if desc else 0
            return round(24.0 + 6.0 + (d_lines * 5.0) + 8.46 + 4.23, 2)

        elif isinstance(block, QuoteBlock) or b_type == "quote":
            quote = getattr(block, "quote", "") or ""
            lines = max(1, math.ceil(len(quote) / 52.0))
            return round((lines * 6.5) + 12.0 + 8.46, 2)

        elif isinstance(block, SourceBlock) or b_type == "source":
            mode = getattr(block, "mode", "card")
            if mode == "inline":
                return 8.0
            title = getattr(block, "title", "") or ""
            t_lines = max(1, math.ceil(len(title) / 50.0))
            return round(7.4 + 5.0 + (t_lines * 5.5) + 6.0 + 4.23, 2)

        elif b_type == "image":
            caption = getattr(block, "caption", "") or ""
            cap_h = 6.0 if caption else 0.0
            return round(65.0 + cap_h + 4.23, 2)

        return 18.0

    @classmethod
    def estimate_page_density(cls, page: Any) -> float:
        """Calculate the estimated fill fraction (0.0 to 1.0+) of available content safe height."""
        util = cls.estimate_utilization(page)
        return util.estimated_ratio

    @classmethod
    def estimate_utilization(
        cls,
        page: Any,
        page_type: str = "chapter_content",
        publication_profile: Optional[PublicationProfile] = None,
    ) -> PageUtilization:
        """Calculate complete physical layout utilization, density band, and component height breakdown."""
        p_type = getattr(page, "page_type", page_type) or page_type
        layout = getattr(page, "layout", "") or ""
        profile = getattr(page, "publication_profile", publication_profile) or publication_profile

        # Poetry / Intentional Minimal Pages: exempt from normal density rules
        if profile == PublicationProfile.POETRY or p_type == "poetry" or layout == "poetry":
            return PageUtilization(
                estimated_ratio=0.45,
                status="healthy",
                density_band="HEALTHY",
                block_breakdown={"poetry_stanza": 112.0},
                usable_height_mm=AVAILABLE_CONTENT_HEIGHT_MM,
                total_content_height_mm=112.0,
                target_min_ratio=0.20,
                target_max_ratio=0.60,
                hard_fail_ratio=0.15,
                content_units=2,
                is_underfilled=False,
                is_hard_fail=False,
                publication_profile=profile,
            )

        # Chapter Opener Page: target 0.35 - 0.65
        if p_type == "chapter_opener" or layout == "chapter_opener":
            return PageUtilization(
                estimated_ratio=0.50,
                status="healthy",
                density_band="HEALTHY",
                block_breakdown={"chapter_opener_banner": 110.0},
                usable_height_mm=AVAILABLE_CONTENT_HEIGHT_MM,
                total_content_height_mm=110.0,
                target_min_ratio=0.35,
                target_max_ratio=0.65,
                hard_fail_ratio=0.25,
                content_units=2,
                is_underfilled=False,
                is_hard_fail=False,
                publication_profile=profile,
            )

        # Full-page dedicated structural layouts (cover, imprint, copyright, toc, references, acknowledgement, thank_you)
        if p_type in ("cover", "copyright", "toc", "thank_you", "imprint", "references", "acknowledgement") or layout in ("cover", "copyright", "toc", "thank_you", "imprint", "references", "acknowledgement"):
            return PageUtilization(
                estimated_ratio=0.88,
                status="healthy",
                density_band="HEALTHY",
                block_breakdown={"structural_layout": AVAILABLE_CONTENT_HEIGHT_MM * 0.88},
                usable_height_mm=AVAILABLE_CONTENT_HEIGHT_MM,
                total_content_height_mm=AVAILABLE_CONTENT_HEIGHT_MM * 0.88,
                target_min_ratio=0.60,
                target_max_ratio=0.95,
                hard_fail_ratio=0.40,
                content_units=3,
                is_underfilled=False,
                is_hard_fail=False,
                publication_profile=profile,
            )

        total_height_mm = 0.0
        breakdown: Dict[str, float] = {}

        # Content object extraction
        content = getattr(page, "content", page)
        headline = getattr(content, "headline", None) if content else None

        # 1. Headline & Header Spacing (Does NOT count as educational content unit)
        content_units_count = 0
        if headline and p_type not in ("copyright", "acknowledgement", "toc"):
            hl_lines = max(1, math.ceil(len(headline) / 50.0))
            hl_h = (hl_lines * 8.0) + 4.23
            total_height_mm += hl_h
            breakdown["headline"] = round(hl_h, 1)

        # 2. Content Blocks with Inter-block Gaps
        blocks = getattr(content, "blocks", []) if content else []
        for idx, b in enumerate(blocks):
            h = cls.estimate_block_height_mm(b)
            # Add inter-block flex gap for subsequent blocks
            if idx > 0 or (idx == 0 and headline):
                total_height_mm += BLOCK_GAP_MM
            total_height_mm += h
            b_name = f"{getattr(b, 'type', 'block')}_{idx+1}"
            breakdown[b_name] = round(h, 1)
            if isinstance(b, TextBlock) or getattr(b, "type", "") == "text":
                paras = getattr(b, "paragraphs", None) or ([p for p in getattr(b, "text", "").split("\n\n") if p.strip()] if getattr(b, "text", "") else [])
                content_units_count += max(1, len(paras))
            elif isinstance(b, StepBlock) or getattr(b, "type", "") == "step":
                content_units_count += max(1, len(getattr(b, "steps", []) or []))
            elif isinstance(b, ChecklistBlock) or getattr(b, "type", "") == "checklist":
                content_units_count += max(1, len(getattr(b, "items", []) or []))
            elif isinstance(b, (CodeBlock, TerminalBlock, TableBlock, ComparisonBlock, CalloutBlock)):
                if h >= 45.0:
                    content_units_count += 2
                else:
                    content_units_count += 1
            else:
                content_units_count += 1

        # 3. Fallback Prose Body
        if not blocks and content and getattr(content, "body", None):
            body = content.body
            paras = [p for p in body.split("\n\n") if p.strip()]
            if paras:
                total_h = 0.0
                for p in paras:
                    p_lines = max(1, math.ceil(len(p) / 75.0))
                    total_h += p_lines * 5.74 + 3.17
                total_height_mm += total_h
                breakdown["body_prose"] = round(total_h, 1)
                content_units_count += len(paras)
            else:
                lines = max(1, math.ceil(len(body) / 75.0))
                h = lines * 5.74 + 3.17
                total_height_mm += h
                breakdown["body_prose"] = round(h, 1)
                content_units_count += 1

        # 4. Fallback HTML
        if not blocks and not (content and getattr(content, "body", None)) and getattr(page, "html", None):
            lines = max(1, math.ceil(len(page.html) / 80.0))
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

        ratio = round(total_height_mm / AVAILABLE_CONTENT_HEIGHT_MM, 3)

        # Target minimum ratios based on specific content archetype:
        has_code = any("code" in k or "terminal" in k for k in breakdown.keys())
        has_diagram = any("diagram" in k or "chart" in k for k in breakdown.keys())
        has_comparison = any("comparison" in k or "table" in k for k in breakdown.keys())
        has_exercise = any("exercise" in k for k in breakdown.keys())

        if has_diagram or has_exercise:
            min_target = 0.75
        elif has_code or has_comparison:
            min_target = 0.80
        else:
            min_target = 0.85

        # Categorize density bands:
        if ratio < 0.55:
            density_band = "HARD_FAILURE"
            status = "hard_failure"
            is_underfilled = True
            is_hard_fail = True
        elif ratio < 0.70:
            density_band = "SEVERELY_UNDERFILLED"
            status = "severely_underfilled"
            is_underfilled = True
            is_hard_fail = False
        elif ratio < min_target:
            density_band = "UNDERFILLED"
            status = "underfilled"
            is_underfilled = True
            is_hard_fail = False
        elif ratio <= 0.95:
            density_band = "HEALTHY"
            status = "healthy"
            is_underfilled = False
            is_hard_fail = False
        elif ratio <= 0.98:
            density_band = "DENSE"
            status = "dense"
            is_underfilled = False
            is_hard_fail = False
        else:
            density_band = "OVERFLOW_RISK"
            status = "overflow_risk"
            is_underfilled = False
            is_hard_fail = False

        return PageUtilization(
            estimated_ratio=ratio,
            status=status,
            density_band=density_band,
            block_breakdown=breakdown,
            usable_height_mm=AVAILABLE_CONTENT_HEIGHT_MM,
            total_content_height_mm=round(total_height_mm, 1),
            target_min_ratio=min_target,
            target_max_ratio=0.95,
            hard_fail_ratio=0.55,
            content_units=content_units_count,
            is_underfilled=is_underfilled,
            is_hard_fail=is_hard_fail,
            publication_profile=profile,
        )


def estimate_page_utilization(
    page: Any,
    page_type: str = "chapter_content",
    publication_profile: Optional[PublicationProfile] = None,
) -> PageUtilization:
    """Public helper to calculate page density and utilization metrics."""
    return DensityEstimator.estimate_utilization(page, page_type=page_type, publication_profile=publication_profile)


class OverflowDetector:
    """Inspects Page content models for capacity limits and overflow risks."""

    def __init__(self, density_estimator: Optional[DensityEstimator] = None):
        self.density_estimator = density_estimator or DensityEstimator()

    def is_overflowing(self, page: Page) -> bool:
        """Evaluate whether page content exceeds safe A4 layout thresholds."""
        if page.layout_type in {LayoutType.CHAPTER_OPENER, LayoutType.COVER, LayoutType.TOC, LayoutType.THANK_YOU, LayoutType.COPYRIGHT}:
            return False

        # Check estimated density (> 0.98 is high risk of overflow or exceeds AVAILABLE_CONTENT_HEIGHT_MM)
        util = self.density_estimator.estimate_utilization(page)
        if util.is_overflow or util.total_content_height_mm > (AVAILABLE_CONTENT_HEIGHT_MM + SAFE_BOTTOM_EPSILON_MM):
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
                if isinstance(b, TerminalBlock) and len(getattr(b, "lines", []) or []) > MAX_CODE_LINES:
                    return True

        for snippet in page.content.code_snippets:
            lines = snippet.get("code", "").split("\n")
            if len(lines) > MAX_CODE_LINES:
                return True

        return False

    def detect_overflow_metrics(self, page: Page) -> dict:
        """Return diagnostic metrics on page content density."""
        util = self.density_estimator.estimate_utilization(page)
        body_text = page.content.body or ""
        total_chars = len(body_text) or len(page.html)
        return {
            "total_chars": total_chars,
            "max_allowed_chars": MAX_PAGE_CHARACTERS,
            "density_fraction": util.estimated_ratio,
            "total_content_height_mm": util.total_content_height_mm,
            "available_content_height_mm": AVAILABLE_CONTENT_HEIGHT_MM,
            "is_overflow": self.is_overflowing(page),
            "code_snippets_count": len(page.content.code_snippets),
        }


class ContentSplitter:
    """Splits long text, paragraphs, or code blocks cleanly at natural sentence/statement boundaries."""

    @staticmethod
    def split_body_text(text: str, max_chars: int = 1800) -> Tuple[str, str]:
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


# =========================================================================
# SEMANTIC COMPONENT SUB-SPLITTING UTILITIES
# =========================================================================

def split_table_block(
    table: TableBlock,
    max_rows_or_height: Union[int, float] = 6,
    max_rows: Optional[int] = None,
) -> Tuple[TableBlock, TableBlock]:
    """Split a TableBlock across pages, repeating columns/headers and adding '(Cont.)' caption."""
    rows = table.rows or []
    if len(rows) <= 1:
        return table, TableBlock(caption=f"{table.caption or 'Table'} (Cont.)", columns=table.columns, rows=[])

    if max_rows is not None:
        max_rows_or_height = max_rows

    if isinstance(max_rows_or_height, float):
        cols = table.columns or table.headers or []
        num_cols = max(1, len(cols) if cols else (len(rows[0]) if rows else 1))
        col_char_capacity = max(15, int(150 / num_cols))
        caption_h = 8.0 if table.caption else 0.0
        source_h = 6.0 if table.source_note else 0.0
        header_row_h = 10.0
        overhead = caption_h + header_row_h + source_h + 4.23
        rem_h = max(0.0, max_rows_or_height - overhead)
        accum_h = 0.0
        split_idx = 0
        for idx, r in enumerate(rows):
            max_cell_lines = 1
            for cell in r:
                c_str = str(cell)
                lines = max(1, math.ceil(len(c_str) / float(col_char_capacity)))
                if lines > max_cell_lines:
                    max_cell_lines = lines
            row_h = 5.29 + (max_cell_lines * 4.79) + 0.3
            if accum_h + row_h <= rem_h or split_idx == 0:
                accum_h += row_h
                split_idx = idx + 1
            else:
                break
        resolved_rows = min(max(1, split_idx), len(rows) - 1)
    else:
        resolved_rows = max_rows_or_height

    rows1 = rows[:resolved_rows]
    rows2 = rows[resolved_rows:]

    t1 = TableBlock(
        caption=table.caption,
        columns=table.columns,
        headers=table.headers,
        header_icons=table.header_icons,
        rows=rows1,
        alignment=table.alignment,
        icons=table.icons[:resolved_rows] if table.icons else None,
        highlight_first_column=table.highlight_first_column,
        source_note=None,
    )

    t2_caption = f"{table.caption} (Cont.)" if table.caption else "Table (Cont.)"
    t2 = TableBlock(
        caption=t2_caption,
        columns=table.columns,
        headers=table.headers,
        header_icons=table.header_icons,
        rows=rows2,
        alignment=table.alignment,
        icons=table.icons[resolved_rows:] if table.icons else None,
        highlight_first_column=table.highlight_first_column,
        source_note=table.source_note,
    )
    return t1, t2


def split_checklist_block(
    block: ChecklistBlock,
    max_items_or_height: Union[int, float] = 5,
    max_items: Optional[int] = None,
) -> Tuple[ChecklistBlock, ChecklistBlock]:
    """Split a ChecklistBlock across pages."""
    items = block.items or []
    if len(items) <= 1:
        return block, ChecklistBlock(title=f"{block.title or 'Checklist'} (Cont.)", items=[])

    if max_items is not None:
        max_items_or_height = max_items

    if isinstance(max_items_or_height, float):
        title_h = 8.0 if block.title else 0.0
        overhead = title_h + 7.4 + 4.23
        rem_h = max(0.0, max_items_or_height - overhead)
        accum_h = 0.0
        split_idx = 0
        for idx, it in enumerate(items):
            txt = getattr(it, "text", str(it)) or ""
            lines = max(1, math.ceil(len(txt) / 65.0))
            it_h = (lines * 5.2) + 2.1
            if accum_h + it_h <= rem_h or split_idx == 0:
                accum_h += it_h
                split_idx = idx + 1
            else:
                break
        resolved_items = min(max(1, split_idx), len(items) - 1)
    else:
        resolved_items = max_items_or_height

    items1 = items[:resolved_items]
    items2 = items[resolved_items:]

    b1 = ChecklistBlock(title=block.title, items=items1)
    b2_title = f"{block.title} (Cont.)" if block.title else "Checklist (Cont.)"
    b2 = ChecklistBlock(title=b2_title, items=items2)
    return b1, b2


def split_step_block(
    block: StepBlock,
    max_steps_or_height: Union[int, float] = 5,
    max_steps: Optional[int] = None,
) -> Tuple[StepBlock, StepBlock]:
    """Split a StepBlock across pages."""
    steps = block.steps or []
    if len(steps) <= 1:
        return block, StepBlock(title=f"{block.title or 'Steps'} (Cont.)", steps=[])

    if max_steps is not None:
        max_steps_or_height = max_steps

    if isinstance(max_steps_or_height, float):
        title_h = 8.0 if block.title else 0.0
        overhead = title_h + 4.23
        rem_h = max(0.0, max_steps_or_height - overhead)
        accum_h = 0.0
        split_idx = 0
        for idx, s in enumerate(steps):
            desc = getattr(s, "description", "") or ""
            desc_lines = max(1, math.ceil(len(desc) / 60.0))
            code = getattr(s, "code", "") or ""
            code_h = (len(code.split("\n")) * 4.8 + 6.0) if code else 0.0
            s_h = 6.35 + 6.0 + (desc_lines * 5.0) + code_h + 3.0
            if accum_h + s_h <= rem_h or split_idx == 0:
                accum_h += s_h
                split_idx = idx + 1
            else:
                break
        resolved_steps = min(max(1, split_idx), len(steps) - 1)
    else:
        resolved_steps = max_steps_or_height

    steps1 = steps[:resolved_steps]
    steps2 = steps[resolved_steps:]

    b1 = StepBlock(title=block.title, steps=steps1)
    b2_title = f"{block.title} (Cont.)" if block.title else "Steps (Cont.)"
    b2 = StepBlock(title=b2_title, steps=steps2)
    return b1, b2


def split_text_block(block: TextBlock, available_height_mm: float) -> Tuple[TextBlock, TextBlock]:
    """Split a TextBlock cleanly across paragraph boundaries to fit available vertical space."""
    paras = block.paragraphs or ([p for p in block.text.split("\n\n") if p.strip()] if "\n\n" in block.text else [block.text])

    if len(paras) > 1:
        accum_h = 0.0
        paras1: List[str] = []
        paras2: List[str] = []

        for p in paras:
            p_lines = max(1, math.ceil(len(p) / 75.0))
            p_h = p_lines * 5.74 + 3.17
            if accum_h + p_h <= available_height_mm or not paras1:
                paras1.append(p)
                accum_h += p_h
            else:
                paras2.append(p)

        b1 = TextBlock(
            text="\n\n".join(paras1),
            paragraphs=paras1,
            typography_role=block.typography_role,
        )
        b2 = TextBlock(
            text="\n\n".join(paras2),
            paragraphs=paras2 if paras2 else None,
            typography_role=block.typography_role,
        )
        return b1, b2
    else:
        max_chars = max(250, int(available_height_mm * 10))
        t1, t2 = ContentSplitter.split_body_text(block.text, max_chars=max_chars)
        b1 = TextBlock(text=t1, typography_role=block.typography_role)
        b2 = TextBlock(text=t2, typography_role=block.typography_role)
        return b1, b2


def split_comparison_block(block: ComparisonBlock, max_items: int) -> Tuple[ComparisonBlock, ComparisonBlock]:
    """Split a ComparisonBlock across pages if item lists are long."""
    left1 = block.left_items[:max_items]
    left2 = block.left_items[max_items:]
    right1 = block.right_items[:max_items]
    right2 = block.right_items[max_items:]

    b1 = ComparisonBlock(
        title=block.title,
        left_title=block.left_title,
        left_items=left1,
        right_title=block.right_title,
        right_items=right1,
        left_icon=block.left_icon,
        right_icon=block.right_icon,
    )
    b2_title = f"{block.title} (Cont.)" if block.title else "Comparison (Cont.)"
    b2 = ComparisonBlock(
        title=b2_title,
        left_title=block.left_title,
        left_items=left2,
        right_title=block.right_title,
        right_items=right2,
        left_icon=block.left_icon,
        right_icon=block.right_icon,
    )
    return b1, b2


def split_code_block(block: CodeBlock, available_height_mm: float) -> Tuple[CodeBlock, CodeBlock]:
    """Split a CodeBlock cleanly across exact newline boundaries with continuation metadata.

    Guarantees:
    - Never character-truncates (code[:N]).
    - Splits strictly on full line boundaries.
    - Preserves 100% of original lines (lines1 + lines2 == lines).
    - Sets appropriate continuation caption on the second block.
    """
    code = block.code or ""
    lines = code.split("\n")
    if len(lines) <= 1:
        return block, CodeBlock(code="", language=block.language)

    header_h = 7.4 if (block.filename or block.language) else 0.0
    caption_h = 7.0 if block.caption else 0.0
    overhead = header_h + caption_h + 7.4 + 4.23  # padding + margin

    rem_h = max(0.0, available_height_mm - overhead)
    accum_h = 0.0
    split_idx = 0
    for idx, l in enumerate(lines):
        wrapped = max(1, math.ceil(len(l) / 70.0))
        l_h = wrapped * 5.13
        if accum_h + l_h <= rem_h or split_idx == 0:
            accum_h += l_h
            split_idx = idx + 1
        else:
            break

    split_idx = min(max(1, split_idx), len(lines) - 1)

    lines1 = lines[:split_idx]
    lines2 = lines[split_idx:]

    b1 = CodeBlock(
        code="\n".join(lines1),
        language=block.language,
        filename=block.filename,
        caption=block.caption,
        line_numbers=block.line_numbers,
    )

    cont_caption = f"{block.caption} (Cont.)" if block.caption else (f"{block.filename} (Cont.)" if block.filename else "Code (Cont.)")
    b2 = CodeBlock(
        code="\n".join(lines2),
        language=block.language,
        filename=block.filename,
        caption=cont_caption,
        line_numbers=block.line_numbers,
    )
    return b1, b2


def split_terminal_block(block: TerminalBlock, available_height_mm: float) -> Tuple[TerminalBlock, TerminalBlock]:
    """Split a TerminalBlock cleanly across full line boundaries with continuation metadata."""
    lines = block.lines or []
    if len(lines) <= 1:
        return block, TerminalBlock(title=f"{block.title or 'Terminal'} (Cont.)", lines=[], shell=block.shell)

    overhead = 7.4 + 7.4 + 4.23  # header + padding + margin = 19.03mm
    rem_h = max(0.0, available_height_mm - overhead)

    accum_h = 0.0
    split_idx = 0
    for idx, l in enumerate(lines):
        txt = getattr(l, "text", str(l)) or ""
        wrapped = max(1, math.ceil(len(txt) / 72.0))
        l_h = wrapped * 6.14
        if accum_h + l_h <= rem_h or split_idx == 0:
            accum_h += l_h
            split_idx = idx + 1
        else:
            break

    split_idx = min(max(1, split_idx), len(lines) - 1)
    lines1 = lines[:split_idx]
    lines2 = lines[split_idx:]

    b1 = TerminalBlock(title=block.title, lines=lines1, shell=block.shell)
    b2_title = f"{block.title or 'Terminal'} (Cont.)" if block.title else "Terminal Session (Cont.)"
    b2 = TerminalBlock(title=b2_title, lines=lines2, shell=block.shell)
    return b1, b2


# =========================================================================
# CANONICAL REUSABLE PAGE PAGINATOR API
# =========================================================================

class PagePaginator:
    """Canonical printable-page safe-area paginator and layout coordinator."""

    def __init__(self, geometry_spec: Optional[PageGeometrySpec] = None, debug: bool = False):
        self.geometry = geometry_spec or PageGeometrySpec()
        self.debug = debug

    def content_top(self) -> float:
        """Top edge of the content-safe area in mm from page top."""
        return self.geometry.content_top_mm

    def content_bottom(self) -> float:
        """Absolute lower boundary of content-safe area in mm from page top."""
        return self.geometry.content_bottom_mm

    def available_content_height(self) -> float:
        """Net usable vertical content height in mm."""
        return self.geometry.available_content_height_mm

    def remaining_height(self, current_y_mm: float) -> float:
        """Calculate remaining usable content height before reaching the bottom safety gap."""
        return max(0.0, self.content_bottom() - current_y_mm)

    def can_fit(self, block: Any, current_y_mm: float, has_preceding_block: bool = True) -> bool:
        """Check if a block fits completely within the content-safe area without touching the footer."""
        gap = self.geometry.block_gap_mm if has_preceding_block else 0.0
        required_h = DensityEstimator.estimate_block_height_mm(block) + gap
        return (current_y_mm + required_h) <= (self.content_bottom() + self.geometry.safe_bottom_epsilon_mm)

    def is_oversized(self, block: Any) -> bool:
        """Check if a block's height exceeds the entire available page content height."""
        return DensityEstimator.estimate_block_height_mm(block) > self.available_content_height()

    def split_block(self, block: Any, available_height_mm: float) -> Tuple[Any, Any]:
        """Split a tall/oversized block into two pieces based on its component archetype."""
        if isinstance(block, CodeBlock) or getattr(block, "type", "") == "code":
            return split_code_block(block, available_height_mm)
        elif isinstance(block, TerminalBlock) or getattr(block, "type", "") == "terminal":
            return split_terminal_block(block, available_height_mm)
        elif isinstance(block, TableBlock) or getattr(block, "type", "") == "table":
            row_h = 10.5
            fit_rows = max(1, int((available_height_mm - 20.0) // row_h))
            return split_table_block(block, fit_rows)
        elif isinstance(block, ChecklistBlock) or getattr(block, "type", "") == "checklist":
            fit_items = max(1, int((available_height_mm - 16.0) // 7.3))
            return split_checklist_block(block, fit_items)
        elif isinstance(block, StepBlock) or getattr(block, "type", "") == "step":
            fit_steps = max(1, int((available_height_mm - 16.0) // 16.0))
            return split_step_block(block, fit_steps)
        elif isinstance(block, ComparisonBlock) or getattr(block, "type", "") == "comparison":
            fit_items = max(1, int((available_height_mm - 24.0) // 8.0))
            return split_comparison_block(block, fit_items)
        elif isinstance(block, TextBlock) or getattr(block, "type", "") == "text":
            return split_text_block(block, available_height_mm)
        return block, None


# =========================================================================
# DYNAMIC PAGE SPLITTING AND CONTINUATION CREATION
# =========================================================================

def find_safe_page_split(
    page: Page,
    max_height_mm: float = AVAILABLE_CONTENT_HEIGHT_MM,
    target_ratio: float = 0.95,
) -> Tuple[PageContent, PageContent]:
    """Evaluate cumulative component heights and partition page content into safe fit and overflow portions."""
    safe_limit_mm = max_height_mm * target_ratio
    clean_hl = (page.content.headline or page.chapter_name or "Section")
    clean_hl = re.sub(r"\s*\(Cont\.?\s*\d*\)", "", clean_hl).strip()

    # 1. Handle Structured Blocks
    if page.content and page.content.blocks:
        headline_h = 0.0
        if page.content.headline:
            hl_lines = max(1, math.ceil(len(page.content.headline) / 50.0))
            headline_h = (hl_lines * 8.0) + 4.23

        total_block_h = headline_h
        for idx, b in enumerate(page.content.blocks):
            if idx > 0 or headline_h > 0:
                total_block_h += BLOCK_GAP_MM
            total_block_h += DensityEstimator.estimate_block_height_mm(b)

        if total_block_h <= safe_limit_mm:
            return page.content, PageContent()

        current_h = headline_h
        fit_blocks: List[ContentBlock] = []
        overflow_blocks: List[ContentBlock] = []
        has_overflowed = False

        for idx, block in enumerate(page.content.blocks):
            if has_overflowed:
                overflow_blocks.append(block)
                continue

            b_h = DensityEstimator.estimate_block_height_mm(block)
            gap = BLOCK_GAP_MM if (idx > 0 or headline_h > 0) else 0.0

            if current_h + gap + b_h <= safe_limit_mm:
                fit_blocks.append(block)
                current_h += gap + b_h
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"[PAGINATOR] Page {page.page_number}: contentTop={CONTENT_TOP_MM:.1f}mm, "
                        f"contentBottom={CONTENT_BOTTOM_MM:.1f}mm, currentY={current_h:.1f}mm, "
                        f"block={getattr(block, 'type', 'block')}, measuredHeight={b_h:.1f}mm, "
                        f"remainingHeight={(safe_limit_mm - current_h):.1f}mm, action=PLACE_BLOCK"
                    )
            else:
                rem_space = max(0.0, safe_limit_mm - current_h - gap)
                sub_split_success = False

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"[PAGINATOR] Page {page.page_number}: contentTop={CONTENT_TOP_MM:.1f}mm, "
                        f"contentBottom={CONTENT_BOTTOM_MM:.1f}mm, currentY={current_h:.1f}mm, "
                        f"block={getattr(block, 'type', 'block')}, measuredHeight={b_h:.1f}mm, "
                        f"remainingHeight={rem_space:.1f}mm, action=SPLIT_OR_MOVE"
                    )

                # Attempt sub-splitting for multi-item components
                if isinstance(block, TableBlock) and len(block.rows) >= 3 and rem_space >= 32.0:
                    t1, t2 = split_table_block(block, rem_space)
                    if t1.rows and t2.rows:
                        fit_blocks.append(t1)
                        overflow_blocks.append(t2)
                        has_overflowed = True
                        sub_split_success = True

                elif isinstance(block, TerminalBlock) and len(getattr(block, "lines", []) or []) >= 4 and rem_space >= 30.0:
                    t1, t2 = split_terminal_block(block, rem_space)
                    if t1.lines and t2.lines:
                        fit_blocks.append(t1)
                        overflow_blocks.append(t2)
                        has_overflowed = True
                        sub_split_success = True

                elif isinstance(block, ChecklistBlock) and len(block.items) >= 3 and rem_space >= 22.0:
                    c1, c2 = split_checklist_block(block, rem_space)
                    if c1.items and c2.items:
                        fit_blocks.append(c1)
                        overflow_blocks.append(c2)
                        has_overflowed = True
                        sub_split_success = True

                elif isinstance(block, StepBlock) and len(block.steps) >= 3 and rem_space >= 32.0:
                    s1, s2 = split_step_block(block, rem_space)
                    if s1.steps and s2.steps:
                        fit_blocks.append(s1)
                        overflow_blocks.append(s2)
                        has_overflowed = True
                        sub_split_success = True

                elif isinstance(block, TextBlock) and (len(getattr(block, "paragraphs", []) or []) > 1 or "\n\n" in block.text) and rem_space >= 22.0:
                    txt1, txt2 = split_text_block(block, rem_space)
                    if txt1.text and txt2.text:
                        fit_blocks.append(txt1)
                        overflow_blocks.append(txt2)
                        has_overflowed = True
                        sub_split_success = True

                elif isinstance(block, CodeBlock) and len(block.code.split("\n")) >= 6 and rem_space >= 30.0:
                    c1, c2 = split_code_block(block, rem_space)
                    if c1.code and c2.code:
                        fit_blocks.append(c1)
                        overflow_blocks.append(c2)
                        has_overflowed = True
                        sub_split_success = True

                if not sub_split_success:
                    if not fit_blocks:
                        # Even the first block alone exceeds budget: force sub-split or keep first block
                        if isinstance(block, TableBlock) and len(block.rows) >= 2:
                            t1, t2 = split_table_block(block, safe_limit_mm)
                            fit_blocks.append(t1)
                            if t2.rows:
                                overflow_blocks.append(t2)
                        elif isinstance(block, TerminalBlock) and len(getattr(block, "lines", []) or []) >= 2:
                            t1, t2 = split_terminal_block(block, safe_limit_mm)
                            fit_blocks.append(t1)
                            if t2.lines:
                                overflow_blocks.append(t2)
                        elif isinstance(block, ChecklistBlock) and len(block.items) >= 2:
                            c1, c2 = split_checklist_block(block, safe_limit_mm)
                            fit_blocks.append(c1)
                            if c2.items:
                                overflow_blocks.append(c2)
                        elif isinstance(block, StepBlock) and len(block.steps) >= 2:
                            s1, s2 = split_step_block(block, safe_limit_mm)
                            fit_blocks.append(s1)
                            if s2.steps:
                                overflow_blocks.append(s2)
                        elif isinstance(block, TextBlock):
                            txt1, txt2 = split_text_block(block, safe_limit_mm)
                            fit_blocks.append(txt1)
                            if txt2.text:
                                overflow_blocks.append(txt2)
                        elif isinstance(block, CodeBlock) and len(block.code.split("\n")) >= 4:
                            c1, c2 = split_code_block(block, safe_limit_mm)
                            fit_blocks.append(c1)
                            if c2.code:
                                overflow_blocks.append(c2)
                        else:
                            fit_blocks.append(block)
                    else:
                        overflow_blocks.append(block)
        # Orphan Heading Prevention: Never leave a heading alone at the bottom of a page
        if fit_blocks and isinstance(fit_blocks[-1], HeadingBlock) and overflow_blocks:
            orphaned_heading = fit_blocks.pop()
            overflow_blocks.insert(0, orphaned_heading)

        fit_content = PageContent(
            headline=page.content.headline,
            blocks=fit_blocks,
        )
        overflow_content = PageContent(
            headline=f"{clean_hl} (Cont.)",
            blocks=overflow_blocks,
        )
        return fit_content, overflow_content

    # 2. Fallback Prose Body
    body = page.content.body or ""
    part1, part2 = ContentSplitter.split_body_text(body, max_chars=1800)

    fit_content = PageContent(
        headline=page.content.headline,
        body=part1,
    )
    overflow_content = PageContent(
        headline=f"{clean_hl} (Cont.)",
        body=part2,
        key_points=page.content.key_points,
    )
    return fit_content, overflow_content


def create_continuation_page(
    source_page: Page,
    overflow_content: PageContent,
    continuation_index: int = 1,
) -> Page:
    """Create a new physical continuation Page inheriting chapter metadata, theme, and style."""
    clean_hl = (source_page.content.headline or source_page.chapter_name or "Section")
    clean_hl = re.sub(r"\s*\(Cont\.?\s*\d*\)", "", clean_hl).strip()

    if continuation_index > 1:
        headline = f"{clean_hl} (Cont. {continuation_index})"
    else:
        headline = f"{clean_hl} (Cont.)"

    overflow_content.headline = headline
    style_copy = source_page.style.model_copy() if source_page.style else PageStyle()

    continuation_page = Page(
        id=generate_id(),
        book_id=source_page.book_id,
        page_number=source_page.page_number + 1,
        page_type=source_page.page_type if source_page.page_type not in ("cover", "chapter_opener", "toc") else "chapter_content",
        chapter_number=source_page.chapter_number,
        chapter_name=source_page.chapter_name,
        theme=source_page.theme,
        layout=source_page.layout if source_page.layout not in ("cover", "chapter_opener", "toc") else LayoutType.EDITORIAL.value,
        content=overflow_content,
        style=style_copy,
        sources=list(source_page.sources),
        validation={
            "repaired_overflow": True,
            "is_continuation": True,
            "continuation_index": continuation_index,
            "parent_page_id": source_page.id,
        },
        previous_page_id=source_page.id,
        next_page_id=source_page.next_page_id,
    )
    return continuation_page


def regenerate_toc_pages(pages: List[Page], book_plan: Optional[Any] = None) -> List[Page]:
    """Dynamically resolve and update Table of Contents physical starting page numbers."""
    chapter_start_pages: dict[int, int] = {}
    for p in pages:
        p_type = getattr(p, "page_type", "") or p.layout
        if (p_type == LayoutType.CHAPTER_OPENER.value or p.layout == LayoutType.CHAPTER_OPENER.value) and p.chapter_number is not None:
            if p.chapter_number not in chapter_start_pages:
                chapter_start_pages[p.chapter_number] = p.page_number
        elif p.chapter_number is not None and p.chapter_number not in chapter_start_pages:
            chapter_start_pages[p.chapter_number] = p.page_number

    for p in pages:
        p_type = getattr(p, "page_type", "") or p.layout
        if p_type == LayoutType.TOC.value or p.layout == LayoutType.TOC.value:
            if p.content and p.content.blocks:
                for b in p.content.blocks:
                    if isinstance(b, TocBlock) or getattr(b, "type", "") == "toc":
                        entries = getattr(b, "entries", [])
                        for entry in entries:
                            ch_num = getattr(entry, "chapter_number", None)
                            if ch_num in chapter_start_pages:
                                entry.page_number = chapter_start_pages[ch_num]
            elif p.content and getattr(p.content, "key_points", None):
                updated_kp = []
                for kp in p.content.key_points:
                    m = re.match(r"(Chapter\s+(\d+):.*?)\s*\.{3,}\s*(\d+)", kp, re.IGNORECASE)
                    if m:
                        ch_prefix = m.group(1)
                        ch_num = int(m.group(2))
                        if ch_num in chapter_start_pages:
                            resolved_pnum = chapter_start_pages[ch_num]
                            updated_kp.append(f"{ch_prefix} ....... {resolved_pnum}")
                        else:
                            updated_kp.append(kp)
                    else:
                        updated_kp.append(kp)
                p.content.key_points = updated_kp
    return pages


class PageRepairEngine:
    """Dynamic page insertion and pagination engine for physical A4 layout constraints."""

    def __init__(self, detector: Optional[OverflowDetector] = None, splitter: Optional[ContentSplitter] = None):
        self.detector = detector or OverflowDetector()
        self.splitter = splitter or ContentSplitter()

    def repair_pages(self, pages: List[Page]) -> List[Page]:
        """Inspect all pages in a book, dynamically inserting physical continuation pages when content overflows."""
        repaired_pages: List[Page] = []
        pages_inserted_count = 0

        for page in pages:
            # Dedicated full-page structural layouts are not split
            p_type = getattr(page, "page_type", "") or page.layout
            if p_type in ("cover", "chapter_opener", "copyright", "thank_you", "toc", "acknowledgement", "imprint"):
                repaired_pages.append(page)
                continue

            # Check if this page overflows safe physical bounds
            if not self.detector.is_overflowing(page):
                repaired_pages.append(page.model_copy(deep=True))
                continue

            # Dynamic pagination loop: split page recursively/iteratively until all fragments fit
            curr_page = page.model_copy(deep=True)
            continuation_idx = 1

            while self.detector.is_overflowing(curr_page):
                fit_content, overflow_content = find_safe_page_split(curr_page)

                has_overflow = bool(overflow_content.blocks or (overflow_content.body and overflow_content.body.strip()))
                if not has_overflow:
                    break

                curr_page.content = fit_content
                curr_page.validation["repaired_overflow"] = True
                curr_page.html = ""
                repaired_pages.append(curr_page)
                pages_inserted_count += 1

                logger.info(
                    f"[PAGINATION] Page {curr_page.page_number} ('{curr_page.content.headline}') exceeded safe A4 height -> "
                    f"split at semantic boundary and created continuation physical page."
                )

                continuation_page = create_continuation_page(
                    source_page=curr_page,
                    overflow_content=overflow_content,
                    continuation_index=continuation_idx,
                )
                continuation_idx += 1
                curr_page = continuation_page

            repaired_pages.append(curr_page)

        # Re-number and re-link all physical pages sequentially
        for i, p in enumerate(repaired_pages):
            p.page_number = i + 1
            p.previous_page_id = repaired_pages[i - 1].id if i > 0 else None
            p.next_page_id = repaired_pages[i + 1].id if i < len(repaired_pages) - 1 else None

        if pages_inserted_count > 0:
            logger.info(
                f"[PAGINATION SUMMARY] Dynamic pagination completed: {len(repaired_pages)} physical pages "
                f"(original: {len(pages)}, inserted: {pages_inserted_count})"
            )

        return repaired_pages


# DynamicPaginator alias
DynamicPaginator = PageRepairEngine


def calculate_semantic_completeness(
    page: Any,
    publication_profile: Optional[PublicationProfile] = None,
    topic: Optional[str] = None,
) -> PageCompletenessScore:
    """Evaluate semantic information density, practical depth, and penalize repetitive filler/genre leakage."""
    content = getattr(page, "content", page)
    blocks = getattr(content, "blocks", []) if content else []
    headline = (getattr(content, "headline", "") or "").lower()

    # Extract all text from page
    texts: List[str] = []
    if getattr(content, "body", None):
        texts.append(content.body)
    for b in blocks:
        for attr in ("text", "content", "explanation", "quote", "caption", "title"):
            val = getattr(b, attr, None)
            if val and isinstance(val, str):
                texts.append(val)
        if getattr(b, "items", None):
            texts.extend([str(item) for item in b.items])
        if getattr(b, "instructions", None):
            texts.extend([str(inst) for inst in b.instructions])

    full_text = " ".join(texts).lower()
    total_words = len(full_text.split())

    issues: List[str] = []
    filler_penalty = 0.0
    repetition_penalty = 0.0
    genre_mismatch_penalty = 0.0

    # 1. Generic filler detection
    filler_patterns = [
        r"\bit is important to understand\b",
        r"\bthis concept plays an important role\b",
        r"\bin today's fast-paced world\b",
        r"\bby following these principles\b",
        r"\bunderstanding this topic is crucial\b",
        r"\bas we have discussed\b",
        r"\bthis can help you achieve your goals\b",
        r"\bit is worth noting that\b",
        r"\bat the end of the day\b",
        r"\bin conclusion, it is vital\b",
        r"\bplays a vital role\b",
        r"\bcrucial aspect of\b",
    ]
    for pattern in filler_patterns:
        matches = len(re.findall(pattern, full_text))
        if matches > 0:
            penalty = matches * 0.25
            filler_penalty += penalty
            issues.append(f"Generic filler detected ({pattern}): {matches} occurrence(s)")

    # 2. Repetition detection (repeated sentences or duplicated chunks)
    sentences = [s.strip() for s in re.split(r"[.!?]+", full_text) if len(s.strip()) > 15]
    if len(sentences) > len(set(sentences)):
        duplicates = len(sentences) - len(set(sentences))
        rep_pen = min(0.60, duplicates * 0.20)
        repetition_penalty += rep_pen
        issues.append(f"Repetitive text detected: {duplicates} duplicate sentence(s)")

    # 3. Genre mismatch detection
    profile = getattr(page, "publication_profile", publication_profile) or publication_profile
    if profile == PublicationProfile.GENERAL_NONFICTION or (profile is None and topic and not any(t in topic.lower() for t in ["code", "python", "rust", "go", "software", "database", "programming"])):
        tech_leaks = [
            r"\bmaintainable, and robust against unexpected inputs\b",
            r"\bkeep your implementations modular\b",
            r"\bvalidate boundary conditions\b",
            r"\bisolated inputs\b",
            r"\bcode idioms\b",
            r"\bunit test\b",
            r"\bapi endpoint\b",
        ]
        for pattern in tech_leaks:
            if re.search(pattern, full_text):
                genre_mismatch_penalty += 0.35
                issues.append(f"Technical template leakage detected in general non-fiction: {pattern}")

    # 4. Component diversity and practical depth score
    block_types = {getattr(b, "type", "") for b in blocks if getattr(b, "type", "")}
    diversity_score = min(1.0, len(block_types) / 3.0) if block_types else (0.5 if total_words > 200 else 0.3)
    explanation_depth = min(1.0, total_words / 250.0) if total_words >= 150 else 0.4
    practical_value = 1.0 if any(t in block_types for t in ["checklist", "exercise", "callout", "comparison", "code", "terminal"]) else 0.5
    example_quality = 1.0 if any(t in block_types for t in ["callout", "comparison", "code", "timeline"]) or "example" in full_text else 0.5

    base_score = 0.3 * explanation_depth + 0.3 * practical_value + 0.2 * example_quality + 0.2 * diversity_score
    final_score = max(0.0, min(1.0, base_score - filler_penalty - repetition_penalty - genre_mismatch_penalty))
    passes = (final_score >= 0.70) and (filler_penalty <= 0.30) and (repetition_penalty <= 0.30) and (genre_mismatch_penalty == 0.0)

    return PageCompletenessScore(
        score=round(final_score, 2),
        core_topic_coverage=round(explanation_depth, 2),
        explanation_depth=round(explanation_depth, 2),
        example_quality=round(example_quality, 2),
        practical_value=round(practical_value, 2),
        component_diversity=round(diversity_score, 2),
        novelty=1.0 - round(min(1.0, repetition_penalty), 2),
        evidence_quality=0.9,
        filler_penalty=round(filler_penalty, 2),
        repetition_penalty=round(repetition_penalty, 2),
        genre_mismatch_penalty=round(genre_mismatch_penalty, 2),
        passes_threshold=passes,
        detected_issues=issues,
    )
