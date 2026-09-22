"""AI-powered technical promotion article generator using Groq/VasukiSquare LLM client."""

import logging
import re
from typing import List, Optional

from vasukisquare.book.models import Book
from vasukisquare.config import Settings, get_settings
from vasukisquare.llm.client import LLMClient
from vasukisquare.promotion.models import GeneratedArticleContent, PromotionPost, PromotionStatus

logger = logging.getLogger("vasukisquare.promotion.writer")

PROMOTION_SYSTEM_PROMPT = """You are a senior software engineer and technical educator writing a high-signal, in-depth technical article for DEV Community (dev.to).

Your goal is to write a standalone, genuinely valuable educational article exploring the core technical architectural principles, design patterns, or engineering methodologies discussed in a published technical ebook.

GUIDELINES FOR THE ARTICLE:
1. VALUE FIRST: The article MUST stand on its own as a great technical tutorial or architecture breakdown. Teach actionable concepts, provide clear mental models, and use clean code snippets, ASCII diagrams, or comparison tables where appropriate.
2. NO SPAMMY MARKETING: Never write generic sales pitches, hollow buzzwords, or "Buy this book now!" spam. Write with an authoritative, practitioner-focused voice.
3. NO FAKE ANECDOTES: Do not claim personal experiences you did not have (e.g. "When I was at company X"). Focus purely on technical merit and engineering analysis.
4. NATURAL EBOOK ATTRIBUTION: Near the conclusion of the article, naturally introduce the full open-access ebook as an extended reference for readers who want to dive deeper into the full curriculum.
5. CANONICAL LINK: You will be given the canonical ebook URL. You MUST include a clear Markdown hyperlink to this canonical URL in your conclusion section (e.g., `[Read the full technical ebook online for free: Title]({canonical_url})`).
6. DEV.TO MARKDOWN FORMATTING: Use clean GitHub/DEV-flavored Markdown with standard headers (`##`, `###`), bolding, code fences, and lists.
7. TAGS: Suggest 2 to 4 relevant tags (lowercase, alphanumeric or hyphens, no hashtags, e.g. `['python', 'architecture', 'webdev', 'systemdesign']`).
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

    def _format_book_context(self, book: Book, canonical_url: str) -> str:
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

        keywords_str = ", ".join(book.discovery.keywords) if book.discovery.keywords else book.category or "Software Engineering"

        prompt = f"""EBOOK CONTEXT:
- Title: {book.title}
- Subtitle: {book.subtitle or 'A Comprehensive Practical Guide'}
- Domain / Category: {book.category or 'Technology & Computing'}
- Target Audience: {book.target_audience or 'Software Developers, Architects, and Tech Enthusiasts'}
- Technical Depth: {book.technical_depth or 'Intermediate to Advanced'}
- Tone: {book.tone or 'Authoritative and Pragmatic'}
- Core Topics & Keywords: {keywords_str}
- Synopsis: {book.description or book.prompt}

CHAPTER STRUCTURE:
{chapters_text}

CANONICAL EBOOK URL:
{canonical_url}

TASK:
Write a comprehensive, engaging technical article (approx. 700 - 1500 words) for DEV Community exploring key insights, architecture patterns, or hands-on concepts from this ebook. Ensure the canonical URL is naturally embedded near the end."""
        return prompt

    def _normalize_tags(self, tags: List[str], default_category: Optional[str] = None) -> List[str]:
        """Normalize tags ensuring valid lowercase strings without special characters."""
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
    ) -> PromotionPost:
        """Generate a validated PromotionPost for the given book and campaign."""
        canonical_url = self.build_canonical_url(book.slug)
        user_prompt = self._format_book_context(book, canonical_url)

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

        tags = self._normalize_tags(content.tags, default_category=book.category)

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

