"""Renderer domain: HTML template generation, cover design, overflow repair, and Playwright PDF export."""

from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.renderer.pdf import PdfRenderer
from vasukisquare.renderer.overflow import (
    OverflowDetector,
    ContentSplitter,
    PageRepairEngine,
    DynamicPaginator,
    PagePaginator,
    find_safe_page_split,
    create_continuation_page,
    regenerate_toc_pages,
)
from vasukisquare.renderer.cover import CoverRenderer, CoverService

__all__ = [
    "HtmlPageRenderer",
    "PdfRenderer",
    "OverflowDetector",
    "ContentSplitter",
    "PageRepairEngine",
    "DynamicPaginator",
    "PagePaginator",
    "find_safe_page_split",
    "create_continuation_page",
    "regenerate_toc_pages",
    "CoverRenderer",
    "CoverService",
]
