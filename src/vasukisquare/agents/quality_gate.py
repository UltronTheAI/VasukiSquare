"""Editorial Quality Gate for validating ideas, generated books, and promotional content against VasukiSquare standards."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from vasukisquare.book.models import Book, BookIntent, Page, PageContent
from vasukisquare.research.models import BookIdea
from vasukisquare.promotion.models import PromotionPost

logger = logging.getLogger("vasukisquare.agents.quality_gate")

# Disallowed AI cliché phrases and tropes
BANNED_AI_CLICHES = [
    "in today's fast-paced world",
    "in today's fast paced world",
    "in the fast-paced digital world",
    "in the digital age",
    "in this digital age",
    "unlock the power of",
    "unlocking the power of",
    "game-changer",
    "game changing",
    "let's dive in",
    "lets dive in",
    "let us dive in",
    "delve into",
    "it's crucial to remember",
    "it is crucial to remember",
    "without further ado",
    "a testament to",
    "navigate the complexities",
    "in conclusion, this section has explored",
]

# Marketing spam phrases to ban in promotion
BANNED_PROMOTION_SPAM = [
    "buy this book",
    "purchase the book",
    "read my new book",
    "limited time offer",
    "special discount",
    "grab your copy",
    "don't miss out on this deal",
]

# Coding tutorial indicator phrases
CODING_TUTORIAL_INDICATORS = [
    "pip install",
    "npm install",
    "cargo add",
    "def __init__",
    "console.log",
    "import React",
    "func main()",
    "public static void main",
]


class QualityValidationResult(BaseModel):
    """Result from an editorial quality check."""

    is_valid: bool
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    detected_cliches: List[str] = Field(default_factory=list)
    code_dump_detected: bool = False


class EditorialQualityGate:
    """Validator enforcing VasukiSquare's editorial identity across ideas, books, and articles."""

    @classmethod
    def validate_idea(cls, idea: BookIdea) -> QualityValidationResult:
        """Validate a researched BookIdea against VasukiSquare publishing standards."""
        reasons = []
        warnings = []
        score = 1.0

        topic_lower = (idea.topic or "").lower()
        title_lower = (idea.title or "").lower()
        prompt_lower = (idea.prompt or "").lower()
        combined = f"{topic_lower} {title_lower} {prompt_lower}"

        # 1. Reject pure coding tutorials or command cheat-sheets
        coding_flags = [
            "tutorial on writing syntax",
            "building a crud app in",
            "introduction to programming in",
            "cheat sheet for commands",
            "api reference manual",
        ]
        if any(flag in combined for flag in coding_flags):
            score -= 0.6
            reasons.append("Idea resembles a generic programming tutorial / syntax manual rather than a practical guide.")

        # 2. Check for explicit reader, problem solved, practical outcome
        if not getattr(idea, "intended_reader", None) and not idea.audience:
            score -= 0.2
            warnings.append("Missing explicit intended reader.")

        if not getattr(idea, "problem_solved", None):
            score -= 0.15
            warnings.append("Missing explicit problem solved statement.")

        if not getattr(idea, "practical_outcome", None):
            score -= 0.15
            warnings.append("Missing explicit practical outcome statement.")

        is_valid = score >= 0.60 and len(reasons) == 0
        return QualityValidationResult(
            is_valid=is_valid,
            score=max(0.0, min(1.0, score)),
            reasons=reasons,
            warnings=warnings,
        )

    @classmethod
    def validate_page_text(cls, text: str, allow_code: bool = False) -> QualityValidationResult:
        """Scan page text for AI clichés, empty filler, or unwanted code blocks."""
        text_lower = text.lower()
        detected_cliches = []
        reasons = []
        warnings = []
        score = 1.0

        for cliche in BANNED_AI_CLICHES:
            if cliche in text_lower:
                detected_cliches.append(cliche)
                score -= 0.2

        if detected_cliches:
            warnings.append(f"Contains AI clichés: {', '.join(detected_cliches)}")

        code_dump = False
        if not allow_code:
            code_matches = sum(1 for ind in CODING_TUTORIAL_INDICATORS if ind in text)
            if code_matches >= 2:
                code_dump = True
                score -= 0.4
                reasons.append("Unsolicited code / package installation snippets found in non-coding guide.")

        return QualityValidationResult(
            is_valid=(score >= 0.70 and len(reasons) == 0),
            score=max(0.0, min(1.0, score)),
            reasons=reasons,
            warnings=warnings,
            detected_cliches=detected_cliches,
            code_dump_detected=code_dump,
        )

    @classmethod
    def validate_book(cls, book: Book) -> QualityValidationResult:
        """Validate an entire generated Book against editorial standards."""
        allow_code = getattr(book, "intent", None) and getattr(book.intent, "code_requirements", False)
        all_cliches = []
        all_reasons = []
        all_warnings = []
        code_dumps = 0
        total_pages = len(book.pages)

        if total_pages == 0:
            return QualityValidationResult(is_valid=False, score=0.0, reasons=["Book has 0 pages."])

        for page in book.pages:
            content_str = ""
            if page.content:
                content_str += f"{page.content.headline or ''}\n{page.content.body or ''}\n"
                if hasattr(page.content, "blocks"):
                    for block in page.content.blocks:
                        if hasattr(block, "text"):
                            content_str += f"{block.text}\n"
                        elif hasattr(block, "content"):
                            content_str += f"{block.content}\n"
                        elif hasattr(block, "code") and not allow_code:
                            code_dumps += 1

            page_res = cls.validate_page_text(content_str, allow_code=bool(allow_code))
            if page_res.detected_cliches:
                all_cliches.extend(page_res.detected_cliches)
            if page_res.code_dump_detected:
                code_dumps += 1

        score = 1.0
        if all_cliches:
            score -= min(0.3, len(set(all_cliches)) * 0.05)
            all_warnings.append(f"Encountered repetitive clichés across book: {', '.join(set(all_cliches))}")

        if not allow_code and code_dumps > 0:
            score -= min(0.5, code_dumps * 0.15)
            all_reasons.append(f"Detected {code_dumps} unsolicited code blocks in non-coding book.")

        return QualityValidationResult(
            is_valid=(score >= 0.65 and len(all_reasons) == 0),
            score=max(0.0, min(1.0, score)),
            reasons=all_reasons,
            warnings=all_warnings,
            detected_cliches=list(set(all_cliches)),
            code_dump_detected=(code_dumps > 0),
        )

    @classmethod
    def validate_promotion_post(cls, post: PromotionPost) -> QualityValidationResult:
        """Validate promotional DEV article for standalone value, absence of spam, and canonical link."""
        body_lower = post.body_markdown.lower()
        reasons = []
        warnings = []
        score = 1.0

        # Check for spam marketing phrases
        for spam in BANNED_PROMOTION_SPAM:
            if spam in body_lower:
                score -= 0.3
                reasons.append(f"Contains promotional sales spam: '{spam}'")

        # Check for canonical link
        if post.canonical_url and post.canonical_url not in post.body_markdown:
            score -= 0.2
            warnings.append("Missing canonical URL hyperlink in article body.")

        # Check minimum word count for standalone educational value
        word_count = len(post.body_markdown.split())
        if word_count < 100:
            score -= 0.4
            reasons.append(f"Article is too short ({word_count} words); lacks standalone educational depth.")

        return QualityValidationResult(
            is_valid=(score >= 0.70 and len(reasons) == 0),
            score=max(0.0, min(1.0, score)),
            reasons=reasons,
            warnings=warnings,
        )

