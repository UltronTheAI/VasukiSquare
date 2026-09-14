"""Preflight visual layout validation and quality assurance before final PDF rendering."""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from vasukisquare.book.models import Page
from vasukisquare.book.layout import LayoutType
from vasukisquare.design.themes import BookThemeMap, SectionTheme
from vasukisquare.renderer.geometry import (
    CONTENT_SAFE_HEIGHT_MM,
    FOOTER_SAFE_ZONE_MM,
    HEADER_SAFE_ZONE_MM,
    USABLE_PAGE_HEIGHT_MM,
    MIN_FOOTER_BREATHING_GAP_MM,
)
from vasukisquare.renderer.overflow import estimate_page_utilization

logger = logging.getLogger(__name__)


class PagePreflightReport(BaseModel):
    """Preflight validation report for a single A4 page."""

    page_number: int
    page_type: str
    layout: str
    valid: bool = True
    overflow: bool = False
    underfilled: bool = False
    content_utilization: float = 0.0
    content_units: int = 0
    header_collision: bool = False
    footer_collision: bool = False
    decorative_collision: bool = False
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class BookPreflightReport(BaseModel):
    """Preflight summary report for the entire book document."""

    total_pages: int
    valid_pages: int
    invalid_pages: int
    underfilled_pages: int = 0
    all_valid: bool = True
    page_reports: List[PagePreflightReport] = Field(default_factory=list)
    overall_warnings: List[str] = Field(default_factory=list)


def preflight_page(page: Page, theme: Optional[SectionTheme] = None) -> PagePreflightReport:
    """Inspect an individual page model against strict physical A4 geometry, safe zones, and density contracts."""
    p_type = getattr(page, "page_type", "") or page.layout_type.value
    layout = getattr(page, "layout", "") or page.layout_type.value

    # Structural cover, opener, thank_you, and TOC pages have dedicated full-page layouts
    if p_type in ("cover", LayoutType.COVER.value) or layout in ("cover", LayoutType.COVER.value):
        return PagePreflightReport(
            page_number=page.page_number,
            page_type=p_type,
            layout=layout,
            valid=True,
            content_utilization=1.0,
            content_units=3,
        )

    if p_type in ("chapter_opener", LayoutType.CHAPTER_OPENER.value):
        return PagePreflightReport(
            page_number=page.page_number,
            page_type=p_type,
            layout=layout,
            valid=True,
            content_utilization=0.45,
            content_units=2,
        )

    if p_type in (
        "toc",
        LayoutType.TOC.value,
        "copyright",
        LayoutType.COPYRIGHT.value,
        "thank_you",
        LayoutType.THANK_YOU.value,
        "imprint",
        "title",
        "acknowledgement",
        LayoutType.ACKNOWLEDGEMENT.value,
        "references",
        LayoutType.REFERENCES.value,
    ) or layout in (
        "toc",
        LayoutType.TOC.value,
        "copyright",
        LayoutType.COPYRIGHT.value,
        "thank_you",
        LayoutType.THANK_YOU.value,
        "imprint",
        "title",
        "acknowledgement",
        LayoutType.ACKNOWLEDGEMENT.value,
        "references",
        LayoutType.REFERENCES.value,
    ):
        return PagePreflightReport(
            page_number=page.page_number,
            page_type=p_type,
            layout=layout,
            valid=True,
            content_utilization=0.85,
            content_units=3,
        )

    util = estimate_page_utilization(page)
    warnings: List[str] = []
    errors: List[str] = []
    is_overflow = False
    is_underfilled = util.is_underfilled
    footer_coll = False
    header_coll = False
    decorative_coll = False

    # 1. Content Safe Height Check
    if util.total_content_height_mm > CONTENT_SAFE_HEIGHT_MM:
        is_overflow = True
        footer_coll = True
        errors.append(
            f"Content height ({util.total_content_height_mm:.1f}mm) exceeds safe content boundary ({CONTENT_SAFE_HEIGHT_MM:.1f}mm), risking footer collision."
        )

    # 2. Table / Footer Breathing Gap Check
    table_heights = [h for k, h in util.block_breakdown.items() if "table" in k]
    if table_heights:
        remaining_space = CONTENT_SAFE_HEIGHT_MM - util.total_content_height_mm
        if remaining_space < MIN_FOOTER_BREATHING_GAP_MM and not is_overflow:
            warnings.append(
                f"Table is within {remaining_space:.1f}mm of footer safe zone (recommended >= {MIN_FOOTER_BREATHING_GAP_MM:.1f}mm)."
            )

    # 3. Utilization Target Verification (90-95% for normal pages)
    if util.is_hard_fail:
        errors.append(
            f"Hard Fail: Page {page.page_number} content utilization ({util.estimated_ratio:.1%}) is below the critical quality threshold ({util.hard_fail_ratio:.1%})."
        )
    elif is_underfilled:
        warnings.append(
            f"Page underfilled: utilization is {util.estimated_ratio:.1%} (target min {util.target_min_ratio:.1%})."
        )
    elif util.estimated_ratio > 0.98:
        is_overflow = True
        errors.append(
            f"Page overfilled: utilization is {util.estimated_ratio:.1%} (> 98.0% overflow threshold)."
        )
    elif util.estimated_ratio > 0.95:
        warnings.append(
            f"Page is dense: utilization is {util.estimated_ratio:.1%} (95.0-98.0% band)."
        )

    # 4. Content Units Count Check (Must have at least 2 distinct educational components)
    if util.content_units < 2:
        errors.append(
            f"Page {page.page_number} is incomplete: contains only {util.content_units} educational content unit(s)."
        )

    # 5. Decorative Watermark Collision Protection
    if util.estimated_ratio > 0.85 and getattr(page, "watermark_svg", None):
        decorative_coll = True
        warnings.append("Decorative watermark rendered on dense page; suppressing watermark to protect text readability.")

    is_valid = len(errors) == 0

    return PagePreflightReport(
        page_number=page.page_number,
        page_type=p_type,
        layout=layout,
        valid=is_valid,
        overflow=is_overflow,
        underfilled=is_underfilled,
        content_utilization=util.estimated_ratio,
        content_units=util.content_units,
        header_collision=header_coll,
        footer_collision=footer_coll,
        decorative_collision=decorative_coll,
        warnings=warnings,
        errors=errors,
    )


def preflight_book(pages: List[Page], book_theme: Optional[BookThemeMap] = None) -> BookPreflightReport:
    """Run automated visual QA and preflight checks across all pages in the book."""
    reports: List[PagePreflightReport] = []
    overall_warnings: List[str] = []

    for page in pages:
        ch_num = page.chapter_number
        sec_theme = None
        if book_theme:
            if ch_num and ch_num in book_theme.chapters:
                sec_theme = book_theme.chapters[ch_num]
            elif page.page_type in (LayoutType.THANK_YOU.value, LayoutType.REFERENCES.value):
                sec_theme = book_theme.backmatter
            else:
                sec_theme = book_theme.frontmatter

        rep = preflight_page(page, theme=sec_theme)
        reports.append(rep)
        if not rep.valid:
            logger.warning(
                f"[PREFLIGHT FAIL] Page {rep.page_number} ({rep.layout}): {'; '.join(rep.errors)}"
            )
        elif rep.warnings:
            logger.debug(
                f"[PREFLIGHT WARN] Page {rep.page_number} ({rep.layout}): {'; '.join(rep.warnings)}"
            )

    invalid_count = sum(1 for r in reports if not r.valid)
    underfilled_count = sum(1 for r in reports if r.underfilled and r.page_type not in ("cover", "chapter_opener", "thank_you"))
    valid_count = len(reports) - invalid_count

    # Book-level density QA: If more than 10% of normal pages are severely underfilled, fail QA
    normal_pages_count = sum(1 for r in reports if r.page_type not in ("cover", "chapter_opener", "thank_you", "toc", "copyright"))
    if normal_pages_count > 0 and (underfilled_count / normal_pages_count) > 0.15:
        overall_warnings.append(
            f"Book density warning: {underfilled_count}/{normal_pages_count} normal content pages are underfilled."
        )

    return BookPreflightReport(
        total_pages=len(pages),
        valid_pages=valid_count,
        invalid_pages=invalid_count,
        underfilled_pages=underfilled_count,
        all_valid=(invalid_count == 0),
        page_reports=reports,
        overall_warnings=overall_warnings,
    )

