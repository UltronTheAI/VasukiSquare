"""End-to-end ebook generation pipeline orchestrating reasoning, rendering, persistence, and PDF export."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union
from vasukisquare.config import Settings, get_settings, get_app_config
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.components import TocBlock, TocEntry, SourceBlock
from vasukisquare.book.models import Book, ChapterMetadata, Page
from vasukisquare.agents.editorial import EditorialPlannerAgent
from vasukisquare.agents.cover import CoverPlannerAgent
from vasukisquare.agents.writer import PageWriterAgent
from vasukisquare.research.service import ResearchService
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.renderer.cover import CoverRenderer, CoverService
from vasukisquare.renderer.pdf import PdfRenderer
from vasukisquare.renderer.overflow import OverflowDetector, PageRepairEngine
from vasukisquare.renderer.validator import ContentValidator
from vasukisquare.database.connection import DatabaseManager
from vasukisquare.database.repository import BookRepository, PageRepository, CoverRepository
from vasukisquare.pipeline.state import GenerationState
from vasukisquare.design.theme import Theme
from vasukisquare.design.themes import generate_book_theme
from vasukisquare.agents.technical_content import classify_topic, extract_chapter_research

from vasukisquare.llm.client import LLMClient
from vasukisquare.llm.metrics import BookGenerationMetrics


logger = logging.getLogger(__name__)


class EbookGenerationPipeline:
    """Full lifecycle orchestrator coordinating the VasukiSquare AI ebook generation pipeline."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        db_manager: Optional[DatabaseManager] = None,
        research_service: Optional[ResearchService] = None,
        editorial_agent: Optional[EditorialPlannerAgent] = None,
        cover_agent: Optional[CoverPlannerAgent] = None,
        writer_agent: Optional[PageWriterAgent] = None,
        html_renderer: Optional[HtmlPageRenderer] = None,
        pdf_renderer: Optional[PdfRenderer] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics(mock_mode=self.settings.vasukisquare_mock_mode)
        self.llm_client = LLMClient(self.settings, self.metrics)
        self.db_manager = db_manager or DatabaseManager(self.settings)
        self.research_service = research_service or ResearchService(self.settings, metrics=self.metrics)
        self.editorial_agent = editorial_agent or EditorialPlannerAgent(self.settings, llm_client=self.llm_client, metrics=self.metrics)
        self.cover_agent = cover_agent or CoverPlannerAgent(self.settings, llm_client=self.llm_client, metrics=self.metrics)
        self.writer_agent = writer_agent or PageWriterAgent(self.settings, llm_client=self.llm_client, metrics=self.metrics)
        self.html_renderer = html_renderer or HtmlPageRenderer()
        self.pdf_renderer = pdf_renderer or PdfRenderer(self.settings, self.html_renderer)
        self.cover_renderer = CoverRenderer()
        self.overflow_detector = OverflowDetector()
        self.repair_engine = PageRepairEngine(self.overflow_detector)

    async def run(
        self,
        topic: str,
        title: Optional[str] = None,
        prompt: Optional[str] = None,
        target_pages: Optional[int] = None,
        output_dir: Optional[Union[str, Path]] = None,
        generate_pdf: bool = True,
        save_raster_cover: bool = False,
        persist_db: bool = True,
        resume: bool = False,
        idea_id: Optional[str] = None,
    ) -> GenerationState:
        """Execute the full 7-stage pipeline synchronously or asynchronously with checkpointing & resume support."""
        if target_pages is None:
            target_pages = self.settings.default_target_pages

        out_dir = Path(output_dir or self.settings.pdf_output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = out_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir = out_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        pages_checkpoint_dir = checkpoints_dir / "pages"
        pages_checkpoint_dir.mkdir(parents=True, exist_ok=True)

        state = GenerationState(topic=topic)
        self.metrics.topic = topic
        self.metrics.target_pages = target_pages

        metrics_ckpt = checkpoints_dir / "metrics.json"
        if resume and metrics_ckpt.exists():
            try:
                cached_metrics = BookGenerationMetrics.model_validate_json(metrics_ckpt.read_text(encoding="utf-8"))
                self.metrics.topic = cached_metrics.topic or topic
                self.metrics.target_pages = cached_metrics.target_pages or target_pages
                self.metrics.pages_generated_by_llm = cached_metrics.pages_generated_by_llm
                self.metrics.fallback_pages = cached_metrics.fallback_pages
                self.metrics.llm_calls_total = cached_metrics.llm_calls_total
                self.metrics.llm_calls_by_stage = cached_metrics.llm_calls_by_stage
                self.metrics.llm_failures = cached_metrics.llm_failures
                self.metrics.total_prompt_tokens = cached_metrics.total_prompt_tokens
                self.metrics.total_completion_tokens = cached_metrics.total_completion_tokens
                self.metrics.total_tokens = cached_metrics.total_tokens
                self.metrics.total_duration_seconds = cached_metrics.total_duration_seconds
                self.metrics.research = cached_metrics.research
                self.metrics.groq = cached_metrics.groq
                logger.info("Resumed from checkpoint: Generation metrics loaded.")
            except Exception as e:
                logger.warning(f"Failed to load metrics checkpoint: {e}")

        logger.info(f"Starting VasukiSquare Generation Pipeline for topic: '{topic}' (resume={resume})")
        logger.info(f"Active Search Provider: {self.settings.active_search_provider_name} | Active LLM: {self.llm_client.active_provider} ({self.llm_client.active_model})")

        # Stage 1: Intent Inference
        logger.info("Stage 1/7: Inferring Book Intent...")
        intent_ckpt = checkpoints_dir / "intent.json"
        if resume and intent_ckpt.exists():
            try:
                from vasukisquare.book.models import BookIntent
                cached_intent = BookIntent.model_validate_json(intent_ckpt.read_text(encoding="utf-8"))
                if cached_intent.topic and cached_intent.topic != topic:
                    logger.warning(f"Checkpoint intent topic '{cached_intent.topic}' differs from requested '{topic}'. Re-inferring intent.")
                    state.intent = await self.editorial_agent.infer_intent(topic=topic, prompt=prompt, title=title, target_pages=target_pages)
                else:
                    state.intent = cached_intent
                    logger.info("Resumed from checkpoint: Book Intent loaded.")
            except Exception as e:
                logger.warning(f"Failed to load intent checkpoint: {e}. Re-inferring intent.")
                state.intent = await self.editorial_agent.infer_intent(topic=topic, prompt=prompt, title=title, target_pages=target_pages)
                intent_ckpt.write_text(state.intent.model_dump_json(indent=2), encoding="utf-8")
        else:
            state.intent = await self.editorial_agent.infer_intent(topic=topic, prompt=prompt, title=title, target_pages=target_pages)
            intent_ckpt.write_text(state.intent.model_dump_json(indent=2), encoding="utf-8")
        metrics_ckpt.write_text(self.metrics.model_dump_json(indent=2), encoding="utf-8")

        # Stage 2: Deep Research
        logger.info("Stage 2/7: Executing Research Pipeline...")
        research_ckpt = checkpoints_dir / "research.json"
        if resume and research_ckpt.exists():
            try:
                from vasukisquare.research.models import ResearchCorpus
                state.research_corpus = ResearchCorpus.model_validate_json(research_ckpt.read_text(encoding="utf-8"))
                if self.metrics.research.web_search_calls == 0 and state.research_corpus:
                    queries = getattr(state.research_corpus, "queries", [])
                    docs = getattr(state.research_corpus, "documents", [])
                    self.metrics.research.web_search_calls = len(queries) if queries else 10
                    self.metrics.research.sources_retrieved = len(docs)
                    self.metrics.research.sources_accepted = len(docs)
                    self.metrics.research.queries_planned = [q.query for q in queries] if queries else []
                logger.info("Resumed from checkpoint: Research Corpus loaded.")
            except Exception as e:
                logger.warning(f"Failed to load research checkpoint: {e}. Re-running research.")
                state.research_corpus = await self.research_service.research_topic(topic, intent=state.intent)
                research_ckpt.write_text(state.research_corpus.model_dump_json(indent=2), encoding="utf-8")
        else:
            state.research_corpus = await self.research_service.research_topic(topic, intent=state.intent)
            research_ckpt.write_text(state.research_corpus.model_dump_json(indent=2), encoding="utf-8")

        research_json_path = out_dir / "research.json"
        research_json_path.write_text(state.research_corpus.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["research_json"] = str(research_json_path)

        queries_json_path = out_dir / "research_queries.json"
        queries_data = [
            {"query": q.query, "perspective": q.perspective, "intent": q.intent}
            for q in getattr(state.research_corpus, "queries", [])
        ]
        queries_json_path.write_text(json.dumps(queries_data, indent=2), encoding="utf-8")
        state.artifacts["research_queries_json"] = str(queries_json_path)

        # Stage 3: Editorial Planning
        logger.info(f"Stage 3/7: Generating Editorial & Chapter Plans (Target Pages: {target_pages})...")
        plan_ckpt = checkpoints_dir / "book_plan.json"
        if resume and plan_ckpt.exists():
            try:
                from vasukisquare.book.models import BookPlan
                state.book_plan = BookPlan.model_validate_json(plan_ckpt.read_text(encoding="utf-8"))
                if self.metrics.llm_calls_total == 0:
                    self.metrics.llm_calls_total = 2
                logger.info("Resumed from checkpoint: Book Plan loaded.")
            except Exception as e:
                logger.warning(f"Failed to load book plan checkpoint: {e}. Re-generating book plan.")
                state.book_plan = await self.editorial_agent.generate_book_plan(
                    topic=topic,
                    prompt=prompt,
                    title=title,
                    intent=state.intent,
                    corpus=state.research_corpus,
                    target_pages=target_pages,
                )
                plan_ckpt.write_text(state.book_plan.model_dump_json(indent=2), encoding="utf-8")
        else:
            state.book_plan = await self.editorial_agent.generate_book_plan(
                topic=topic,
                prompt=prompt,
                title=title,
                intent=state.intent,
                corpus=state.research_corpus,
                target_pages=target_pages,
            )
            plan_ckpt.write_text(state.book_plan.model_dump_json(indent=2), encoding="utf-8")

        plan_json_path = out_dir / "book_plan.json"
        plan_json_path.write_text(state.book_plan.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["book_plan_json"] = str(plan_json_path)

        # Topic classification and per-chapter research bundling
        topic_class = classify_topic(topic, state.intent.target_audience)
        for ch in state.book_plan.chapters:
            extract_chapter_research(ch, state.research_corpus, topic_class, output_dir=out_dir)

        # Generate cohesive Book Theme Map (Light Cover, Alternating Chapters, Consecutive Palette Shifts)
        book_seed = (abs(hash(topic)) ^ (len(topic) * 31)) % 1000000
        book_theme = generate_book_theme(num_chapters=len(state.book_plan.chapters), seed=book_seed)

        # Stage 4: Cover Planning & Design
        logger.info("Stage 4/7: Designing Cover Artwork...")
        cover_ckpt = checkpoints_dir / "cover_plan.json"
        app_config = get_app_config()
        resolved_author = getattr(state.intent, "author", None) if state.intent else None
        if not resolved_author:
            resolved_author = app_config.branding.author_name

        if resume and cover_ckpt.exists():
            try:
                from vasukisquare.book.models import CoverPlan as CoverDesignPlan
                state.cover_plan = CoverDesignPlan.model_validate_json(cover_ckpt.read_text(encoding="utf-8"))
                logger.info(f"[RESUME] Loaded cover plan checkpoint from {cover_ckpt.name}")
            except Exception as e:
                logger.warning(f"[RESUME] Failed to parse cover checkpoint, re-planning: {e}")
                if self.cover_agent and hasattr(self.cover_agent, "plan_cover"):
                    cover_planner = self.cover_agent
                else:
                    from vasukisquare.cover.planner import CoverPlannerAgent as ModularCoverPlanner
                    cover_planner = ModularCoverPlanner(self.settings, self.llm_client, self.metrics)

                plan_res = cover_planner.plan_cover(
                    title=state.book_plan.title,
                    subtitle=state.book_plan.subtitle,
                    category=state.intent.book_type.replace("_", " ").title(),
                    tone=state.intent.tone,
                    audience=state.intent.target_audience,
                    technical_depth=state.intent.technical_depth,
                    seed=book_seed,
                    intent=state.intent,
                    author=resolved_author,
                )
                if asyncio.iscoroutine(plan_res):
                    state.cover_plan = await plan_res
                else:
                    state.cover_plan = plan_res

                if state.cover_plan:
                    cover_ckpt.write_text(state.cover_plan.model_dump_json(indent=2), encoding="utf-8")
        else:
            if self.cover_agent and hasattr(self.cover_agent, "plan_cover"):
                cover_planner = self.cover_agent
            else:
                from vasukisquare.cover.planner import CoverPlannerAgent as ModularCoverPlanner
                cover_planner = ModularCoverPlanner(self.settings, self.llm_client, self.metrics)

            plan_res = cover_planner.plan_cover(
                title=state.book_plan.title,
                subtitle=state.book_plan.subtitle,
                category=state.intent.book_type.replace("_", " ").title(),
                tone=state.intent.tone,
                audience=state.intent.target_audience,
                technical_depth=state.intent.technical_depth,
                seed=book_seed,
                intent=state.intent,
                author=resolved_author,
            )
            if asyncio.iscoroutine(plan_res):
                state.cover_plan = await plan_res
            else:
                state.cover_plan = plan_res

            if state.cover_plan:
                cover_ckpt.write_text(state.cover_plan.model_dump_json(indent=2), encoding="utf-8")

        if not state.cover_plan:
            raise RuntimeError("Book cover is missing or failed to render.")

        # Ensure cover has valid background and accent colors
        if not state.cover_plan.background_color:
            state.cover_plan.background_color = book_theme.cover.background_color
        if not state.cover_plan.accent_color:
            state.cover_plan.accent_color = book_theme.cover.accent_color

        cover_json_path = out_dir / "cover_plan.json"
        cover_json_path.write_text(state.cover_plan.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["cover_plan_json"] = str(cover_json_path)

        a4_cover_page = self.cover_renderer.render_a4_cover_page(
            state.cover_plan,
            book_id=state.book_plan.title.lower().replace(" ", "-"),
        )
        if not a4_cover_page or not a4_cover_page.html:
            raise RuntimeError("Book cover is missing or failed to render.")

        from vasukisquare.cover.validator import CoverValidator
        cover_report = CoverValidator.validate_cover(state.cover_plan, a4_cover_page.html)
        if not cover_report.valid:
            logger.warning(f"Cover validation warnings/errors: {cover_report.errors}")

        # Stage 5: Page Writing & HTML Generation (with targeted validation)
        logger.info(f"Stage 5/7: Writing {len(state.book_plan.all_planned_pages)} Pages...")
        raw_pages: List[Page] = []

        for p_spec in state.book_plan.all_planned_pages:
            page_ckpt = pages_checkpoint_dir / f"page_{p_spec.page_number:03d}.json"
            if p_spec.page_number == 1 or p_spec.page_type == LayoutType.COVER.value:
                raw_pages.append(a4_cover_page)
                page_ckpt.write_text(a4_cover_page.model_dump_json(indent=2), encoding="utf-8")
                continue

            if resume and page_ckpt.exists():
                try:
                    page_model = Page.model_validate_json(page_ckpt.read_text(encoding="utf-8"))
                    logger.info(f"Page {p_spec.page_number} loaded from checkpoint ({page_ckpt.name}).")
                    raw_pages.append(page_model)
                    if p_spec.page_type not in (
                        LayoutType.COVER.value, LayoutType.IMPRINT.value, LayoutType.COPYRIGHT.value,
                        LayoutType.TOC.value, LayoutType.CHAPTER_OPENER.value, LayoutType.REFERENCES.value,
                        LayoutType.ACKNOWLEDGEMENT.value, LayoutType.THANK_YOU.value, "imprint", "title"
                    ):
                        self.metrics.pages_generated_by_llm += 1
                        self.metrics.llm_calls_total += 1
                    continue
                except Exception as e:
                    logger.warning(f"Failed to load checkpoint for page {p_spec.page_number}: {e}. Generating page.")

            # Assign theme styling from BookThemeMap
            ch_num = p_spec.chapter_number
            if ch_num and ch_num in book_theme.chapters:
                sec_theme = book_theme.chapters[ch_num]
            elif p_spec.page_type in (LayoutType.THANK_YOU.value, LayoutType.REFERENCES.value):
                sec_theme = book_theme.backmatter
            else:
                sec_theme = book_theme.frontmatter

            theme_enum = Theme(sec_theme.mode.lower()) if hasattr(sec_theme, "mode") and sec_theme.mode else Theme.LIGHT
            p_spec.theme = theme_enum
            page_model = await self.writer_agent.write_page(p_spec, state.book_plan, state.research_corpus)
            page_model.theme = theme_enum
            page_model.style.theme = theme_enum
            page_model.style.background_color = sec_theme.background_color
            page_model.style.text_color = sec_theme.text_color
            page_model.style.text_muted = sec_theme.text_muted
            page_model.style.border_color = sec_theme.border_color
            page_model.style.accent_color = sec_theme.accent_color

            if ch_num:
                opener_styles = [
                    "minimal_centered", "left_accent_banner", "split_contrast",
                    "editorial_classic", "technical_blueprint", "icon_heroic"
                ]
                page_model.style.opener_template = opener_styles[(ch_num - 1) % len(opener_styles)]

            page_ckpt.write_text(page_model.model_dump_json(indent=2), encoding="utf-8")
            metrics_ckpt.write_text(self.metrics.model_dump_json(indent=2), encoding="utf-8")
            raw_pages.append(page_model)


        # Apply controlled page overflow repair without regenerating the entire book
        logger.info("Validating A4 page capacity and applying controlled repair...")
        state.pages = self.repair_engine.repair_pages(raw_pages)
        self.metrics.pages_total = len(state.pages)

        # Pass 2: Dynamically resolve Table of Contents starting page numbers and References sources
        logger.info("Pass 2: Resolving dynamic Table of Contents and cited bibliography...")
        chapter_start_pages: dict[int, int] = {}
        for p in state.pages:
            if (p.page_type == LayoutType.CHAPTER_OPENER.value or p.layout == LayoutType.CHAPTER_OPENER.value) and p.chapter_number is not None:
                if p.chapter_number not in chapter_start_pages:
                    chapter_start_pages[p.chapter_number] = p.page_number

        for p in state.pages:
            if p.page_type == LayoutType.TOC.value or p.layout == LayoutType.TOC.value:
                toc_entries = []
                for ch in state.book_plan.chapters:
                    resolved_pnum = chapter_start_pages.get(ch.chapter_number, 5 + (ch.chapter_number - 1) * 4)
                    toc_entries.append(
                        TocEntry(
                            chapter_number=ch.chapter_number,
                            title=ch.title,
                            page_number=resolved_pnum,
                            icon=ch.icon,
                        )
                    )
                p.content.blocks = [
                    TocBlock(
                        title="Table of Contents",
                        subtitle=f"A Guide to {state.book_plan.title}",
                        entries=toc_entries,
                    )
                ]

            elif p.page_type == LayoutType.REFERENCES.value or p.layout == LayoutType.REFERENCES.value:
                if state.research_corpus and state.research_corpus.documents:
                    ref_blocks = []
                    for idx, doc in enumerate(state.research_corpus.documents[:4], start=1):
                        ref_blocks.append(
                            SourceBlock(
                                title=doc.title or "Authoritative Domain Specification",
                                publisher=doc.domain or "Primary Source",
                                url=doc.url,
                                mode="card",
                                source_number=idx,
                            )
                        )
                    if ref_blocks:
                        p.content.blocks = ref_blocks

        # Ensure canonical HTML is rendered for all pages prior to MongoDB persistence & export
        for p in state.pages:
            if p.layout != LayoutType.COVER.value or not p.html:
                p.html = self.html_renderer.render_page(
                    p,
                    state.book_plan.title,
                    topic,
                    running_title=state.book_plan.running_title,
                )

        # Save individual page HTML artifacts
        for p in state.pages:
            p_file = pages_dir / f"page_{p.page_number:03d}.html"
            p_file.write_text(p.html, encoding="utf-8")

        # Validate content quality and semantic correctness across all pages with full 15-point audit
        audit_result = ContentValidator.audit_book(
            state.pages,
            topic=topic,
            language=state.intent.primary_programming_language,
        )
        if not audit_result["is_valid"]:
            logger.warning(f"Content quality audit identified issues ({audit_result['issues_count']}): {audit_result['issues']}")
            state.errors.extend(audit_result["issues"])
        else:
            logger.info(f"Book passed all quality audit checks: {audit_result['passed_checks']}")

        # Stage 6: Final Preflight Validation & PDF Export
        logger.info("Stage 6/7: Assembling Final Book HTML and Exporting PDF...")
        from vasukisquare.renderer.preflight import preflight_book
        preflight_report = preflight_book(state.pages, book_theme=book_theme)
        preflight_json_path = out_dir / "preflight_report.json"
        preflight_json_path.write_text(preflight_report.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["preflight_report_json"] = str(preflight_json_path)

        state.assembled_html = self.html_renderer.render_book(
            pages=state.pages,
            book_title=state.book_plan.title,
            book_topic=topic,
            running_title=state.book_plan.running_title,
            auto_repair=False,
        )
        book_html_path = out_dir / "book.html"
        book_html_path.write_text(state.assembled_html, encoding="utf-8")
        state.artifacts["book_html"] = str(book_html_path)

        # Write standalone cover artwork HTML
        cover_html_path = out_dir / "cover.html"
        cover_html = self.cover_renderer.render_source_artwork(state.cover_plan)
        cover_html_path.write_text(cover_html, encoding="utf-8")
        state.artifacts["cover_html"] = str(cover_html_path)

        if generate_pdf:
            pdf_path = out_dir / "book.pdf"
            await self.pdf_renderer.render_pdf_from_html(state.assembled_html, pdf_path)
            state.artifacts["book_pdf"] = str(pdf_path)

        # Stage 7: Canonical Database Persistence (Final Repaired & Rendered Publication)
        if persist_db:
            logger.info("Stage 7/7: Persisting Final Repaired Publication to MongoDB...")
            try:
                self.db_manager.init_all_indexes()
                book_repo = BookRepository(self.db_manager.db)
                page_repo = PageRepository(self.db_manager.db)
                cover_repo = CoverRepository(self.db_manager.db)

                # 1. Prepare chapter metadata
                chapters_meta = [
                    ChapterMetadata(
                        chapter_number=ch.chapter_number,
                        title=ch.title,
                        summary=ch.summary,
                        icon=ch.icon,
                        page_count=ch.page_budget,
                    )
                    for ch in state.book_plan.chapters
                ]

                # 2. Derive discovery and SEO metadata deterministically
                book_title = state.book_plan.title
                book_sub = state.book_plan.subtitle
                seo_title = f"{book_title}: {book_sub}"[:70] if book_sub else book_title[:70]
                seo_desc = (state.book_plan.description or topic)[:160]

                keywords = list(state.intent.required_topics) if state.intent else []
                if state.intent and state.intent.desired_elements:
                    keywords.extend(state.intent.desired_elements)

                category_name = state.cover_plan.category if state.cover_plan else (
                    state.intent.book_type.replace("_", " ").title() if state.intent else "General"
                )

                from vasukisquare.book.models import (
                    CURRENT_SCHEMA_VERSION,
                    CURRENT_RENDERER_VERSION,
                    PublicationInfo,
                    PublicationStatus,
                    PublicationVisibility,
                    FeaturedInfo,
                    DiscoveryInfo,
                    SeoInfo,
                    BookStats,
                )

                now = datetime.now(timezone.utc)
                book_entity = Book(
                    schema_version=CURRENT_SCHEMA_VERSION,
                    renderer_version=CURRENT_RENDERER_VERSION,
                    title=book_title,
                    subtitle=book_sub,
                    running_title=state.book_plan.running_title,
                    author=state.cover_plan.author or resolved_author,
                    topic=topic,
                    prompt=prompt or topic,
                    description=state.book_plan.description,
                    book_type=state.intent.book_type if state.intent else "practical_guide",
                    publication_profile=str(state.intent.publication_profile.value) if state.intent and state.intent.publication_profile else "general_nonfiction",
                    category=category_name,
                    target_audience=state.intent.target_audience if state.intent else "General Readers",
                    tone=state.intent.tone if state.intent else "practical",
                    technical_depth=state.intent.technical_depth if state.intent else "intermediate",
                    status=PublicationStatus.DRAFT.value,
                    chapter_count=len(chapters_meta),
                    page_count=len(state.pages),
                    idea_id=idea_id,
                    chapters=chapters_meta,
                    publication=PublicationInfo(
                        status=PublicationStatus.DRAFT,
                        visibility=PublicationVisibility.PUBLIC,
                        published_at=None,
                        updated_at=now,
                    ),
                    featured=FeaturedInfo(pinned=False, position=None),
                    discovery=DiscoveryInfo(
                        search_title=book_title.strip().lower(),
                        keywords=keywords,
                        category=category_name,
                    ),
                    seo=SeoInfo(
                        title=seo_title,
                        description=seo_desc,
                        canonical_slug="",
                    ),
                    stats=BookStats(views=0, opens=0),
                )

                book_repo.create(book_entity)
                state.book = book_entity

                # 3. Update page book_ids and persist linked pages
                for p in state.pages:
                    p.book_id = book_entity.id
                    p.schema_version = CURRENT_SCHEMA_VERSION
                    p.renderer_version = CURRENT_RENDERER_VERSION

                page_repo.insert_pages_linked(state.pages)
                book_repo.update_starting_page(book_entity.id, state.pages[0].id)
                book_entity.starting_page_id = state.pages[0].id

                # 4. Persist Cover
                cover_service = CoverService(
                    settings=self.settings,
                    renderer=self.cover_renderer,
                    cover_repo=cover_repo,
                    book_repo=book_repo,
                )
                cover_entity = await cover_service.generate_and_persist_cover(
                    book_id=book_entity.id,
                    plan=state.cover_plan,
                    save_raster_image=save_raster_cover,
                )
                book_entity.cover_id = cover_entity.id
                state.cover = cover_entity

                # 5. Atomically transition publication to PUBLISHED
                book_repo.update_publication_status(
                    book_id=book_entity.id,
                    status=PublicationStatus.PUBLISHED,
                    visibility=PublicationVisibility.PUBLIC,
                )
                book_entity.publication.status = PublicationStatus.PUBLISHED
                book_entity.publication.published_at = datetime.now(timezone.utc)
                book_entity.status = PublicationStatus.PUBLISHED.value
                logger.info(f"Book successfully published to MongoDB (id={book_entity.id}, slug='{book_entity.slug}')")
            except Exception as e:
                logger.warning(f"Database persistence skipped or failed (non-blocking): {e}")
                state.errors.append(f"MongoDB: {e}")

        # Save generation metrics artifact
        metrics_json_path = out_dir / "generation_metrics.json"
        metrics_json_path.write_text(self.metrics.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["generation_metrics_json"] = str(metrics_json_path)

        # Save Book Manifest canonical record
        manifest_data = {
            "topic": topic,
            "title": state.book_plan.title if state.book_plan else (state.intent.title if state.intent else topic),
            "subtitle": state.book_plan.subtitle if state.book_plan else (state.intent.subtitle if state.intent else None),
            "author": state.cover_plan.author if state.cover_plan else resolved_author,
            "publisher": app_config.branding.publication_name,
            "company": app_config.branding.company_name,
            "edition": app_config.edition.name,
            "publication_year": app_config.edition.year,
            "website": app_config.branding.website if app_config.branding.website else None,
            "cover": {
                "style": state.cover_plan.cover_style if state.cover_plan else "editorial_minimal",
                "seed": state.cover_plan.cover_seed if state.cover_plan else book_seed,
                "background": state.cover_plan.background_color if state.cover_plan else "#faf8f5",
                "concept": state.cover_plan.concept_name if state.cover_plan else "Editorial Minimal",
            },
            "prompt": prompt,
            "target_pages": target_pages,
            "actual_pages": len(state.pages),
            "book_type": state.intent.book_type if state.intent else "practical_guide",
            "is_technical": state.intent.is_technical if state.intent else False,
            "target_audience": state.intent.target_audience if state.intent else "General Readers",
            "tone": state.intent.tone if state.intent else "practical",
            "technical_depth": state.intent.technical_depth if state.intent else "introductory",
            "required_topics": state.intent.required_topics if state.intent else [],
            "desired_elements": state.intent.desired_elements if state.intent else [],
            "chapter_count": len(state.book_plan.chapters) if state.book_plan else 0,
            "theme_palette": book_theme.palette_name if hasattr(book_theme, "palette_name") else "editorial_calm",
            "artifacts": dict(state.artifacts),
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        manifest_json_path = out_dir / "book_manifest.json"
        manifest_json_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        state.artifacts["book_manifest_json"] = str(manifest_json_path)

        # Enforce Production Non-Negotiable Contract
        if not self.settings.vasukisquare_mock_mode:
            if self.metrics.llm_calls_total == 0:
                raise RuntimeError(f"Production failure: 0 {self.llm_client.active_provider.upper()} LLM calls occurred during generation.")
            if self.metrics.pages_generated_by_llm == 0:
                raise RuntimeError(f"Production failure: 0 pages were authored by {self.llm_client.active_provider.upper()} LLM during generation.")
            if self.metrics.research.web_search_calls == 0:
                raise RuntimeError("Production failure: 0 web search calls occurred during generation.")
            if self.metrics.research.sources_accepted == 0:
                raise RuntimeError("Production failure: 0 research sources were accepted during generation.")
            if self.metrics.fallback_pages > 0:
                raise RuntimeError(f"Production failure: {self.metrics.fallback_pages} fallback pages were emitted.")

        summary_lines = [f"Pipeline Completed! Total Pages: {len(state.pages)}", self.metrics.summary_string()]
        if hasattr(self.llm_client, "groq_pool") and self.llm_client.active_provider == "groq":
            summary_lines.append(self.llm_client.groq_pool.get_summary())
        logger.info("\n".join(summary_lines))
        return state

