"""Editorial Planning Agent inferring intent and generating structured BookPlans."""

import logging
from typing import List, Optional
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import (
    BookIntent,
    BookPlan,
    PlannedChapter,
    PlannedPage,
    SectionPlan,
    VisualAnchorType,
)
from vasukisquare.design.theme import Theme, get_chapter_theme
from vasukisquare.research.models import ResearchCorpus

logger = logging.getLogger(__name__)


# Default icons mapped to common chapter motifs
MOTIF_ICONS = [
    "sparkles",
    "cpu",
    "database",
    "layers",
    "code",
    "compass",
    "book-open",
    "globe",
]


class EditorialPlannerAgent:
    """Agent responsible for intent inference and structural editorial book planning."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    async def infer_intent(
        self,
        prompt: str,
        corpus: Optional[ResearchCorpus] = None,
    ) -> BookIntent:
        """Infer editorial intent, target audience, depth, and requirements from prompt."""
        if not self.settings.groq_api_key:
            return self._heuristic_intent(prompt)

        try:
            from langchain_groq import ChatGroq
            from langchain_core.prompts import ChatPromptTemplate

            llm = ChatGroq(
                api_key=self.settings.groq_api_key,
                model_name=self.settings.groq_model,
                temperature=0.2,
            )
            structured_llm = llm.with_structured_output(BookIntent)

            system_prompt = (
                "You are an executive book editor. Analyze the user's topic prompt and research summary. "
                "Infer the book_type, target_audience, technical_depth, tone, approximate_length, chapter_count (4 to 10), "
                "code_requirements, and diagram_requirements."
            )

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "Topic prompt: {prompt}\nResearch findings: {findings}"),
            ])

            findings_summary = ", ".join(corpus.key_findings[:5]) if corpus else "None"
            result = await (prompt_template | structured_llm).ainvoke({
                "prompt": prompt,
                "findings": findings_summary,
            })
            if isinstance(result, BookIntent):
                return result
            return self._heuristic_intent(prompt)
        except Exception as e:
            logger.warning(f"LLM Intent inference failed, falling back to heuristic: {e}")
            return self._heuristic_intent(prompt)

    def _heuristic_intent(self, prompt: str) -> BookIntent:
        """Deterministic heuristic intent inference based on prompt keywords."""
        p_lower = prompt.lower()

        # Length & Chapter count
        if any(w in p_lower for w in ["comprehensive", "in-depth", "complete", "definitive", "advanced"]):
            length = "standard"
            chapter_count = 6
        elif any(w in p_lower for w in ["short", "brief", "quick", "introductory", "overview"]):
            length = "short"
            chapter_count = 4
        else:
            length = "standard"
            chapter_count = 5

        # Code & diagram flags
        code_keywords = [
            "code", "programming", "python", "rust", "go", "java", "c++", "typescript",
            "javascript", "framework", "algorithm", "developer", "api", "database",
            "concurrency", "memory", "async", "backend"
        ]
        diagram_keywords = [
            "architecture", "system", "distributed", "network", "cloud", "pipeline",
            "design", "protocol", "concurrency", "memory", "management"
        ]

        code_req = any(w in p_lower for w in code_keywords)
        diagram_req = any(w in p_lower for w in diagram_keywords)

        # Technical depth
        if "expert" in p_lower or "internals" in p_lower:
            depth = "expert"
        elif "advanced" in p_lower:
            depth = "advanced"
        elif "beginner" in p_lower or "intro" in p_lower:
            depth = "introductory"
        else:
            depth = "intermediate"

        return BookIntent(
            book_type="technical_deep_dive",
            target_audience="Software Engineers, Architects, and Technical Leaders",
            technical_depth=depth,
            tone="authoritative",
            approximate_length=length,
            chapter_count=chapter_count,
            research_intensity="deep",
            code_requirements=code_req,
            diagram_requirements=diagram_req,
        )

    def _build_deterministic_chapters(
        self,
        title: str,
        intent: BookIntent,
        corpus: Optional[ResearchCorpus] = None,
    ) -> List[PlannedChapter]:
        """Generate structured chapter definitions and section layouts deterministically."""
        chapters: List[PlannedChapter] = []
        chapter_topics = [
            ("Foundations and Core Concepts", "Theoretical baseline, history, and key definitions.", "sparkles", [
                SectionPlan(title="Historical Context & Evolution", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                SectionPlan(title="Core Terminology & Taxonomies", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
            ]),
            ("Architectural Principles", "Internal mechanisms, components, and data flow.", "cpu", [
                SectionPlan(title="System Topology & Component Model", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                SectionPlan(title="Core Protocols & State Machines", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.TEXT]),
            ]),
            ("Practical Implementation", "Engineering patterns, code structures, and workflows.", "code", [
                SectionPlan(title="Reference Implementation Patterns", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                SectionPlan(title="Integration & Developer Experience", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
            ]),
            ("Performance, Benchmarks & Trade-offs", "Quantitative evaluations and comparative analysis.", "layers", [
                SectionPlan(title="Throughput & Latency Benchmarks", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.COMPARISON]),
                SectionPlan(title="Architectural Trade-offs Matrix", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
            ]),
            ("Production Best Practices & Case Studies", "Operational scaling, security, and real-world post-mortems.", "database", [
                SectionPlan(title="Scaling & Reliability Strategies", visual_anchors=[VisualAnchorType.QUOTE, VisualAnchorType.TEXT]),
                SectionPlan(title="Production Case Study & Retrospective", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
            ]),
            ("Emerging Trends & Future Outlook", "Next-generation paradigms and future research directions.", "compass", [
                SectionPlan(title="Horizon Technologies", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                SectionPlan(title="Strategic Recommendations", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
            ]),
        ]

        # Use intent.chapter_count
        count = min(intent.chapter_count, len(chapter_topics))
        page_budget_per_ch = 6 if intent.approximate_length == "short" else 8

        # Associate cited sources if corpus exists
        source_urls = [d.url for d in corpus.documents] if corpus else []

        for i in range(count):
            ch_num = i + 1
            ch_title, ch_summary, default_icon, sections = chapter_topics[i]
            icon = MOTIF_ICONS[i % len(MOTIF_ICONS)]
            theme = get_chapter_theme(ch_num)
            
            # Divide source URLs across chapters
            ch_sources = source_urls[i * 2 : (i + 1) * 2] if source_urls else []

            chapters.append(
                PlannedChapter(
                    chapter_number=ch_num,
                    title=f"{ch_title}",
                    summary=ch_summary,
                    icon=icon,
                    theme=theme,
                    page_budget=page_budget_per_ch,
                    sections=sections,
                    sources_to_cite=ch_sources,
                )
            )

        return chapters

    def _assemble_pages(
        self,
        book_title: str,
        chapters: List[PlannedChapter],
    ) -> tuple[List[PlannedPage], List[PlannedPage], List[PlannedPage]]:
        """Pre-allocate all book pages with strict sequential page numbering."""
        frontmatter: List[PlannedPage] = []
        backmatter: List[PlannedPage] = []
        all_pages: List[PlannedPage] = []
        curr_page_num = 1

        # 1. Frontmatter
        # Page 1: Cover
        p_cover = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.DARK,
            brief="High-impact visual book cover.",
        )
        frontmatter.append(p_cover)
        all_pages.append(p_cover)
        curr_page_num += 1

        # Page 2: Title / Imprint
        p_imprint = PlannedPage(
            page_number=curr_page_num,
            page_type="imprint",
            layout=LayoutType.TEXT_HEAVY.value,
            theme=Theme.LIGHT,
            brief="Half-title and publisher imprint.",
        )
        frontmatter.append(p_imprint)
        all_pages.append(p_imprint)
        curr_page_num += 1

        # Page 3: Copyright / Notice
        p_copyright = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.COPYRIGHT.value,
            layout=LayoutType.COPYRIGHT.value,
            theme=Theme.LIGHT,
            brief="Copyright notice, versioning, and legal disclaimer.",
        )
        frontmatter.append(p_copyright)
        all_pages.append(p_copyright)
        curr_page_num += 1

        # Page 4: Table of Contents
        p_toc = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.TOC.value,
            layout=LayoutType.TOC.value,
            theme=Theme.LIGHT,
            brief="Complete structured table of contents.",
        )
        frontmatter.append(p_toc)
        all_pages.append(p_toc)
        curr_page_num += 1

        # 2. Chapters
        for ch in chapters:
            # Opener page (Page 1 of chapter budget)
            p_opener = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.CHAPTER_OPENER.value,
                layout=LayoutType.CHAPTER_OPENER.value,
                chapter_number=ch.chapter_number,
                chapter_title=ch.title,
                theme=ch.theme,
                icon=ch.icon,
                brief=f"Chapter {ch.chapter_number} Opener: Lucide icon, number, and title only.",
            )
            all_pages.append(p_opener)
            curr_page_num += 1

            # Content pages in chapter budget (page_budget - 1)
            content_page_count = ch.page_budget - 1
            for cp_idx in range(content_page_count):
                # Distribute sections and visual anchors
                sec_idx = cp_idx % len(ch.sections) if ch.sections else 0
                sec = ch.sections[sec_idx] if ch.sections else None
                anchor = sec.visual_anchors[cp_idx % len(sec.visual_anchors)] if sec and sec.visual_anchors else VisualAnchorType.TEXT
                
                layout_type = LayoutType.EDITORIAL.value
                if anchor == VisualAnchorType.CODE:
                    layout_type = LayoutType.CODE_FOCUS.value
                elif anchor in (VisualAnchorType.COMPARISON, VisualAnchorType.TABLE):
                    layout_type = LayoutType.COMPARISON.value
                elif anchor == VisualAnchorType.DIAGRAM:
                    layout_type = LayoutType.DIAGRAM_FOCUS.value
                elif anchor == VisualAnchorType.STATISTIC:
                    layout_type = LayoutType.LARGE_NUMBER.value
                elif anchor == VisualAnchorType.QUOTE:
                    layout_type = LayoutType.QUOTE.value
                elif anchor == VisualAnchorType.TIMELINE:
                    layout_type = LayoutType.TIMELINE.value

                p_content = PlannedPage(
                    page_number=curr_page_num,
                    page_type="chapter_content",
                    layout=layout_type,
                    chapter_number=ch.chapter_number,
                    chapter_title=ch.title,
                    theme=ch.theme,
                    visual_anchor=anchor,
                    brief=sec.title if sec else f"Core Concepts: {anchor.value.title()}",
                )
                all_pages.append(p_content)
                curr_page_num += 1

        # 3. Backmatter
        # References Page
        p_refs = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.REFERENCES.value,
            layout=LayoutType.REFERENCES.value,
            theme=Theme.LIGHT,
            brief="Comprehensive bibliography and primary source citations.",
        )
        backmatter.append(p_refs)
        all_pages.append(p_refs)
        curr_page_num += 1

        # Acknowledgement Page
        p_ack = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.ACKNOWLEDGEMENT.value,
            layout=LayoutType.ACKNOWLEDGEMENT.value,
            theme=Theme.LIGHT,
            icon="heart",
            brief="Author and institutional acknowledgments.",
        )
        backmatter.append(p_ack)
        all_pages.append(p_ack)
        curr_page_num += 1

        # Thank You Page
        p_thanks = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.THANK_YOU.value,
            layout=LayoutType.THANK_YOU.value,
            theme=Theme.DARK,
            icon="sparkles",
            brief="Concluding acknowledgments and publisher note.",
        )
        backmatter.append(p_thanks)
        all_pages.append(p_thanks)

        return frontmatter, backmatter, all_pages

    async def generate_book_plan(
        self,
        prompt: str,
        intent: Optional[BookIntent] = None,
        corpus: Optional[ResearchCorpus] = None,
    ) -> BookPlan:
        """Create a complete editorial BookPlan from prompt, intent, and research corpus."""
        if intent is None:
            intent = await self.infer_intent(prompt, corpus)

        title = prompt.strip().title()
        subtitle = f"A Definitive {intent.book_type.replace('_', ' ').title()}"
        description = (
            f"An authoritative, {intent.technical_depth} guide tailored for {intent.target_audience}, "
            f"covering architectural principles, practical implementations, and production patterns."
        )

        chapters = self._build_deterministic_chapters(title, intent, corpus)
        frontmatter, backmatter, all_pages = self._assemble_pages(title, chapters)

        return BookPlan(
            title=title,
            subtitle=subtitle,
            description=description,
            intent=intent,
            frontmatter_pages=frontmatter,
            chapters=chapters,
            backmatter_pages=backmatter,
            all_planned_pages=all_pages,
            total_pages=len(all_pages),
        )

