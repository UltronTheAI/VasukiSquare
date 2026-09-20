"""Editorial Planning Agent inferring intent and generating structured BookPlans."""

import logging
import re
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import (
    LayoutType,
    PAGE_TYPE_SPECS,
    TechnicalPageType,
    PublicationProfile,
)
from vasukisquare.book.models import (
    BookIntent,
    BookPlan,
    PlannedChapter,
    PlannedPage,
    PagePurpose,
    RequirementCoverageItem,
    RequirementCoverageMatrix,
    SectionPlan,
    VisualAnchorType,
)
from vasukisquare.design.theme import Theme, get_chapter_theme
from vasukisquare.research.models import ResearchCorpus
from vasukisquare.research.sanitization import clean_source_title
from vasukisquare.llm.client import LLMClient, GroqGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics

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
    "terminal",
    "shield-check",
    "zap",
    "git-branch",
    "globe",
]


class GeneratedChapterPlan(BaseModel):
    """Schema for LLM-generated chapter plan."""

    title: str = Field(description="Chapter title")
    summary: str = Field(description="Summary of topics covered in this chapter")
    icon: str = Field(default="code", description="Lucide icon name")
    key_sections: List[str] = Field(default_factory=list, description="3 to 5 distinct section titles for this chapter")


class GeneratedBookOutline(BaseModel):
    """Schema for LLM-generated complete book outline."""

    chapters: List[GeneratedChapterPlan] = Field(description="Sequential list of chapters")


def clean_and_resolve_title(
    topic: Optional[str],
    prompt: Optional[str] = None,
    explicit_title: Optional[str] = None,
) -> str:
    """Resolve and enforce strict title constraints: non-empty, clean, and <= 50 chars."""
    if explicit_title and explicit_title.strip():
        t = explicit_title.strip()
        for q in ['"', "'", "“", "”", "`"]:
            if t.startswith(q) and t.endswith(q):
                t = t[1:-1].strip()
        for pfx in ["Title:", "Book Title:", "title:"]:
            if t.startswith(pfx):
                t = t[len(pfx):].strip()
        t = clean_source_title(t)
        if len(t) <= 50:
            return t
        return t[:47].rstrip() + "..."

    raw = (topic or prompt or "Comprehensive Guide").strip()
    for q in ['"', "'", "“", "”", "`"]:
        if raw.startswith(q) and raw.endswith(q):
            raw = raw[1:-1].strip()
    for pfx in ["Title:", "Book Title:", "title:"]:
        if raw.startswith(pfx):
            raw = raw[len(pfx):].strip()

    clean_topic = clean_source_title(raw)
    if len(clean_topic) <= 50:
        return clean_topic

    if ":" in clean_topic:
        first_part = clean_topic.split(":", 1)[0].strip()
        if 8 <= len(first_part) <= 50:
            return first_part
    if " - " in clean_topic:
        first_part = clean_topic.split(" - ", 1)[0].strip()
        if 8 <= len(first_part) <= 50:
            return first_part

    words = clean_topic.split()
    cand = ""
    for w in words:
        if len(cand) + len(w) + 1 <= 47:
            cand = f"{cand} {w}".strip() if cand else w
        else:
            break
    if cand and len(cand) >= 8:
        return cand + "..."
    return clean_topic[:47].rstrip() + "..."


def validate_chapter_progression(chapters: List[PlannedChapter]) -> bool:
    """Validate that chapter titles form a logical, non-repetitive pedagogical progression."""
    if not chapters:
        return False
    seen_titles = set()
    for ch in chapters:
        normalized = ch.title.lower().strip()
        if not normalized or len(normalized) < 3:
            return False
        if normalized in seen_titles:
            logger.warning(f"Duplicate chapter title detected: '{ch.title}'")
            return False
        seen_titles.add(normalized)
    return True


def build_requirement_coverage_matrix(
    intent: BookIntent,
    chapters: List[PlannedChapter],
    all_pages: List[PlannedPage],
) -> RequirementCoverageMatrix:
    """Build and evaluate requirement coverage matrix mapping user requirements to planned chapters/pages."""
    items: List[RequirementCoverageItem] = []
    missing: List[str] = []

    # 1. Check required topics
    req_topics = list(intent.required_topics or [])
    if intent.is_technical:
        if not any("syntax" in t.lower() or "variable" in t.lower() for t in req_topics):
            req_topics.append("Core Syntax & Variables")
        if not any("loop" in t.lower() or "control" in t.lower() for t in req_topics):
            req_topics.append("Control Flow & Loops")
        if not any("function" in t.lower() for t in req_topics):
            req_topics.append("Functions & Reusability")

    for req in req_topics:
        req_norm = req.lower()
        matched_pages = []
        matched_ch_num = None
        for p in all_pages:
            p_text = f"{p.chapter_title or ''} {p.brief} {p.page_purpose.learning_goal if p.page_purpose else ''}".lower()
            if any(term in p_text for term in req_norm.split()):
                matched_pages.append(p.page_number)
                if matched_ch_num is None and p.chapter_number:
                    matched_ch_num = p.chapter_number
        is_covered = len(matched_pages) > 0
        items.append(
            RequirementCoverageItem(
                requirement=req,
                planned=is_covered,
                chapter_number=matched_ch_num,
                page_numbers=matched_pages,
            )
        )
        if not is_covered:
            missing.append(req)

    # 2. Check desired elements (exercises, code, etc.)
    desired = list(intent.desired_elements or [])
    if intent.code_requirements and "executable code examples" not in desired:
        desired.append("executable code examples")

    for elem in desired:
        elem_norm = elem.lower()
        matched_pages = []
        for p in all_pages:
            purpose = p.page_purpose
            if "code" in elem_norm and (p.visual_anchor == VisualAnchorType.CODE or (purpose and purpose.is_hands_on)):
                matched_pages.append(p.page_number)
            elif "exercise" in elem_norm and (p.visual_anchor == VisualAnchorType.EXERCISE or (purpose and purpose.page_type == "exercise")):
                matched_pages.append(p.page_number)
            elif "checklist" in elem_norm and p.visual_anchor == VisualAnchorType.CHECKLIST:
                matched_pages.append(p.page_number)
            elif "plan" in elem_norm and p.visual_anchor == VisualAnchorType.TIMELINE:
                matched_pages.append(p.page_number)

        is_covered = len(matched_pages) > 0
        items.append(
            RequirementCoverageItem(
                requirement=f"Element: {elem}",
                planned=is_covered,
                page_numbers=matched_pages,
            )
        )
        if not is_covered:
            missing.append(f"Element: {elem}")

    return RequirementCoverageMatrix(
        items=items,
        is_complete=(len(missing) == 0),
        missing_requirements=missing,
    )


def log_plan_diagnostics(plan: BookPlan, coverage: RequirementCoverageMatrix) -> None:
    """Output detailed development diagnostics on the constructed editorial plan."""
    logger.info("=" * 60)
    logger.info(f"EDITORIAL PLAN DIAGNOSTICS: '{plan.title}'")
    logger.info(f"Subtitle: {plan.subtitle}")
    logger.info(f"Target Pages: {plan.total_pages} | Chapters: {len(plan.chapters)}")
    logger.info(f"Requirement Coverage: {len(coverage.items) - len(coverage.missing_requirements)}/{len(coverage.items)} items planned.")
    if coverage.missing_requirements:
        logger.warning(f"Uncovered requirements: {', '.join(coverage.missing_requirements)}")
    for ch in plan.chapters:
        content_pages = ch.page_budget - 1
        logger.info(f"  Ch {ch.chapter_number}: '{ch.title}' ({content_pages} content pages, Theme: {ch.theme.value}, Icon: {ch.icon})")
    logger.info("=" * 60)


class EditorialPlannerAgent:
    """Agent responsible for intent inference and structural editorial book planning."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self.llm_client = llm_client or LLMClient(self.settings, self.metrics)

    async def infer_intent(
        self,
        topic: Optional[str] = None,
        prompt: Optional[str] = None,
        title: Optional[str] = None,
        target_pages: int = 30,
        corpus: Optional[ResearchCorpus] = None,
    ) -> BookIntent:
        """Infer editorial intent, target audience, depth, and requirements from topic and prompt."""
        resolved_title = clean_and_resolve_title(topic, prompt=prompt, explicit_title=title)
        effective_topic = topic or prompt or "General Subject"

        if self.settings.vasukisquare_mock_mode:
            return self._heuristic_intent(effective_topic, prompt=prompt, title=resolved_title, target_pages=target_pages)

        system_prompt = (
            "You are an executive book editor and educational curriculum architect. "
            "Analyze the user's book topic, editorial prompt/instructions, and research findings. "
            "Infer the book_type (e.g. practical_guide, beginner_guide, tutorial_manual, technical_deep_dive, handbook), "
            "is_technical (boolean: true if software/programming/technical systems, false if self-help, habits, finance, lifestyle, general knowledge), "
            "target_audience, technical_depth (introductory, intermediate, advanced, expert), purpose, tone, "
            "required_topics (list of subtopics that must be covered based on the curriculum and user prompt), "
            "avoid_topics (list of topics or filler to avoid), "
            "desired_elements (e.g. exercises, checklists, 30-day plan, case studies, code examples, comparison tables, mini-project), "
            "special_instructions, chapter_count (adaptive, default 6 to 10), code_requirements, diagram_requirements, "
            "primary_programming_language (null if non-technical or language-agnostic), and domain_topic."
        )

        findings_summary = "\n".join([f"- {d.title} ({d.domain}): {d.summary[:200]}" for d in corpus.documents[:5]]) if corpus and corpus.documents else "None"
        user_prompt = (
            f"Topic: {effective_topic}\n"
            f"Explicit Title: {title or 'None'}\n"
            f"Editorial Brief / Prompt: {prompt or 'None'}\n"
            f"Target Pages: {target_pages}\n\n"
            f"Research dossier findings:\n{findings_summary}\n\n"
            f"Infer the complete structured BookIntent."
        )

        try:
            result = await self.llm_client.invoke_structured(
                schema=BookIntent,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                stage="intent_inference",
                temperature=0.2,
            )
            result.topic = effective_topic
            result.title = resolved_title
            result.original_prompt = prompt
            result.target_pages = target_pages

            if not result.is_technical:
                result.code_requirements = False
                result.primary_programming_language = None
                if any(w in effective_topic.lower() for w in ["poem", "poetry", "verse", "sonnet"]):
                    result.publication_profile = PublicationProfile.POETRY
                elif not result.publication_profile or result.publication_profile == PublicationProfile.TECHNICAL:
                    result.publication_profile = PublicationProfile.GENERAL_NONFICTION
            else:
                result.publication_profile = PublicationProfile.TECHNICAL
                if not result.primary_programming_language:
                    combined_text = f"{effective_topic} {prompt or ''}"
                    result.primary_programming_language = self._detect_language(combined_text)

            return result
        except Exception as e:
            if self.settings.vasukisquare_mock_mode:
                logger.warning(f"LLM Intent inference failed in mock mode, falling back to heuristic: {e}")
                return self._heuristic_intent(effective_topic, prompt=prompt, title=resolved_title, target_pages=target_pages)
            raise GroqGenerationError(f"Book intent inference failed via Groq: {e}") from e

    def _detect_language(self, prompt: str) -> Optional[str]:
        """Detect primary programming language from prompt."""
        p_lower = prompt.lower()
        languages = {
            "python": "python",
            "rust": "rust",
            "golang": "go",
            "go ": "go",
            "typescript": "typescript",
            "javascript": "javascript",
            "c++": "cpp",
            "cpp": "cpp",
            "java ": "java",
            "kotlin": "kotlin",
            "swift": "swift",
            "sql": "sql",
        }
        for kw, lang in languages.items():
            if kw in p_lower:
                return lang
        return None

    def _heuristic_intent(
        self,
        topic: str,
        prompt: Optional[str] = None,
        title: Optional[str] = None,
        target_pages: int = 30,
    ) -> BookIntent:
        """Deterministic heuristic intent inference based on topic and prompt keywords."""
        resolved_title = clean_and_resolve_title(topic, prompt=prompt, explicit_title=title)
        combined = f"{topic} {prompt or ''}".lower()
        primary_lang = self._detect_language(combined)

        tech_indicators = [
            "code", "programming", "python", "rust", "go", "java", "c++", "typescript",
            "javascript", "framework", "algorithm", "developer", "api", "database",
            "concurrency", "memory", "async", "backend", "programs", "building", "liorandb",
            "db", "software", "devops", "kubernetes", "linux", "cloud", "react", "sql"
        ]
        is_technical = any(w in combined for w in tech_indicators) or (primary_lang is not None)

        # Technical depth & Audience
        if any(w in combined for w in ["beginner", "zero to", "getting started", "from scratch", "basics", "introduction", "intro", "noob", "noobs", "student", "young professional"]):
            depth = "introductory"
            audience = "Students, Young Professionals, and Beginners" if not is_technical else "Absolute Beginners, Self-Taught Learners, and New Practitioners"
            book_type = "practical_guide" if not is_technical else "beginner_guide"
            tone = "encouraging, practical, and structured"
        elif any(w in combined for w in ["expert", "internals", "under the hood", "advanced architecture"]):
            depth = "expert"
            audience = "Domain Specialists and Senior Leaders" if not is_technical else "Principal Engineers, System Architects, and Technical Leaders"
            book_type = "executive_briefing" if not is_technical else "technical_deep_dive"
            tone = "authoritative and analytical"
        elif any(w in combined for w in ["advanced", "deep dive", "performance"]):
            depth = "advanced"
            audience = "Experienced Practitioners and Strategists" if not is_technical else "Senior Software Engineers and Architects"
            book_type = "handbook" if not is_technical else "technical_deep_dive"
            tone = "authoritative and comprehensive"
        else:
            depth = "intermediate"
            audience = "Practitioners, Students, and Enthusiasts" if not is_technical else "Software Developers and Engineering Practitioners"
            book_type = "practical_guide" if not is_technical else "technical_handbook"
            tone = "practical, actionable, and clear"

        desired_elements = []
        if "exercise" in combined or "exercises" in combined:
            desired_elements.append("exercises")
        if "checklist" in combined or "checklists" in combined:
            desired_elements.append("checklists")
        if "30-day" in combined or "action plan" in combined or "plan" in combined:
            desired_elements.append("30-day improvement plan")
        if "mistake" in combined or "common mistakes" in combined:
            desired_elements.append("common mistakes and solutions")
        if "example" in combined or "examples" in combined:
            desired_elements.append("realistic practical examples")
        if is_technical:
            desired_elements.append("code examples")
            desired_elements.append("expected terminal output")
            if "project" in combined or "final project" in combined or "mini project" in combined or "challenge" in combined:
                desired_elements.append("capstone mini-project")

        required_topics = []
        if "habit" in combined or "routine" in combined:
            required_topics.extend(["habit loops and psychology", "small daily wins", "tracking and systems", "breaking bad habits", "30-day roadmap"])
        elif "python" in combined or primary_lang == "python":
            required_topics.extend([
                "what Python is and how programs work",
                "installation and running Python",
                "variables and primitive data types",
                "operators and boolean expressions",
                "input, output and formatted strings",
                "conditional branches (if/elif/else)",
                "loops (for, while, break, continue)",
                "functions, arguments and return values",
                "lists, tuples, dictionaries and sets",
                "error handling and exceptions",
                "reading and writing files",
                "modules and packages",
                "basic object-oriented programming",
                "final mini project combining concepts"
            ])
        elif "liorandb" in combined:
            required_topics.extend(["core architecture", "installation & setup", "crud queries", "indexing & performance"])

        chapter_count = self.calculate_adaptive_chapter_count(target_pages)
        # Extract explicit chapter count if specified in prompt (e.g. "5 chapters", "8 chapters")
        ch_match = re.search(r"(\d+)\s+chapters?", combined)
        if ch_match:
            try:
                chapter_count = int(ch_match.group(1))
            except ValueError:
                pass

        code_req = is_technical and (any(w in combined for w in tech_indicators) or primary_lang is not None)
        diagram_keywords = [
            "architecture", "system", "distributed", "network", "cloud", "pipeline",
            "design", "protocol", "concurrency", "memory", "management", "workflow",
            "cycle", "loop", "framework", "model", "mindset"
        ]
        diagram_req = any(w in combined for w in diagram_keywords)
        domain_topic = "personal_development" if not is_technical else ("programming_guide" if primary_lang else "systems_architecture")

        pub_profile = PublicationProfile.TECHNICAL if is_technical else (
            PublicationProfile.POETRY if any(w in combined for w in ["poem", "poetry", "verse", "sonnet"]) else PublicationProfile.GENERAL_NONFICTION
        )

        return BookIntent(
            topic=topic,
            title=resolved_title,
            original_prompt=prompt,
            book_type=book_type,
            target_audience=audience,
            purpose=f"Provide a comprehensive, actionable guide to {topic}." if not prompt else prompt[:150],
            tone=tone,
            technical_depth=depth,
            approximate_length="standard",
            required_topics=required_topics,
            avoid_topics=["generic fluff", "unverified claims", "SEO filler"],
            desired_elements=desired_elements,
            target_pages=target_pages,
            is_technical=is_technical,
            publication_profile=pub_profile,
            chapter_count=chapter_count,
            research_intensity="standard",
            code_requirements=code_req,
            diagram_requirements=diagram_req,
            primary_programming_language=primary_lang if is_technical else None,
            domain_topic=domain_topic,
        )

    async def _plan_chapters_with_llm(
        self,
        title: str,
        intent: BookIntent,
        corpus: Optional[ResearchCorpus],
        chapter_count: int,
    ) -> Optional[List[PlannedChapter]]:
        """Use Groq LLM to generate topic-specific, progression-aligned chapters."""
        if self.settings.vasukisquare_mock_mode:
            return None

        findings = []
        if corpus and corpus.documents:
            for d in corpus.documents[:8]:
                cleaned_doc_title = clean_source_title(d.title)
                findings.append(f"Source: {cleaned_doc_title} ({d.url})\nSummary: {d.summary}")
        findings_text = "\n\n".join(findings) if findings else "No external research available."

        if intent.is_technical:
            system_prompt = (
                f"You are a master technical author and curriculum architect. "
                f"Create a logically structured, progressive Table of Contents for an ebook titled: '{title}'.\n"
                f"Target Audience: {intent.target_audience} (Depth: {intent.technical_depth}).\n"
                f"Primary Language / Ecosystem: {intent.primary_programming_language or 'Domain Standard'}.\n\n"
                f"CRITICAL INSTRUCTIONS:\n"
                f"1. Generate EXACTLY {chapter_count} sequential chapters taking the reader progressively from basics to building real applications.\n"
                f"2. DERIVE the outline strictly from the core pedagogical curriculum and required topics. "
                f"DO NOT copy web search snippet titles, Wikipedia headings, or SEO strings into chapter titles.\n"
                f"3. For EACH chapter, specify 3 to 4 distinct key_sections covering concrete subtopics.\n"
                f"4. Assign a relevant Lucide icon (e.g. terminal, code, database, layers, cpu, shield-check, zap, compass) to each chapter."
            )
        else:
            system_prompt = (
                f"You are a master author and educational book architect. "
                f"Create a logically structured, progressive Table of Contents for a practical guide titled: '{title}'.\n"
                f"Target Audience: {intent.target_audience} (Tone: {intent.tone}).\n"
                f"Desired Elements: {', '.join(intent.desired_elements) if intent.desired_elements else 'exercises, checklists, action plans'}.\n\n"
                f"CRITICAL INSTRUCTIONS:\n"
                f"1. Generate EXACTLY {chapter_count} sequential chapters that take the reader from foundational concepts to lasting practical mastery.\n"
                f"2. Include dedicated chapters/sections for practical exercises, checklists, and step-by-step action plans.\n"
                f"3. Do NOT copy raw search titles or web page headlines.\n"
                f"4. Assign a relevant Lucide icon (e.g. sparkles, compass, shield-check, layers, zap, book-open, heart) to each chapter."
            )

        user_prompt = f"Research Dossier:\n{findings_text}\n\nGenerate the complete GeneratedBookOutline."

        try:
            result: GeneratedBookOutline = await self.llm_client.invoke_structured(
                schema=GeneratedBookOutline,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                stage="chapter_planning",
                temperature=0.3,
            )

            if not result or not result.chapters or len(result.chapters) < 2:
                raise ValueError("LLM returned insufficient chapters in GeneratedBookOutline.")

            source_urls = [d.url for d in corpus.documents] if corpus else []
            chapters: List[PlannedChapter] = []

            for i, gen_ch in enumerate(result.chapters[:chapter_count]):
                ch_num = i + 1
                theme = get_chapter_theme(ch_num)
                icon = gen_ch.icon if gen_ch.icon in MOTIF_ICONS else MOTIF_ICONS[i % len(MOTIF_ICONS)]
                ch_sources = source_urls[i * 2 : (i + 1) * 2] if source_urls else []
                ch_title = clean_source_title(gen_ch.title)

                sections: List[SectionPlan] = []
                raw_sections = gen_ch.key_sections if len(gen_ch.key_sections) >= 3 else [
                    f"Understanding {ch_title}",
                    f"Core Concepts and Framework of {ch_title}",
                    "Practical Workflows and Real-World Examples",
                    "Actionable Exercises and Summary",
                ]

                for sec_idx, sec_title in enumerate(raw_sections):
                    clean_sec_title = clean_source_title(sec_title)
                    anchors = [VisualAnchorType.TEXT]
                    if intent.code_requirements:
                        if sec_idx % 2 == 0:
                            anchors.append(VisualAnchorType.CODE)
                        else:
                            anchors.append(VisualAnchorType.TABLE)
                    else:
                        if sec_idx == 0:
                            anchors.append(VisualAnchorType.DIAGRAM)
                        elif sec_idx == 1:
                            anchors.append(VisualAnchorType.COMPARISON)
                        elif sec_idx == 2:
                            anchors.append(VisualAnchorType.CHECKLIST if "checklist" in (intent.desired_elements or []) else VisualAnchorType.TABLE)
                        else:
                            anchors.append(VisualAnchorType.EXERCISE if "exercises" in (intent.desired_elements or []) else VisualAnchorType.TIMELINE)
                    sections.append(SectionPlan(title=clean_sec_title, visual_anchors=anchors))

                chapters.append(
                    PlannedChapter(
                        chapter_number=ch_num,
                        title=ch_title,
                        summary=gen_ch.summary,
                        icon=icon,
                        theme=theme,
                        page_budget=4,
                        sections=sections,
                        sources_to_cite=ch_sources,
                    )
                )

            if validate_chapter_progression(chapters):
                return chapters
            else:
                logger.warning("LLM chapter outline failed progression validation, falling back to deterministic.")
                return None

        except Exception as e:
            if self.settings.vasukisquare_mock_mode:
                logger.warning(f"LLM chapter outline generation failed in mock mode, falling back to heuristic: {e}")
                return None
            raise GroqGenerationError(f"Chapter planning failed via Groq: {e}") from e

    def _build_deterministic_chapters(
        self,
        title: str,
        intent: BookIntent,
        corpus: Optional[ResearchCorpus] = None,
        chapter_count: Optional[int] = None,
    ) -> List[PlannedChapter]:
        """Generate structured chapter definitions tailored to the topic domain."""
        t_lower = title.lower()
        p_lang = (intent.primary_programming_language or "").lower()

        # Domain 1: Habits / Personal Development / Productivity (Non-technical)
        if any(w in t_lower for w in ["habit", "routine", "productivity", "mindset", "discipline", "daily", "life", "health", "time management", "goal"]):
            chapter_topics = [
                ("The Science & Psychology of Habit Formation", "Understanding the habit loop: cue, craving, response, and reward with cognitive neuroscience insights.", "sparkles", [
                    SectionPlan(title="The Habit Loop: Cue, Routine & Reward", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Identity-Based Habits vs Outcome Goals", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TEXT]),
                    SectionPlan(title="The Cognitive Energy Equation & Willpower Limits", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="Foundational Mindset & Self-Assessment", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.QUOTE]),
                ]),
                ("Designing Micro-Habits & Daily Environmental Cues", "Strategies for habit stacking, friction reduction, environmental design, and starting absurdly small.", "compass", [
                    SectionPlan(title="The 2-Minute Rule & Micro-Commitments", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Environmental Architecture: Cues That Work", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Habit Stacking & Trigger Sequencing", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Daily Routine Design Worksheet", visual_anchors=[VisualAnchorType.EXERCISE, VisualAnchorType.CHECKLIST]),
                ]),
                ("Overcoming Resistance, Plateaus & Breaking Bad Habits", "Inverting the habit loop to dissolve destructive patterns, resist temptation, and recover from slip-ups.", "shield-check", [
                    SectionPlan(title="Deconstructing Bad Habits: Root Cause Inversion", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TEXT]),
                    SectionPlan(title="Overcoming the Valley of Disappointment", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.QUOTE]),
                    SectionPlan(title="The Never Miss Twice Recovery Protocol", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.TABLE]),
                    SectionPlan(title="Coping with Plateaus, Stress & Burnout", visual_anchors=[VisualAnchorType.TEXT, VisualAnchorType.EXERCISE]),
                ]),
                ("Tracking Systems, Accountability & Measurable Progress", "Using habit scorecards, visual trackers, accountability partners, and positive reinforcement loops.", "layers", [
                    SectionPlan(title="Visual Tracking: The Power of the Streak", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.TEXT]),
                    SectionPlan(title="Accountability Systems & Social Contracts", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Weekly Review Cadence & Habit Audits", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.TIMELINE]),
                    SectionPlan(title="Metrics That Matter vs Vanity Tracking", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                ]),
                ("The 30-Day Practical Habit Action Plan", "A structured day-by-day implementation roadmap to lock in sustainable compounding behaviors.", "zap", [
                    SectionPlan(title="Phase 1 (Days 1–10): Establishing the Micro-Foundation", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.CHECKLIST]),
                    SectionPlan(title="Phase 2 (Days 11–20): Overcoming Resistance & Reinforcing", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.EXERCISE]),
                    SectionPlan(title="Phase 3 (Days 21–30): Automation & Compounding Gains", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="30-Day Completion Audit & Milestone Review", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.QUOTE]),
                ]),
                ("Long-Term Sustainability, Mastery & Continuous Evolution", "Evolving routines through life transitions, preventing habit decay, and lifelong compounding.", "book-open", [
                    SectionPlan(title="Upgrading Habits as Your Life Evolves", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Avoiding Rigidity: Flexible Habit Systems", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Mastery Through Deliberate Compounding", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.TABLE]),
                    SectionPlan(title="Lifelong Habit Maintenance Checklist", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.TEXT]),
                ]),
            ]
        # Domain 2: Python for Beginners / Zero to Real Programs (Comprehensive 10-Chapter Curriculum)
        elif "python" in t_lower or p_lang == "python":
            chapter_topics = [
                ("Introduction to Python & Setting Up Your Environment", "Understanding the Python interpreter, installing Python 3, running scripts vs interactive REPL, and code editors.", "terminal", [
                    SectionPlan(title="Why Python & How the Interpreter Executes Code", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Installation, Tooling & Your First 'Hello World' Script", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Interactive REPL vs Running .py Files", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Syntax Fundamentals, Indentation & Beginner Errors", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                ]),
                ("Variables, Data Types & Core Operators", "Understanding dynamic typing, strings, integers, floats, booleans, arithmetic and comparison operators.", "code", [
                    SectionPlan(title="Primitive Data Types & Type Conversion Functions", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="String Manipulation, Concatenation & Formatted f-strings", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Numeric Calculations & Arithmetic Operators", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.CODE]),
                    SectionPlan(title="Boolean Logic, Comparison & Logical Operators", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TEXT]),
                ]),
                ("User Input, Output Formatting & Conditions", "Taking interactive user input, formatting console output, and branching execution with if-elif-else statements.", "layers", [
                    SectionPlan(title="Capturing Input with input() and Casting Types", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Branching Decisions with if, elif, and else", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Nested Conditions & Compound Boolean Expressions", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Common Beginner Branching Pitfalls & Fixes", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Loops & Iteration Control", "Mastering for loops, while loops, the range() function, break, continue, and loop patterns.", "cpu", [
                    SectionPlan(title="Iterating with for Loops and the range() Builtin", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="While Loops & State-Controlled Iteration", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Loop Control Statements: break, continue, and pass", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Avoiding Infinite Loops & Nested Iteration Patterns", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Functions, Scope & Modular Code", "Defining reusable functions, parameters, return values, default arguments, and local vs global variable scope.", "zap", [
                    SectionPlan(title="Defining Functions, Parameters & Return Values", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Positional Arguments, Keyword Arguments & Defaults", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Variable Scope: Local vs Global Variables", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Writing Clean Code: Docstrings & Type Annotations", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                ]),
                ("Collections: Lists, Tuples, Dictionaries & Sets", "Organizing structured data with lists, immutable tuples, key-value dictionaries, and unique sets.", "database", [
                    SectionPlan(title="Lists: Indexing, Slicing, and In-Place Methods", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.CODE]),
                    SectionPlan(title="Tuples & Immutability Patterns", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.CODE]),
                    SectionPlan(title="Dictionaries: Key-Value Mapping & Iteration", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="Sets & List Comprehensions for Data Transformation", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.COMPARISON]),
                ]),
                ("Error Handling & File Operations", "Defensive programming with try-except-finally blocks and persistent storage using file context managers.", "shield-check", [
                    SectionPlan(title="Exception Handling with try, except, and finally", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Reading and Writing Text Files with Context Managers", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Structured File I/O: Handling JSON and CSV Data", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Defensive Coding Practices & Catching Specific Errors", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                ]),
                ("Object-Oriented Programming Fundamentals", "Understanding classes, objects, the __init__ constructor, instance methods, and attributes.", "layers", [
                    SectionPlan(title="Classes, Instances & The __init__ Constructor", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Defining Methods & Working with self", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Encapsulation & Basic Class Inheritance", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="OOP vs Procedural Design Trade-offs", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TEXT]),
                ]),
                ("Capstone Mini-Project: Building a Complete Application", "Step-by-step construction of a real-world CLI expense and task tracker combining all concepts.", "sparkles", [
                    SectionPlan(title="Project Architecture & Data Model Design", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Implementing Core Business Logic & File Storage", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Building the Interactive Menu & User Flow", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Complete Runnable Code & Testing the Application", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                ]),
                ("Standard Library, Packages & Next Steps", "Exploring Python's standard library modules, pip package management, virtual environments, and PEP 8 style.", "compass", [
                    SectionPlan(title="Essential Built-in Modules: math, random, datetime, os", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Virtual Environments and Installing Packages with pip", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="PEP 8 Style Guide & Clean Code Principles", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Continuous Learning Roadmap: Projects & Ecosystem", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                ]),
            ]
        # Domain 3: Distributed Systems / Databases
        elif any(w in t_lower for w in ["database", "distributed", "raft", "storage", "consensus", "kv"]):
            chapter_topics = [
                ("Foundations of Distributed Storage Systems", "Theoretical baselines, consistency models, and the evolution of data architectures.", "sparkles", [
                    SectionPlan(title="CAP Theorem & Consistency Spectrum", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Partitioning & Consistent Hashing", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Vector Clocks & Causal Ordering", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Replication Strategies: Active vs Passive", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                ]),
                ("Consensus Protocols & State Machine Replication", "Raft, Paxos, and leader election mechanisms under network partitions.", "cpu", [
                    SectionPlan(title="Quorum Verification & Term Transitions", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Log Replication & Commit Invariants", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="Joint Consensus & Cluster Membership Changes", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Snapshotting & Log Compaction Mechanics", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.DIAGRAM]),
                ]),
                ("Storage Engine Internals: B+ Trees vs LSM-Trees", "Data structures for persistent storage, write-ahead logging, and tiered compaction.", "database", [
                    SectionPlan(title="B+ Tree Page Management & In-Place Updates", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TEXT]),
                    SectionPlan(title="LSM-Tree MemTable Ingestion & SSTable Compaction", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Write-Ahead Logging & Crash Recovery Protocols", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Bloom Filters & Block Indexing Accelerators", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.CODE]),
                ]),
                ("Concurrency Control & Isolation Levels", "Multi-Version Concurrency Control (MVCC), 2-Phase Locking, and serializable transactions.", "layers", [
                    SectionPlan(title="Snapshot Isolation & Read Views", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Deadlock Detection & Resolution Strategies", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Two-Phase Commit & Distributed Transactions", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Optimistic vs Pessimistic Concurrency Trade-offs", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                ]),
                ("Performance Benchmarks & Architectural Trade-offs", "Empirical evaluations of throughput, tail latency, and hardware tiering.", "sparkles", [
                    SectionPlan(title="Ingestion Throughput & Latency Profiles", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.COMPARISON]),
                    SectionPlan(title="Hardware Offloading & NVMe Tiering", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Tail Latency Mitigation & Read Amplification", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="System Architecture Decision Matrix", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Production Reliability & Operational Best Practices", "Scaling distributed clusters, chaos testing, monitoring, and real-world post-mortems.", "compass", [
                    SectionPlan(title="Observability, Replica Drift & Alerting", visual_anchors=[VisualAnchorType.QUOTE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Incident Retrospective & Disaster Recovery", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Chaos Engineering & Fault Injection", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Production Readiness Checklist & Runbooks", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                ]),
            ]
        # Domain 4: General Non-technical
        elif not intent.is_technical:
            words = [w.capitalize() for w in title.replace(":", " ").replace("-", " ").split() if len(w) > 2]
            key_subject = " ".join(words[:4]) if words else title

            chapter_topics = [
                (f"Core Principles & Mental Models of {key_subject}", "Fundamental principles, cognitive frameworks, and orientation.", "sparkles", [
                    SectionPlan(title="Core Concepts & Definitions", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Guiding Principles & Frameworks", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Key Mindsets & Common Misconceptions", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Self-Assessment & Baseline Diagnostic", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.TEXT]),
                ]),
                ("Practical Strategies & Actionable Methods", "Step-by-step techniques, workflows, and implementation strategies.", "compass", [
                    SectionPlan(title="Primary Frameworks in Practice", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Step-by-Step Implementation Guide", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Actionable Exercises & Worksheets", visual_anchors=[VisualAnchorType.EXERCISE, VisualAnchorType.CHECKLIST]),
                    SectionPlan(title="Optimizing Your Daily Workflow", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.TABLE]),
                ]),
                ("Navigating Challenges, Pitfalls & Solutions", "Analyzing common bottlenecks, mitigating obstacles, and resilient problem-solving.", "shield-check", [
                    SectionPlan(title="Most Common Mistakes & How to Avoid Them", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                    SectionPlan(title="Troubleshooting & Resilience Strategies", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Real-World Case Studies & Lessons Learned", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Diagnostic Checklist for Plateaus", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.TABLE]),
                ]),
                ("Frameworks for Measurement & Continuous Progress", "Tracking results, performance indicators, and iterative improvements.", "layers", [
                    SectionPlan(title="Key Performance Metrics & Tracking", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.TABLE]),
                    SectionPlan(title="Review Cadence & Feedback Loops", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Comparative Analysis & Benchmarks", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Continuous Improvement Checklist", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.TEXT]),
                ]),
                ("The Step-by-Step Implementation Roadmap", "Structured execution plan and milestone-based progression.", "zap", [
                    SectionPlan(title="Phase 1: Foundation & Quick Wins", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.CHECKLIST]),
                    SectionPlan(title="Phase 2: Deepening the Practice", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.EXERCISE]),
                    SectionPlan(title="Phase 3: Scaling & Integration", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="Milestone Evaluation & Scorecard", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.QUOTE]),
                ]),
                ("Long-Term Mastery & Strategic Outlook", "Sustaining success, adapting to change, and long-term vision.", "book-open", [
                    SectionPlan(title="Sustaining Long-Term Momentum", visual_anchors=[VisualAnchorType.QUOTE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Advanced Strategies for Mastery", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Future Trends & Ongoing Evolution", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Mastery Checklist & Next Steps", visual_anchors=[VisualAnchorType.CHECKLIST, VisualAnchorType.TEXT]),
                ]),
            ]
        # Domain 5: General Technical & Software Engineering
        else:
            words = [w.capitalize() for w in title.replace(":", " ").replace("-", " ").split() if len(w) > 2]
            key_subject = " ".join(words[:4]) if words else title

            chapter_topics = [
                (f"Foundations & Core Principles of {key_subject}", "Fundamental concepts, historical context, and mental models.", "sparkles", [
                    SectionPlan(title="Historical Context & Core Terminology", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Guiding Principles & System Philosophy", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Core Mental Models & Abstractions", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Prerequisites & Environmental Setup", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Core Architecture & Component Models", "Structural components, lifecycle mechanics, and interaction patterns.", "cpu", [
                    SectionPlan(title="System Topology & Component Topology", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Data Flow & Interaction Lifecycles", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="State Management & Coordination", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="Interface Contracts & Protocol Design", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.CODE]),
                ]),
                ("Implementation Patterns & Practical Techniques", "Real-world engineering patterns, idiomatic implementations, and code structures.", "code", [
                    SectionPlan(title="Reference Implementation Patterns", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Developer Workflows & Tooling", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Error Handling & Resilience Patterns", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Testing Strategies & Quality Assurance", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.CODE]),
                ]),
                ("Performance, Scalability & Trade-offs", "Quantitative evaluations, bottleneck analysis, and optimization strategies.", "layers", [
                    SectionPlan(title="Throughput & Efficiency Benchmarks", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.COMPARISON]),
                    SectionPlan(title="Trade-off Matrix & Decision Trees", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                    SectionPlan(title="Profiling, Bottleneck Detection & Tuning", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Resource Allocation & Scaling Dynamics", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.TABLE]),
                ]),
                ("Production Best Practices & Case Studies", "Operational readiness, security patterns, and real-world lessons learned.", "database", [
                    SectionPlan(title="Security & Resilience Patterns", visual_anchors=[VisualAnchorType.QUOTE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Real-World Deployment Case Study", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Monitoring, Telemetry & SRE Runbooks", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TABLE]),
                    SectionPlan(title="Post-Mortem Lessons & Anti-Patterns", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Emerging Trends & Future Outlook", "Next-generation paradigms, ecosystem evolution, and forward-looking recommendations.", "compass", [
                    SectionPlan(title="Horizon Technologies & Evolution", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Strategic Recommendations", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Ecosystem Tooling & Community Direction", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Continuous Learning & Mastery Roadmap", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                ]),
            ]

        desired_count = chapter_count or intent.chapter_count
        count = max(1, desired_count)

        source_urls = [d.url for d in corpus.documents] if corpus else []
        chapters: List[PlannedChapter] = []

        for i in range(count):
            ch_num = i + 1
            ch_title, ch_summary, default_icon, sections = chapter_topics[i % len(chapter_topics)]
            icon = default_icon if default_icon in MOTIF_ICONS else MOTIF_ICONS[i % len(MOTIF_ICONS)]
            theme = get_chapter_theme(ch_num)
            ch_sources = source_urls[i * 2 : (i + 1) * 2] if source_urls else []

            chapters.append(
                PlannedChapter(
                    chapter_number=ch_num,
                    title=clean_source_title(ch_title),
                    summary=ch_summary,
                    icon=icon,
                    theme=theme,
                    page_budget=4,
                    sections=sections,
                    sources_to_cite=ch_sources,
                )
            )

        return chapters

    @staticmethod
    def calculate_adaptive_chapter_count(target_pages: int) -> int:
        """Calculate the ideal chapter count so that every chapter has an opener and adequate content pages,
        while keeping the total physical page count close to target_pages."""
        if target_pages <= 12:
            return 1
        elif target_pages <= 18:
            return 2
        elif target_pages <= 26:
            return 3
        elif target_pages <= 35:
            return 4
        elif target_pages <= 50:
            return 6
        elif target_pages <= 80:
            return 8
        elif target_pages <= 100:
            return 10
        else:
            return min(12, max(8, target_pages // 10))

    def _assemble_pages(
        self,
        book_title: str,
        chapters: List[PlannedChapter],
        target_total_pages: int = 40,
        intent: Optional[BookIntent] = None,
    ) -> tuple[List[PlannedPage], List[PlannedPage], List[PlannedPage]]:
        """Pre-allocate all book pages with strict sequential page numbering, exact target budgeting, and explicit PagePurpose."""
        frontmatter: List[PlannedPage] = []
        backmatter: List[PlannedPage] = []
        all_pages: List[PlannedPage] = []
        curr_page_num = 1

        is_technical = intent.is_technical if intent else False

        # 1. Frontmatter
        # Page 1: Cover (always physical page 1)
        p_cover = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.DARK,
            brief="High-impact visual book cover.",
            page_purpose=PagePurpose(
                page_type="frontmatter",
                learning_goal="Visual book cover and title presentation.",
                forbidden_components=["step", "code", "terminal", "table"],
            ),
        )
        frontmatter.append(p_cover)
        all_pages.append(p_cover)
        curr_page_num += 1

        if target_total_pages <= 12:
            # Short-Book Mode: Single consolidated TOC & Imprint frontmatter page
            p_toc = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.TOC.value,
                layout=LayoutType.TOC.value,
                theme=Theme.LIGHT,
                brief="Table of contents & publication imprint.",
                page_purpose=PagePurpose(
                    page_type="frontmatter",
                    learning_goal="Overview of book structure, navigation, and publication imprint.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            frontmatter.append(p_toc)
            all_pages.append(p_toc)
            curr_page_num += 1
        elif target_total_pages <= 16:
            p_title = PlannedPage(
                page_number=curr_page_num,
                page_type="imprint",
                layout=LayoutType.TEXT_HEAVY.value,
                theme=Theme.LIGHT,
                brief="Title, publisher imprint, and copyright notice.",
                page_purpose=PagePurpose(
                    page_type="frontmatter",
                    learning_goal="Imprint and publication metadata.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            frontmatter.append(p_title)
            all_pages.append(p_title)
            curr_page_num += 1

            p_toc = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.TOC.value,
                layout=LayoutType.TOC.value,
                theme=Theme.LIGHT,
                brief="Table of contents.",
                page_purpose=PagePurpose(
                    page_type="frontmatter",
                    learning_goal="Overview of book structure and navigation.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            frontmatter.append(p_toc)
            all_pages.append(p_toc)
            curr_page_num += 1
        else:
            p_imprint = PlannedPage(
                page_number=curr_page_num,
                page_type="imprint",
                layout=LayoutType.TEXT_HEAVY.value,
                theme=Theme.LIGHT,
                brief="Half-title and publisher imprint.",
                page_purpose=PagePurpose(
                    page_type="frontmatter",
                    learning_goal="Imprint and publication metadata.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            frontmatter.append(p_imprint)
            all_pages.append(p_imprint)
            curr_page_num += 1

            p_copyright = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.COPYRIGHT.value,
                layout=LayoutType.COPYRIGHT.value,
                theme=Theme.LIGHT,
                brief="Copyright notice, versioning, and legal disclaimer.",
                page_purpose=PagePurpose(
                    page_type="frontmatter",
                    learning_goal="Legal and copyright documentation.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            frontmatter.append(p_copyright)
            all_pages.append(p_copyright)
            curr_page_num += 1

            p_toc = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.TOC.value,
                layout=LayoutType.TOC.value,
                theme=Theme.LIGHT,
                brief="Complete structured table of contents.",
                page_purpose=PagePurpose(
                    page_type="frontmatter",
                    learning_goal="Table of contents navigation.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            frontmatter.append(p_toc)
            all_pages.append(p_toc)
            curr_page_num += 1

        if target_total_pages <= 12:
            backmatter_count = 1
        elif target_total_pages <= 24:
            backmatter_count = 2
        else:
            backmatter_count = 3

        # 2. Proportional Page Budgeting for Chapters
        structural_pages = len(all_pages) + backmatter_count + len(chapters)
        available_content_pages = max(len(chapters), target_total_pages - structural_pages)

        num_chapters = len(chapters)
        
        weights = []
        is_conclusion_list = []
        for i, ch in enumerate(chapters):
            t_lower = ch.title.lower()
            is_last = (i == num_chapters - 1)
            is_conclusion_title = any(w in t_lower for w in ["conclusion", "next step", "summary", "future outlook", "emerging trend", "roadmap", "wrap up"])
            is_conc = is_last or is_conclusion_title
            is_conclusion_list.append(is_conc)
            
            if is_conc and num_chapters > 2:
                w = 1.0
            else:
                num_sec = len(ch.sections) if ch.sections else 3
                has_code = any(VisualAnchorType.CODE in s.visual_anchors for s in ch.sections) if ch.sections else False
                has_diag = any(VisualAnchorType.DIAGRAM in s.visual_anchors for s in ch.sections) if ch.sections else False
                w = float(num_sec)
                if has_code:
                    w += 1.5
                if has_diag:
                    w += 1.0
            weights.append(w)

        allocated_content = [1] * num_chapters
        remaining_pages = max(0, available_content_pages - num_chapters)

        conclusion_caps = {}
        for i in range(num_chapters):
            if is_conclusion_list[i] and num_chapters > 2:
                conclusion_caps[i] = 2
            else:
                conclusion_caps[i] = 9999

        while remaining_pages > 0:
            eligible = [i for i in range(num_chapters) if allocated_content[i] < conclusion_caps[i]]
            if not eligible:
                eligible = list(range(num_chapters))
            
            best_ch = max(eligible, key=lambda idx: weights[idx] / (allocated_content[idx] + 0.5))
            allocated_content[best_ch] += 1
            remaining_pages -= 1

        for i, ch in enumerate(chapters):
            ch.page_budget = 1 + allocated_content[i]

        # 3. Chapters
        for ch in chapters:
            p_opener = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.CHAPTER_OPENER.value,
                layout=LayoutType.CHAPTER_OPENER.value,
                chapter_number=ch.chapter_number,
                chapter_title=ch.title,
                theme=ch.theme,
                icon=ch.icon,
                brief=f"Chapter {ch.chapter_number} Opener: Lucide icon, number, and title only.",
                page_purpose=PagePurpose(
                    page_type="chapter_opener",
                    learning_goal=f"Introduce Chapter {ch.chapter_number}: {ch.title}",
                    forbidden_components=["step", "code", "terminal", "table", "callout", "quote"],
                ),
            )
            all_pages.append(p_opener)
            curr_page_num += 1

            content_page_count = ch.page_budget - 1
            for cp_idx in range(content_page_count):
                if ch.sections and cp_idx < len(ch.sections):
                    sec = ch.sections[cp_idx]
                    anchor = sec.visual_anchors[0] if sec.visual_anchors else VisualAnchorType.TEXT
                    brief_text = sec.title
                else:
                    sec_idx = cp_idx % len(ch.sections) if ch.sections else 0
                    sec = ch.sections[sec_idx] if ch.sections else None
                    anchor = sec.visual_anchors[cp_idx % len(sec.visual_anchors)] if sec and sec.visual_anchors else VisualAnchorType.TEXT
                    subtopic_suffixes = ["Advanced Nuances & Mechanics", "Practical Patterns & Edge Cases", "Architecture & Real-World Usage"]
                    suffix = subtopic_suffixes[(cp_idx - (len(ch.sections) if ch.sections else 0)) % len(subtopic_suffixes)]
                    brief_text = f"{sec.title}: {suffix}" if sec else f"{ch.title} In-Depth Exploration"

                layout_type = LayoutType.EDITORIAL.value
                req_components = ["explanation"]
                forb_components = ["step"]
                is_hands_on = False
                page_archetype = "concept"
                type_enum = TechnicalPageType.CONCEPT

                brief_l = brief_text.lower()
                ch_l = ch.title.lower()

                if "history" in brief_l or "origin" in brief_l or "evolution" in brief_l:
                    page_archetype = "history"
                    type_enum = TechnicalPageType.HISTORY
                    layout_type = LayoutType.TIMELINE.value
                    req_components = ["explanation", "timeline", "callout"]
                elif "features" in brief_l or "benefits" in brief_l or "advantages" in brief_l or "why python" in brief_l:
                    page_archetype = "features"
                    type_enum = TechnicalPageType.FEATURES
                    layout_type = LayoutType.COMPARISON.value
                    req_components = ["explanation", "table", "code", "callout"]
                elif "capstone" in ch_l or "project" in ch_l or "project" in brief_l:
                    page_archetype = "mini_project"
                    type_enum = TechnicalPageType.MINI_PROJECT
                    layout_type = LayoutType.CODE_FOCUS.value
                    req_components = ["explanation", "code", "output"]
                    is_hands_on = True
                elif "setup" in brief_l or "install" in brief_l or "environment" in brief_l:
                    page_archetype = "procedure_setup"
                    type_enum = TechnicalPageType.PROCEDURE_SETUP
                    layout_type = LayoutType.EDITORIAL.value
                    req_components = ["explanation", "terminal"]
                    forb_components = []
                    is_hands_on = True
                elif anchor == VisualAnchorType.CODE or (is_technical and cp_idx % 2 == 1):
                    page_archetype = "code_tutorial"
                    type_enum = TechnicalPageType.CODE_TUTORIAL
                    layout_type = LayoutType.CODE_FOCUS.value
                    req_components = ["explanation", "code", "output"]
                    is_hands_on = True
                elif anchor in (VisualAnchorType.COMPARISON, VisualAnchorType.TABLE):
                    page_archetype = "comparison"
                    type_enum = TechnicalPageType.COMPARISON
                    layout_type = LayoutType.COMPARISON.value
                    req_components = ["explanation", "table"]
                elif anchor == VisualAnchorType.DIAGRAM:
                    page_archetype = "concept"
                    type_enum = TechnicalPageType.CONCEPT
                    layout_type = LayoutType.DIAGRAM_FOCUS.value
                    req_components = ["explanation", "diagram"]
                elif anchor == VisualAnchorType.STATISTIC:
                    page_archetype = "concept"
                    type_enum = TechnicalPageType.CONCEPT
                    layout_type = LayoutType.LARGE_NUMBER.value
                    req_components = ["explanation", "statistic"]
                elif anchor == VisualAnchorType.QUOTE:
                    page_archetype = "concept"
                    type_enum = TechnicalPageType.CONCEPT
                    layout_type = LayoutType.QUOTE.value
                    req_components = ["explanation", "quote"]
                elif anchor == VisualAnchorType.TIMELINE:
                    page_archetype = "history"
                    type_enum = TechnicalPageType.HISTORY
                    layout_type = LayoutType.TIMELINE.value
                    req_components = ["explanation", "timeline"]
                elif anchor == VisualAnchorType.EXERCISE:
                    page_archetype = "exercise"
                    type_enum = TechnicalPageType.EXERCISE
                    layout_type = LayoutType.EDITORIAL.value
                    req_components = ["explanation", "exercise"]
                    is_hands_on = True

                type_spec = PAGE_TYPE_SPECS.get(type_enum, PAGE_TYPE_SPECS[TechnicalPageType.CONCEPT])

                p_content = PlannedPage(
                    page_number=curr_page_num,
                    page_type="chapter_content",
                    layout=layout_type,
                    chapter_number=ch.chapter_number,
                    chapter_title=ch.title,
                    theme=ch.theme,
                    visual_anchor=anchor,
                    brief=brief_text,
                    page_purpose=PagePurpose(
                        page_type=page_archetype,
                        learning_goal=f"Master {brief_text} in Chapter {ch.chapter_number}",
                        concepts=[brief_text],
                        required_components=req_components,
                        forbidden_components=forb_components,
                        is_hands_on=is_hands_on,
                        content_budget=type_spec.content_budget,
                        content_depth="normal",
                        minimum_content_units=type_spec.minimum_content_units,
                    ),
                )
                all_pages.append(p_content)
                curr_page_num += 1

        # 4. Backmatter
        p_refs = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.REFERENCES.value,
            layout=LayoutType.REFERENCES.value,
            theme=Theme.LIGHT,
            brief="Comprehensive bibliography and primary source citations.",
            page_purpose=PagePurpose(
                page_type="backmatter",
                learning_goal="Bibliography and official documentation references.",
                forbidden_components=["step", "code", "terminal"],
            ),
        )
        backmatter.append(p_refs)
        all_pages.append(p_refs)
        curr_page_num += 1

        if backmatter_count >= 3:
            p_ack = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.ACKNOWLEDGEMENT.value,
                layout=LayoutType.ACKNOWLEDGEMENT.value,
                theme=Theme.LIGHT,
                icon="heart",
                brief="Author and institutional acknowledgments.",
                page_purpose=PagePurpose(
                    page_type="backmatter",
                    learning_goal="Author and community acknowledgments.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            backmatter.append(p_ack)
            all_pages.append(p_ack)
            curr_page_num += 1

        if backmatter_count >= 2:
            p_thanks = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.THANK_YOU.value,
                layout=LayoutType.THANK_YOU.value,
                theme=Theme.DARK,
                icon="sparkles",
                brief="Concluding acknowledgments and publisher note.",
                page_purpose=PagePurpose(
                    page_type="backmatter",
                    learning_goal="Concluding reader thank you.",
                    forbidden_components=["step", "code", "terminal"],
                ),
            )
            backmatter.append(p_thanks)
            all_pages.append(p_thanks)

        # Log detailed Page Budget
        frontmatter_count_clean = len(frontmatter) - 1
        content_count = sum(ch.page_budget - 1 for ch in chapters)
        logger.info(
            f"Page Budget:\n"
            f"  Requested final pages: {target_total_pages}\n"
            f"  Cover: 1\n"
            f"  Front matter: {frontmatter_count_clean}\n"
            f"  Chapter openers: {len(chapters)}\n"
            f"  Content pages: {content_count}\n"
            f"  Back matter: {len(backmatter)}\n"
            f"  Planned total: {len(all_pages)}"
        )

        max_variance = 1 if target_total_pages <= 20 else 2
        if abs(len(all_pages) - target_total_pages) > max_variance:
            raise ValueError(
                f"Page planning error: Planned {len(all_pages)} pages for target {target_total_pages}, "
                f"which exceeds allowed variance (±{max_variance})."
            )

        return frontmatter, backmatter, all_pages

    async def generate_book_plan(
        self,
        topic: Optional[str] = None,
        intent: Optional[Union[BookIntent, str]] = None,
        corpus: Optional[ResearchCorpus] = None,
        target_pages: int = 40,
        prompt: Optional[str] = None,
        title: Optional[str] = None,
    ) -> BookPlan:
        """Create a complete editorial BookPlan from topic/prompt, intent, and research corpus."""
        actual_intent: Optional[BookIntent] = None
        if isinstance(intent, BookIntent):
            actual_intent = intent
        elif isinstance(intent, str) and prompt is None:
            prompt = intent

        effective_topic = topic or (actual_intent.topic if actual_intent else None) or prompt or "Comprehensive Guide"

        if actual_intent is None:
            actual_intent = await self.infer_intent(topic=effective_topic, prompt=prompt, title=title, target_pages=target_pages, corpus=corpus)

        book_title = actual_intent.title or clean_and_resolve_title(effective_topic, prompt=prompt, explicit_title=title)
        
        # Format subtitle
        if actual_intent.subtitle:
            subtitle = actual_intent.subtitle
        elif actual_intent.book_type == "beginner_guide":
            subtitle = "A Practical, Hands-On Guide from Zero to Mastery"
        elif actual_intent.book_type == "tutorial_manual":
            subtitle = "A Step-by-Step Developer Tutorial and Code Reference"
        elif not actual_intent.is_technical:
            subtitle = "A Practical, Step-by-Step Guide to Lasting Change"
        else:
            subtitle = f"A Definitive {actual_intent.book_type.replace('_', ' ').title()}"

        description = (
            f"An actionable, {actual_intent.technical_depth} guide tailored for {actual_intent.target_audience}, "
            f"covering foundational mental models, progressive practical implementations, and essential strategies."
        )

        frontmatter_est = 3 if target_pages <= 12 else 4
        backmatter_est = 1 if target_pages <= 12 else (2 if target_pages <= 24 else 3)
        max_possible_chapters = max(1, (target_pages - frontmatter_est - backmatter_est) // 2)
        adaptive_count = min(self.calculate_adaptive_chapter_count(target_pages), max_possible_chapters)

        if (
            actual_intent
            and actual_intent.chapter_count is not None
            and (actual_intent.target_pages is None or actual_intent.target_pages == target_pages)
            and 1 <= actual_intent.chapter_count <= max_possible_chapters
        ):
            calculated_chapter_count = actual_intent.chapter_count
        else:
            calculated_chapter_count = adaptive_count

        if actual_intent:
            actual_intent.target_pages = target_pages
            actual_intent.chapter_count = calculated_chapter_count

        chapters = await self._plan_chapters_with_llm(book_title, actual_intent, corpus, calculated_chapter_count)

        if not chapters:
            chapters = self._build_deterministic_chapters(book_title, actual_intent, corpus, calculated_chapter_count)

        frontmatter, backmatter, all_pages = self._assemble_pages(book_title, chapters, target_total_pages=target_pages, intent=actual_intent)

        # Build coverage matrix and log diagnostic metrics
        coverage = build_requirement_coverage_matrix(actual_intent, chapters, all_pages)

        plan = BookPlan(
            title=book_title,
            subtitle=subtitle,
            description=description,
            intent=actual_intent,
            frontmatter_pages=frontmatter,
            chapters=chapters,
            backmatter_pages=backmatter,
            all_planned_pages=all_pages,
            total_pages=len(all_pages),
        )

        log_plan_diagnostics(plan, coverage)
        return plan
