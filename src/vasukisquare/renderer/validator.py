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
    def validate_no_duplicate_pages(cls, pages: List[Page]) -> List[str]:
        """Detect identical or near-duplicate content pages across the book."""
        errors: List[str] = []
        seen_texts: Dict[str, int] = {}

        for p in pages:
            if p.layout in ("cover", "imprint", "title", "copyright", "toc", "thank_you", "chapter_opener"):
                continue

            # Extract main text
            text_parts = []
            if p.content.headline:
                text_parts.append(p.content.headline.strip())
            for block in getattr(p.content, "blocks", []):
                if hasattr(block, "text") and block.text:
                    text_parts.append(block.text.strip())
                if hasattr(block, "code") and block.code:
                    text_parts.append(block.code.strip())

            combined = " ".join(text_parts).lower()
            if len(combined) > 40:
                # Normalize spaces
                import re
                norm = re.sub(r"\s+", " ", combined)
                if norm in seen_texts:
                    orig_page = seen_texts[norm]
                    err = f"Page {p.page_number} is an exact duplicate of Page {orig_page}."
                    errors.append(err)
                    logger.error(err)
                else:
                    seen_texts[norm] = p.page_number

        return errors

    @classmethod
    def validate_topic_relevance(
        cls,
        pages: List[Page],
        expected_topic: str,
        expected_language: Optional[str] = None,
    ) -> List[str]:
        """Verify that pages do not leak unrelated fallback code or off-topic database copy."""
        errors: List[str] = []
        t_lower = expected_topic.lower()

        is_python_book = "python" in t_lower or (expected_language == "python")
        is_database_book = any(w in t_lower for w in ["database", "raft", "lsm", "distributed", "b-tree", "consensus"])

        for p in pages:
            # Check for leaked distributed DB demo strings in non-database books
            if is_python_book and not is_database_book:
                page_text = ""
                if p.content.headline:
                    page_text += " " + p.content.headline
                for block in getattr(p.content, "blocks", []):
                    if hasattr(block, "text") and block.text:
                        page_text += " " + block.text
                    if hasattr(block, "code") and block.code:
                        page_text += " " + block.code
                    if hasattr(block, "language"):
                        lang = (block.language or "").lower()
                        if lang in ("rust", "c++", "cpp") and expected_language == "python":
                            err = f"Page {p.page_number} contains {lang.upper()} code block in a Python book."
                            errors.append(err)
                            logger.error(err)

                pt_lower = page_text.lower()
                for leaked_term in ["raftnode", "broadcast_request_votes", "b+ tree index", "memtable / wal"]:
                    if leaked_term in pt_lower:
                        err = f"Page {p.page_number} contains off-topic demo leak: '{leaked_term}' in a Python guide."
                        errors.append(err)
                        logger.error(err)

        return errors

    @classmethod
    def validate_final_book_quality(
        cls,
        pages: List[Page],
    ) -> List[str]:
        """Validate interior content density, utilization ratio, and content unit counts across book pages."""
        from vasukisquare.renderer.overflow import estimate_page_utilization

        errors: List[str] = []
        content_pages = [
            p for p in pages
            if p.layout not in ("cover", "imprint", "title", "copyright", "toc", "thank_you", "chapter_opener", "references", "acknowledgement")
            and p.page_type not in ("cover", "imprint", "title", "copyright", "toc", "thank_you", "chapter_opener", "references", "acknowledgement")
        ]

        if not content_pages:
            return errors

        ratios = []
        severely_underfilled = 0

        for p in content_pages:
            util = estimate_page_utilization(p)
            ratios.append(util.estimated_ratio)

            if util.is_hard_fail:
                severely_underfilled += 1
                err = (
                    f"Page {p.page_number} ('{p.content.headline}') is severely underfilled: "
                    f"utilization {util.estimated_ratio:.1%} < {util.hard_fail_ratio:.1%} threshold ({util.density_band.value})."
                )
                errors.append(err)
                logger.error(err)

            if util.content_units < 3:
                err = (
                    f"Page {p.page_number} ('{p.content.headline}') lacks sufficient educational content: "
                    f"found {util.content_units} content units (minimum required is 3-4)."
                )
                errors.append(err)
                logger.error(err)

            # Validate semantic completeness score if present
            if util.completeness_score and util.completeness_score.total_score < 60.0:
                err = (
                    f"Page {p.page_number} ('{p.content.headline}') failed semantic completeness score: "
                    f"{util.completeness_score.total_score:.1f}/100.0. Quality issues detected."
                )
                errors.append(err)
                logger.error(err)

        underfill_rate = severely_underfilled / len(content_pages)
        if underfill_rate > 0.15:
            err = (
                f"Book failed content density QA: {severely_underfilled}/{len(content_pages)} "
                f"({underfill_rate:.1%}) normal content pages are severely underfilled (max allowed: 15.0%)."
            )
            errors.append(err)
            logger.error(err)

        avg_density = sum(ratios) / len(ratios) if ratios else 0.0
        logger.info(
            f"[DENSITY SUMMARY] Content Pages: {len(content_pages)} | "
            f"Average Usable Density: {avg_density:.1%} | "
            f"Severely Underfilled: {severely_underfilled}"
        )

        return errors

    @classmethod
    def validate_book(
        cls,
        pages: List[Page],
        expected_topic: str = "",
        expected_language: Optional[str] = None,
        allow_fixtures: bool = False,
    ) -> List[str]:
        """Validate an entire book page sequence."""
        if allow_fixtures:
            return []
        all_errors: List[str] = []
        for p in pages:
            errs = cls.validate_page_content(p)
            all_errors.extend(errs)

        # Check for duplicates
        dup_errors = cls.validate_no_duplicate_pages(pages)
        all_errors.extend(dup_errors)

        # Check for topic relevance
        if expected_topic:
            rel_errors = cls.validate_topic_relevance(pages, expected_topic, expected_language)
            all_errors.extend(rel_errors)

        # Check content density and quality
        density_errors = cls.validate_final_book_quality(pages)
        all_errors.extend(density_errors)

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

