"""AI-powered technical promotion article generator using Groq/VasukiSquare LLM client."""

import logging
import re
from typing import List, Optional

from vasukisquare.book.models import Book
from vasukisquare.config import Settings, get_settings
from vasukisquare.llm.client import LLMClient
from vasukisquare.promotion.models import GeneratedArticleContent, PromotionPost, PromotionStatus

logger = logging.getLogger("vasukisquare.promotion.writer")

PROMOTION_SYSTEM_PROMPT = """You are a senior technical writer and educational essayist writing a high-signal article for DEV Community (dev.to) and developer platforms.

Your goal is to write a standalone, genuinely valuable, human-readable educational article exploring core principles, practical workflows, mental models, or actionable insights from a published guide.

EDITORIAL GUIDELINES FOR THE ARTICLE:
1. VALUE FIRST: The article MUST stand on its own as a valuable read. Deliver immediate insight, practical workflows, and clear mental models even if the reader never clicks any external link.
2. NO SPAMMY MARKETING: Never write sales pitches, generic hype, hollow buzzwords, or "Read my new book!" spam. Write with an authoritative, practitioner-focused voice.
3. ADAPTIVE CONTENT: If the guide is about programming, use clean code examples. If the guide is about AI prompting, digital privacy, cloud concepts, habits, or productivity, explain concepts using mental models, structured checklists, decision tables, and practical scenarios without forcing arbitrary code snippets.
4. NO FAKE ANECDOTES: Do not invent fake corporate stories ("When I worked at BigTech Corp"). Focus on real principles, methodologies, and clear analysis.
5. CLEAN ATTRIBUTION: Near the conclusion of the article, naturally introduce the full open-access guide as a free, comprehensive reference for readers who want to explore further.
6. CANONICAL LINK: You will be given the canonical guide URL. Include a clean Markdown hyperlink to this canonical URL in your conclusion section (e.g., `[Read the full guide online for free: Title]({canonical_url})`).
7. DEV.TO MARKDOWN FORMATTING: Use clean GitHub/DEV-flavored Markdown with standard headers (`##`, `###`), bolding, tables, and lists.
8. DEV.TO TAGS REQUIREMENTS:
   - Must contain ONLY lowercase ASCII letters and numbers (a-z, 0-9).
   - Must NOT contain spaces, hyphens, underscores, or '#' prefixes.
   - Must be between 2 and 30 characters in length.
   - Suggest ONLY 2 to 4 relevant tags (e.g. ['productivity', 'ai', 'cloud', 'security', 'webdev']).
"""


class PromotionWriter:
    """Generates educational promotion articles for published books using LLMClient."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.settings = settings or get_settings()
        self.llm_client = llm_client or LLMClient(settings=self.settings)

    def build_canonical_url(self, slug: str) -> str:
        """Construct the canonical web reader URL for a given book slug."""
        base = (self.settings.publication_base_url or "https://vasukisquare.cc").rstrip("/")
        clean_slug = (slug or "").strip().lstrip("/")
        return f"{base}/book/{clean_slug}"

    def _format_book_context(
        self,
        book: Book,
        canonical_url: str,
        angle_type: Optional[str] = None,
    ) -> str:
        """Construct rich contextual prompt detailing the book's contents and editorial structure."""
        chapters_text = ""
        if book.chapters:
            chapters_text = "\n".join(
                f"- Chapter {ch.chapter_number}: {ch.title}"
                + (f" - {ch.summary}" if ch.summary else "")
                for ch in book.chapters
            )
        else:
            chapters_text = "Standard comprehensive curriculum."

        keywords_str = ", ".join(book.discovery.keywords) if book.discovery.keywords else book.category or "Technology"

        angle_instruction = ""
        if angle_type == "mistakes_breakdown":
            angle_instruction = "\nEDITORIAL ANGLE: Focus on the top misconceptions, anti-patterns, and common mistakes people make, and how to fix them."
        elif angle_type == "actionable_checklist":
            angle_instruction = "\nEDITORIAL ANGLE: Structure the article as a practical, step-by-step checklist / implementation playbook."
        elif angle_type == "mental_model":
            angle_instruction = "\nEDITORIAL ANGLE: Break down the core mental models and foundational concepts with clear analogies and decision frameworks."
        elif angle_type == "deep_dive":
            angle_instruction = "\nEDITORIAL ANGLE: Provide a deep-dive exploration of a key subtopic or architectural principle from the guide."

        prompt = f"""EBOOK CONTEXT:
- Title: {book.title}
- Subtitle: {book.subtitle or 'A Comprehensive Practical Guide'}
- Domain / Category: {book.category or 'Technology & Computing'}
- Target Audience: {book.target_audience or 'Professionals, Learners, and Curious Thinkers'}
- Technical Depth: {book.technical_depth or 'Practical & Approachable'}
- Tone: {book.tone or 'Authoritative and Pragmatic'}
- Core Topics & Keywords: {keywords_str}
- Synopsis: {book.description or book.prompt}

CHAPTER STRUCTURE:
{chapters_text}
{angle_instruction}

CANONICAL EBOOK URL:
{canonical_url}

TASK:
Write a comprehensive, engaging educational article (approx. 700 - 1500 words) for DEV Community exploring key insights, mental models, or hands-on practices from this guide. Ensure the canonical URL is naturally embedded near the end."""
        return prompt

    def _normalize_tags(
        self,
        tags: List[str],
        default_category: Optional[str] = None,
        platform: str = "devto",
    ) -> List[str]:
        """Normalize tags ensuring valid lowercase strings without special characters."""
        if platform == "devto":
            from vasukisquare.promotion.publishers.devto import sanitize_devto_tags
            return sanitize_devto_tags(tags, fallback_category=default_category)

        # Generic fallback for other platforms
        clean: List[str] = []
        for t in tags:
            tag = str(t).strip().lower().lstrip("#")
            tag = "".join(c for c in tag if c.isalnum() or c in ("-", "_"))
            if tag and tag not in clean:
                clean.append(tag)
            if len(clean) >= 4:
                break
        if not clean:
            cat_tag = "".join(c for c in (default_category or "technology").lower() if c.isalnum())
            clean = [cat_tag or "programming", "tutorial"]
        return clean[:4]

    async def generate_article(
        self,
        book: Book,
        campaign_run_id: str,
        platform: str = "devto",
        angle_type: Optional[str] = None,
    ) -> PromotionPost:
        """Generate a validated PromotionPost for the given book and campaign."""
        canonical_url = self.build_canonical_url(book.slug)
        user_prompt = self._format_book_context(book, canonical_url, angle_type=angle_type)

        logger.info(
            f"[PromotionWriter:START] Generating article for book='{book.title}' (slug={book.slug}) "
            f"campaign={campaign_run_id} platform={platform}"
        )

        try:
            content: GeneratedArticleContent = await self.llm_client.invoke_structured(
                schema=GeneratedArticleContent,
                system_prompt=PROMOTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                stage="writing",
                temperature=0.7,
            )
        except Exception as e:
            logger.error(
                f"[PromotionWriter:ERROR] LLM generation failed for book='{book.title}': {e}"
            )
            raise e

        # Ensure canonical link exists in Markdown body
        body_md = content.body_markdown.strip()
        if canonical_url not in body_md:
            logger.info(
                f"[PromotionWriter] Appending missing canonical URL link to article footer for book='{book.slug}'."
            )
            cta_block = (
                f"\n\n---\n\n"
                f"### Further Reading\n\n"
                f"This article is adapted from the open technical curriculum in **[{book.title}]({canonical_url})**. "
                f"You can read the complete publication and interactive chapters online at [{canonical_url}]({canonical_url})."
            )
            body_md += cta_block

        tags = self._normalize_tags(content.tags, default_category=book.category, platform=platform)

        post = PromotionPost(
            campaign_run_id=campaign_run_id,
            book_id=book.id,
            book_slug=book.slug,
            platform=platform,
            title=content.title.strip(),
            body_markdown=body_md,
            tags=tags,
            canonical_url=canonical_url,
            status=PromotionStatus.GENERATED,
            generation_model=getattr(self.llm_client, "active_model", None),
        )

        logger.info(
            f"[PromotionWriter:SUCCESS] Generated article '{post.title}' ({len(body_md)} chars, tags={tags})"
        )
        return post

