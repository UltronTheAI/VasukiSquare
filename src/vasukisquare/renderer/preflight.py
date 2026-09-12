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
    content_utilization: float = 0.0
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
    all_valid: bool
    page_reports: List[PagePreflightReport] = Field(default_factory=list)
    overall_warnings: List[str] = Field(default_factory=list)


def preflight_page(page: Page, theme: Optional[SectionTheme] = None) -> PagePreflightReport:
    """Inspect an individual page model against strict physical A4 geometry, safe zones, and collision contracts."""
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
        )

    if p_type in ("chapter_opener", LayoutType.CHAPTER_OPENER.value):
        return PagePreflightReport(
            page_number=page.page_number,
            page_type=p_type,
            layout=layout,
            valid=True,
            content_utilization=0.45,
        )

    util = estimate_page_utilization(page)
    warnings: List[str] = []
    errors: List[str] = []
    is_overflow = False
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

    # 3. Utilization Target Verification (70-90% for normal pages)
    if util.estimated_ratio < util.target_min_ratio:
        warnings.append(
            f"Page underfilled: utilization is {util.estimated_ratio:.1%} (target min {util.target_min_ratio:.1%})."
        )
    elif util.estimated_ratio > 0.95:
        is_overflow = True
        errors.append(
            f"Page overfilled: utilization is {util.estimated_ratio:.1%} (> 95% threshold)."
        )

    # 4. Decorative Watermark Collision Protection
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
        content_utilization=util.estimated_ratio,
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
    valid_count = len(reports) - invalid_count

    return BookPreflightReport(
        total_pages=len(pages),
        valid_pages=valid_count,
        invalid_pages=invalid_count,
        all_valid=(invalid_count == 0),
        page_reports=reports,
        overall_warnings=overall_warnings,
    )

