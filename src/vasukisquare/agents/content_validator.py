"""Content density, word count, and technical quality validator for book pages."""

import logging
import re
from typing import Any, List, Optional
from pydantic import BaseModel, Field

from vasukisquare.book.models import PageContent
from vasukisquare.book.components import ContentBlock

logger = logging.getLogger(__name__)


class ContentValidationResult(BaseModel):
    """Result of evaluating generated page content density and completeness."""

    is_valid: bool = Field(description="Whether page satisfies quality and density criteria")
    word_count: int = Field(description="Estimated total words in prose and component blocks")
    needs_expansion: bool = Field(default=False, description="True if content is too sparse (< 250 words)")
    issues: List[str] = Field(default_factory=list, description="Specific quality issues detected")
    suggestions: List[str] = Field(default_factory=list, description="Suggested additions for expansion")


def count_page_words(page: PageContent) -> int:
    """Calculate total word count across prose paragraphs and component blocks."""
    total_words = 0

    # Count main body prose
    if page.body:
        total_words += len(re.findall(r'\b\w+\b', page.body))

    # Count sections
    if hasattr(page, "sections") and page.sections:
        for s in page.sections:
            if hasattr(s, "heading") and s.heading:
                total_words += len(re.findall(r'\b\w+\b', s.heading))
            if hasattr(s, "body") and s.body:
                total_words += len(re.findall(r'\b\w+\b', s.body))
            if hasattr(s, "content") and s.content:
                total_words += len(re.findall(r'\b\w+\b', s.content))

    # Count blocks
    for block in getattr(page, "blocks", []):
        b_type = getattr(block, "type", "")
        if b_type == "text" or hasattr(block, "text"):
            total_words += len(re.findall(r'\b\w+\b', getattr(block, "text", "")))
        if hasattr(block, "paragraphs") and block.paragraphs:
            for p in block.paragraphs:
                total_words += len(re.findall(r'\b\w+\b', str(p)))
        if hasattr(block, "content") and block.content:
            total_words += len(re.findall(r'\b\w+\b', str(block.content)))
        if hasattr(block, "code") and block.code:
            # Code tokens count toward density
            total_words += len(re.findall(r'\b\w+\b', str(block.code)))
        if hasattr(block, "lines") and block.lines:
            for line in block.lines:
                txt = getattr(line, "text", str(line))
                total_words += len(re.findall(r'\b\w+\b', txt))
        if hasattr(block, "quote") and block.quote:
            total_words += len(re.findall(r'\b\w+\b', str(block.quote)))
        if hasattr(block, "steps") and block.steps:
            for step in block.steps:
                total_words += len(re.findall(r'\b\w+\b', str(step)))
        if hasattr(block, "instructions") and block.instructions:
            for inst in block.instructions:
                total_words += len(re.findall(r'\b\w+\b', str(inst)))

    return total_words


def validate_page_content(
    page: PageContent,
    page_type: str = "content",
    is_technical: bool = True,
    min_words: int = 220,
    target_words: int = 400,
) -> ContentValidationResult:
    """Validate page against density, structure, and technical requirements."""
    # Special pages like chapter_opener, toc, copyright have different word count rules
    if page_type in ("chapter_opener", "cover", "toc", "copyright", "title", "half_title"):
        return ContentValidationResult(
            is_valid=True,
            word_count=50,
            needs_expansion=False,
            issues=[],
            suggestions=[],
        )

    words = count_page_words(page)
    issues = []
    suggestions = []

    # Check for placeholder text
    full_text_str = str(page.model_dump() if hasattr(page, "model_dump") else page)
    placeholder_patterns = [r"lorem ipsum", r"\[todo\]", r"\[placeholder\]", r"insert text here", r"sample text"]
    for pat in placeholder_patterns:
        if re.search(pat, full_text_str, re.IGNORECASE):
            issues.append(f"Detected placeholder text matching '{pat}'")

    # Word count check
    needs_expansion = False
    if words < min_words:
        needs_expansion = True
        issues.append(f"Page word count ({words}) is below minimum density threshold ({min_words} words)")
        suggestions.append("Add detailed explanations, concrete examples, or technical component blocks (Terminal/Code/Callout)")

    # Technical check
    if is_technical and page_type == "content":
        has_technical_block = False
        for b in getattr(page, "blocks", []):
            b_type = getattr(b, "type", "")
            if b_type in ("code", "terminal", "table", "step", "exercise", "comparison", "diagram"):
                has_technical_block = True
                break
        if not has_technical_block and words < 350:
            suggestions.append("Add a practical CodeBlock, Terminal command, or StepBlock to enhance technical teaching.")

    is_valid = len(issues) == 0 and not needs_expansion

    return ContentValidationResult(
        is_valid=is_valid,
        word_count=words,
        needs_expansion=needs_expansion,
        issues=issues,
        suggestions=suggestions,
    )

