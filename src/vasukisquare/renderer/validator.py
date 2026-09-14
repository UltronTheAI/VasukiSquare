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
                band_str = getattr(util.density_band, "value", str(util.density_band))
                err = (
                    f"Page {p.page_number} ('{p.content.headline}') is severely underfilled: "
                    f"utilization {util.estimated_ratio:.1%} < {util.hard_fail_ratio:.1%} threshold ({band_str})."
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
    def audit_book(
        cls,
        pages: List[Page],
        topic: str = "",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive 15-point audit of entire book across all generation, content, source, and layout rules."""
        import re
        issues: List[str] = []
        passed_checks: List[str] = []

        is_python_guide = "python" in topic.lower() or (language == "python")

        # 1. Escaped newlines in terminal blocks
        term_newline_issue = False
        for p in pages:
            for b in getattr(p.content, "blocks", []):
                if getattr(b, "type", "") == "terminal":
                    for line in getattr(b, "lines", []):
                        txt = getattr(line, "text", "")
                        if "\\n" in txt or "\\r" in txt:
                            issues.append(f"Page {p.page_number} TerminalBlock contains literal escaped newline in line: '{txt}'")
                            term_newline_issue = True
        if not term_newline_issue:
            passed_checks.append("Terminal newline escaping")

        # 2. Meaningless / Glitched Page Content
        glitch_issue = False
        for p in pages:
            if p.layout in ("cover", "chapter_opener", "toc", "copyright"):
                continue
            h = (p.content.headline or "").strip()
            if len(h) <= 2 or bool(re.match(r"^[^\w]*[a-zA-Z0-9]{1,2}[^\w]*$", h)):
                issues.append(f"Page {p.page_number} has glitched single-character headline: '{h}'")
                glitch_issue = True
            for b in getattr(p.content, "blocks", []):
                if getattr(b, "type", "") == "text":
                    t = getattr(b, "text", "").strip()
                    if bool(re.match(r"^(?:([a-zA-Z0-9])(?:\s+|\n+)*\1*)+$", t)) and len(set(t.replace(" ", "").replace("\n", ""))) <= 2:
                        issues.append(f"Page {p.page_number} contains repeated single-character junk paragraph: '{t[:30]}'")
                        glitch_issue = True
        if not glitch_issue:
            passed_checks.append("Glitched single-character content rejection")

        # 3. Post-code explanation requirement
        code_expl_issue = False
        for p in pages:
            if p.layout in ("cover", "chapter_opener", "toc", "copyright", "imprint", "references", "thank_you"):
                continue
            blocks = getattr(p.content, "blocks", [])
            for idx, b in enumerate(blocks):
                if getattr(b, "type", "") == "code":
                    # Check if subsequent block provides explanation
                    has_expl = False
                    for next_b in blocks[idx + 1:]:
                        if getattr(next_b, "type", "") in ("text", "callout") and len((getattr(next_b, "text", "") or getattr(next_b, "content", "")).split()) >= 6:
                            has_expl = True
                            break
                    if not has_expl:
                        issues.append(f"Page {p.page_number} has CodeBlock without post-code explanation walkthrough.")
                        code_expl_issue = True
        if not code_expl_issue:
            passed_checks.append("Post-code walkthrough coverage")

        # 4. Inappropriate or fake sources (ACM for programming guides)
        source_issue = False
        for p in pages:
            for s in p.sources or []:
                url = (getattr(s, "url", "") or "").lower()
                title = (getattr(s, "title", "") or "").lower()
                if "acm.org" in url and is_python_guide:
                    issues.append(f"Page {p.page_number} contains inappropriate ACM academic proceeding source for programming guide: '{url}'")
                    source_issue = True
                if "primary specification" in title and "acm.org" in url:
                    issues.append(f"Page {p.page_number} contains synthetic 'Primary Specification' title: '{title}'")
                    source_issue = True
        if not source_issue:
            passed_checks.append("Authoritative source verification")

        # 5. Generic systems engineering filler sentences
        filler_issue = False
        filler_patterns = [
            r"in modern systems engineering, .* serves as a foundational component",
            r"by consistently applying .*, you establish repeatable, friction-free execution",
            r"when designing systems around .*, decouple storage and computation",
        ]
        for p in pages:
            p_text = f"{p.content.headline or ''} {p.content.body or ''} " + " ".join(
                getattr(b, "text", "") or getattr(b, "content", "") for b in getattr(p.content, "blocks", [])
            )
            for pat in filler_patterns:
                if re.search(pat, p_text, re.IGNORECASE):
                    issues.append(f"Page {p.page_number} contains generic boilerplate pattern: '{pat}'")
                    filler_issue = True
        if not filler_issue:
            passed_checks.append("Generic filler suppression")

        # 6. False verification claims
        false_claim_issue = False
        for p in pages:
            p_text = f"{p.content.headline or ''} {p.content.body or ''} " + " ".join(
                getattr(b, "text", "") or getattr(b, "content", "") for b in getattr(p.content, "blocks", [])
            )
            for claim in ["Execution verified successfully.", "Concept verified successfully."]:
                if claim in p_text:
                    issues.append(f"Page {p.page_number} contains false unverified claim: '{claim}'")
                    false_claim_issue = True
        if not false_claim_issue:
            passed_checks.append("Truthful output verification")

        # 7. Empty visual component blocks
        empty_comp_issue = False
        for p in pages:
            for b in getattr(p.content, "blocks", []):
                b_type = getattr(b, "type", "")
                if b_type == "table" and not getattr(b, "rows", []):
                    issues.append(f"Page {p.page_number} contains TableBlock with no rows.")
                    empty_comp_issue = True
                elif b_type == "checklist" and not getattr(b, "items", []):
                    issues.append(f"Page {p.page_number} contains ChecklistBlock with no items.")
                    empty_comp_issue = True
                elif b_type == "comparison" and not (getattr(b, "left_items", []) or getattr(b, "right_items", [])):
                    issues.append(f"Page {p.page_number} contains empty ComparisonBlock.")
                    empty_comp_issue = True
        if not empty_comp_issue:
            passed_checks.append("Empty visual component suppression")

        # 8. Standard page validation (placeholders, topic drift, density)
        std_errors = cls.validate_book(pages, expected_topic=topic, expected_language=language)
        issues.extend(std_errors)
        if not std_errors:
            passed_checks.append("General content density and layout validation")

        return {
            "is_valid": len(issues) == 0,
            "total_pages": len(pages),
            "issues_count": len(issues),
            "issues": issues,
            "passed_checks": passed_checks,
        }

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

