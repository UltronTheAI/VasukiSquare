"""Overflow detection, density estimation, and controlled page repair for physical A4 layout constraints."""

import re
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field
from vasukisquare.book.layout import LayoutType, PublicationProfile
from vasukisquare.book.models import (
    Page,
    PageContent,
    PageCompletenessScore,
    generate_id,
)
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

from vasukisquare.renderer.geometry import (
    CONTENT_SAFE_HEIGHT_MM,
    USABLE_PAGE_HEIGHT_MM as GEOMETRY_USABLE_HEIGHT_MM,
)

# Maximum content thresholds for an individual A4 page with safe padding
MAX_PAGE_CHARACTERS = 2800
MAX_CODE_LINES = 38
MAX_BODY_PARAGRAPHS = 6
USABLE_PAGE_HEIGHT_MM = CONTENT_SAFE_HEIGHT_MM  # 215.0mm (usable content region excluding header/footer chrome)


class PageUtilization(BaseModel):
    """Accurate physical A4 vertical layout utilization and educational density metrics."""

    estimated_ratio: float = Field(description="Estimated content height fraction of usable A4 height (0.0 to 1.0+)")
    status: str = Field(description="Utilization status: hard_failure, severely_underfilled, underfilled, enrich_if_safe, healthy, dense, or overflow_risk")
    density_band: str = Field(default="healthy", description="Density band: HARD_FAILURE, SEVERELY_UNDERFILLED, UNDERFILLED, ENRICH_IF_SAFE, HEALTHY, DENSE, OVERFLOW_RISK")
    block_breakdown: Dict[str, float] = Field(default_factory=dict, description="Estimated height in mm per component")
    usable_height_mm: float = Field(default=USABLE_PAGE_HEIGHT_MM)
    total_content_height_mm: float = Field(default=0.0)
    target_min_ratio: float = Field(default=0.90)
    target_max_ratio: float = Field(default=0.95)
    hard_fail_ratio: float = Field(default=0.60)
    content_units: int = Field(default=0, description="Count of meaningful educational content units")
    is_underfilled: bool = Field(default=False, description="True if utilization is below the minimum threshold")
    is_hard_fail: bool = Field(default=False, description="True if content density is severely deficient (< 0.60 for normal pages)")
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
        return self.estimated_ratio > 0.98


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
                usable_height_mm=USABLE_PAGE_HEIGHT_MM,
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
                block_breakdown={"chapter_opener_banner": 124.5},
                usable_height_mm=USABLE_PAGE_HEIGHT_MM,
                total_content_height_mm=124.5,
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
                block_breakdown={"structural_layout": 219.0},
                usable_height_mm=USABLE_PAGE_HEIGHT_MM,
                total_content_height_mm=219.0,
                target_min_ratio=0.65,
                target_max_ratio=0.95,
                hard_fail_ratio=0.45,
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

        # Target minimum ratios based on specific content archetype:
        # DIAGRAM / VISUAL PAGE: target 0.80–0.95
        # CODE / TERMINAL HEAVY: target 0.85–0.95
        # COMPARISON / FRAMEWORK: target 0.85–0.95
        # EXERCISE / PRACTICE: target 0.80–0.95
        # NORMAL CONTENT PAGE: target 0.90–0.95
        has_code = any("code" in k or "terminal" in k for k in breakdown.keys())
        has_diagram = any("diagram" in k or "chart" in k for k in breakdown.keys())
        has_comparison = any("comparison" in k or "table" in k for k in breakdown.keys())
        has_exercise = any("exercise" in k for k in breakdown.keys())

        if has_diagram:
            min_target = 0.80
        elif has_exercise:
            min_target = 0.80
        elif has_code or has_comparison:
            min_target = 0.85
        else:
            min_target = 0.90

        # Categorize density bands:
        # < 0.60: HARD FAILURE
        # 0.60–0.75: SEVERELY UNDERFILLED
        # 0.75–0.85: UNDERFILLED
        # 0.85–0.90: ENRICH IF SAFE
        # 0.90–0.95: HEALTHY
        # 0.95–0.98: DENSE
        # > 0.98: OVERFLOW RISK
        if ratio < 0.60:
            density_band = "HARD_FAILURE"
            status = "hard_failure"
            is_underfilled = True
            is_hard_fail = True
        elif ratio < 0.75:
            density_band = "SEVERELY_UNDERFILLED"
            status = "severely_underfilled"
            is_underfilled = True
            is_hard_fail = False
        elif ratio < 0.85:
            density_band = "UNDERFILLED"
            status = "underfilled"
            is_underfilled = True
            is_hard_fail = False
        elif ratio < min_target:
            density_band = "ENRICH_IF_SAFE"
            status = "enrich_if_safe"
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
            usable_height_mm=USABLE_PAGE_HEIGHT_MM,
            total_content_height_mm=round(total_height_mm, 1),
            target_min_ratio=min_target,
            target_max_ratio=0.95,
            hard_fail_ratio=0.60,
            content_units=content_units_count,
            is_underfilled=is_underfilled,
            is_hard_fail=is_hard_fail,
            publication_profile=profile,
        )


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

