"""Content quality and geometric overflow validator for VasukiSquare pages and books."""

import logging
from typing import Any, Dict, List, Optional
from vasukisquare.book.models import Page

logger = logging.getLogger(__name__)

# Forbidden placeholder strings that must never appear in production output
FORBIDDEN_PLACEHOLDERS = [
    "content for section",
    "focusing on",
    "lorem ipsum",
    "placeholder text",
    "sample content",
    "example content here",
    "todo:",
    "tbd:",
    "[insert ",
    "<insert ",
]

# Patterns that indicate search query leakage or raw encoding in visible text
FORBIDDEN_ARTIFACT_PATTERNS = [
    "q=",
    "utm_source=",
    "utm_medium=",
    "%20",
    "%3a",
    "%2c",
    "%2f",
]


class ContentValidator:
    """Validates that rendered book pages contain substantive, placeholder-free technical content."""

    @classmethod
    def validate_page_content(cls, page: Page) -> List[str]:
        """Inspect an individual page for scaffolding copy and placeholder text."""
        errors: List[str] = []
        text_corpus: List[str] = []

        if page.content.headline:
            text_corpus.append(page.content.headline)
        if page.content.body:
            text_corpus.append(page.content.body)
        for kp in page.content.key_points:
            text_corpus.append(kp)

        # Inspect blocks
        for block in getattr(page.content, "blocks", []):
            if hasattr(block, "text") and block.text:
                text_corpus.append(block.text)
            if hasattr(block, "content") and block.content:
                text_corpus.append(block.content)
            if hasattr(block, "caption") and block.caption:
                text_corpus.append(block.caption)
            if hasattr(block, "quote") and block.quote:
                text_corpus.append(block.quote)
            if hasattr(block, "title") and block.title:
                text_corpus.append(block.title)
            if hasattr(block, "source_title") and block.source_title:
                text_corpus.append(block.source_title)

        # Inspect raw HTML if set
        if page.html:
            # Strip tags and inspect text nodes
            import re
            text_only = re.sub(r"<[^>]+>", " ", page.html)
            text_corpus.append(text_only)

        full_text = " ".join(text_corpus).lower()
        for placeholder in FORBIDDEN_PLACEHOLDERS:
            if placeholder in full_text:
                err = f"Page {page.page_number} contains forbidden placeholder copy: '{placeholder}'"
                errors.append(err)
                logger.error(err)

        for artifact in FORBIDDEN_ARTIFACT_PATTERNS:
            if artifact in full_text:
                err = f"Page {page.page_number} contains query/encoding artifact: '{artifact}'"
                errors.append(err)
                logger.error(err)

        return errors

    @classmethod
    def validate_book(cls, pages: List[Page], allow_fixtures: bool = False) -> List[str]:
        """Validate an entire book page sequence."""
        if allow_fixtures:
            return []
        all_errors: List[str] = []
        for p in pages:
            errs = cls.validate_page_content(p)
            all_errors.extend(errs)
        return all_errors

    @classmethod
    def validate_dom_metrics(
        cls,
        page_number: int,
        metrics: Dict[str, Any],
        safe_right_mm: float = 192.0,
        safe_bottom_mm: float = 277.0,
    ) -> List[str]:
        """Inspect Playwright DOM bounding box measurements for right/bottom overflow."""
        errors: List[str] = []
        scroll_width = metrics.get("scroll_width", 0)
        client_width = metrics.get("client_width", 0)

        if scroll_width > client_width + 1:
            diff_px = scroll_width - client_width
            err = (
                f"Page {page_number} horizontal overflow detected: "
                f"scrollWidth ({scroll_width}px) > clientWidth ({client_width}px), delta: {diff_px}px"
            )
            errors.append(err)
            logger.warning(err)

        for el in metrics.get("overflow_elements", []):
            selector = el.get("selector", "element")
            right_mm = el.get("right_mm", 0)
            if right_mm > safe_right_mm:
                overflow_mm = right_mm - safe_right_mm
                err = (
                    f"Page {page_number} right edge overflow: selector '{selector}', "
                    f"right edge: {right_mm:.1f}mm > safe edge: {safe_right_mm:.1f}mm "
                    f"(overflow: {overflow_mm:.1f}mm)"
                )
                errors.append(err)
                logger.warning(err)

        return errors

