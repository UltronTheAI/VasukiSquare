"""End-to-end ebook generation pipeline orchestrating reasoning, rendering, persistence, and PDF export."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from vasukisquare.config import Settings, get_settings
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
        self.cover_agent = cover_agent or CoverPlannerAgent(self.settings)
        self.writer_agent = writer_agent or PageWriterAgent(self.settings, llm_client=self.llm_client, metrics=self.metrics)
        self.html_renderer = html_renderer or HtmlPageRenderer()
        self.pdf_renderer = pdf_renderer or PdfRenderer(self.settings, self.html_renderer)
        self.cover_renderer = CoverRenderer()
        self.overflow_detector = OverflowDetector()
        self.repair_engine = PageRepairEngine(self.overflow_detector)

    async def run(
        self,
        topic: str,
        target_pages: int = 60,
        output_dir: Optional[Path] = None,
        generate_pdf: bool = True,
        save_raster_cover: bool = True,
        persist_db: bool = True,
    ) -> GenerationState:
        """Execute the complete generation pipeline for a book topic."""
        # 0. Validate production environment configuration before starting
        self.settings.validate_production_environment()
        self.llm_client.log_startup_banner()

        self.metrics.topic = topic
        self.metrics.target_pages = target_pages
        self.metrics.mock_mode = self.settings.vasukisquare_mock_mode

        state = GenerationState(topic=topic, target_pages=target_pages)
        out_dir = Path(output_dir or self.settings.pdf_output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = out_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting VasukiSquare Generation Pipeline for topic: '{topic}'")
        logger.info(
            f"Active Search Provider: {self.settings.active_search_provider_name} | "
            f"Active LLM Provider: {self.llm_client.active_provider.upper()} | "
            f"Model: {self.llm_client.active_model}"
        )

        # Stage 1: Intent Analysis
        logger.info("Stage 1/7: Inferring Book Intent...")
        state.intent = await self.editorial_agent.infer_intent(topic)

        # Stage 2: Deep Research
        logger.info("Stage 2/7: Executing Multi-Perspective Research...")
        state.research_corpus = await self.research_service.research_topic(topic)
        research_json_path = out_dir / "research.json"
        research_json_path.write_text(state.research_corpus.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["research_json"] = str(research_json_path)

        # Save planned research queries debug artifact
        queries_json_path = out_dir / "research_queries.json"
        queries_data = {
            "topic": topic,
            "queries": state.research_corpus.queries_executed,
            "key_findings": state.research_corpus.key_findings,
        }
        queries_json_path.write_text(json.dumps(queries_data, indent=2), encoding="utf-8")
        state.artifacts["research_queries_json"] = str(queries_json_path)

        # Stage 3: Editorial Planning
        logger.info(f"Stage 3/7: Generating Editorial & Chapter Plans (Target Pages: {target_pages})...")
        state.book_plan = await self.editorial_agent.generate_book_plan(
            prompt=topic,
            intent=state.intent,
            corpus=state.research_corpus,
            target_pages=target_pages,
        )
        plan_json_path = out_dir / "book_plan.json"
        plan_json_path.write_text(state.book_plan.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["book_plan_json"] = str(plan_json_path)

        # Stage 4: Cover Planning & Design
        logger.info("Stage 4/7: Designing Cover Artwork...")
        state.cover_plan = await self.cover_agent.plan_cover(
            title=state.book_plan.title,
            subtitle=state.book_plan.subtitle,
            category=state.intent.book_type.replace("_", " ").title(),
            tone=state.intent.tone,
            audience=state.intent.target_audience,
        )
        if not state.cover_plan:
            raise RuntimeError("Book cover is missing or failed to render.")

        a4_cover_page = self.cover_renderer.render_a4_cover_page(
            state.cover_plan,
            book_id=state.book_plan.title.lower().replace(" ", "-"),
        )
        if not a4_cover_page or not a4_cover_page.html:
            raise RuntimeError("Book cover is missing or failed to render.")

        # Stage 5: Page Writing & HTML Generation (with targeted validation)
        logger.info(f"Stage 5/7: Writing {len(state.book_plan.all_planned_pages)} Pages...")
        raw_pages: List[Page] = []

        for p_spec in state.book_plan.all_planned_pages:
            if p_spec.page_number == 1 or p_spec.page_type == LayoutType.COVER.value:
                raw_pages.append(a4_cover_page)
                continue

            page_model = await self.writer_agent.write_page(p_spec, state.book_plan, state.research_corpus)
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
                    for idx, doc in enumerate(state.research_corpus.documents[:6], start=1):
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

        # Validate content quality and semantic correctness across all pages
        content_errors = ContentValidator.validate_book(
            state.pages,
            expected_topic=topic,
            expected_language=state.intent.primary_programming_language,
        )
        if content_errors:
            logger.warning(f"Content quality validator identified issues: {content_errors}")
            state.errors.extend(content_errors)

        # Stage 6: Database Persistence
        if persist_db:
            logger.info("Stage 6/7: Persisting Book, Pages, and Cover to MongoDB...")
            try:
                book_repo = BookRepository(self.db_manager.db)
                page_repo = PageRepository(self.db_manager.db)
                cover_repo = CoverRepository(self.db_manager.db)

                # 1. Persist Book
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
                book_entity = Book(
                    title=state.book_plan.title,
                    subtitle=state.book_plan.subtitle,
                    running_title=state.book_plan.running_title,
                    prompt=topic,
                    description=state.book_plan.description,
                    chapter_count=len(chapters_meta),
                    page_count=len(state.pages),
                    chapters=chapters_meta,
                )
                book_repo.create(book_entity)
                state.book = book_entity

                # 2. Update page book_ids and persist linked pages
                for p in state.pages:
                    p.book_id = book_entity.id

                page_repo.insert_pages_linked(state.pages)
                book_repo.update_starting_page(book_entity.id, state.pages[0].id)
                book_entity.starting_page_id = state.pages[0].id

                # 3. Persist Cover
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
            except Exception as e:
                logger.warning(f"Database persistence skipped or failed (non-blocking): {e}")
                state.errors.append(f"MongoDB: {e}")

        # Stage 7: Final HTML Assembly & PDF Rendering
        logger.info("Stage 7/7: Assembling Final Book HTML and Exporting PDF...")
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

        # Save generation metrics artifact
        metrics_json_path = out_dir / "generation_metrics.json"
        metrics_json_path.write_text(self.metrics.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["generation_metrics_json"] = str(metrics_json_path)

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

        logger.info(f"Pipeline Completed! Total Pages: {len(state.pages)}\n{self.metrics.summary_string()}")
        return state

