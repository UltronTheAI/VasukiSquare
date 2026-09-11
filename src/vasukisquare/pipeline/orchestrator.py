"""End-to-end ebook generation pipeline orchestrating reasoning, rendering, persistence, and PDF export."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import Book, ChapterMetadata, Page
from vasukisquare.agents.editorial import EditorialPlannerAgent
from vasukisquare.agents.cover import CoverPlannerAgent
from vasukisquare.agents.writer import PageWriterAgent
from vasukisquare.research.service import ResearchService
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.renderer.cover import CoverRenderer, CoverService
from vasukisquare.renderer.pdf import PdfRenderer
from vasukisquare.renderer.overflow import OverflowDetector, PageRepairEngine
from vasukisquare.database.connection import DatabaseManager
from vasukisquare.database.repository import BookRepository, PageRepository, CoverRepository
from vasukisquare.pipeline.state import GenerationState

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
    ):
        self.settings = settings or get_settings()
        self.db_manager = db_manager or DatabaseManager(self.settings)
        self.research_service = research_service or ResearchService(self.settings)
        self.editorial_agent = editorial_agent or EditorialPlannerAgent(self.settings)
        self.cover_agent = cover_agent or CoverPlannerAgent(self.settings)
        self.writer_agent = writer_agent or PageWriterAgent(self.settings)
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
        state = GenerationState(topic=topic, target_pages=target_pages)
        out_dir = Path(output_dir or self.settings.pdf_output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = out_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting VasukiSquare Generation Pipeline for topic: '{topic}'")

        # Stage 1: Intent Analysis
        logger.info("Stage 1/7: Inferring Book Intent...")
        state.intent = await self.editorial_agent.infer_intent(topic)

        # Stage 2: Deep Research
        logger.info("Stage 2/7: Executing Multi-Perspective Research...")
        state.research_corpus = await self.research_service.research_topic(topic)
        research_json_path = out_dir / "research.json"
        research_json_path.write_text(state.research_corpus.model_dump_json(indent=2), encoding="utf-8")
        state.artifacts["research_json"] = str(research_json_path)

        # Stage 3: Editorial Planning
        logger.info("Stage 3/7: Generating Editorial & Chapter Plans...")
        state.book_plan = await self.editorial_agent.generate_book_plan(
            prompt=topic,
            intent=state.intent,
            corpus=state.research_corpus,
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
        a4_cover_page = self.cover_renderer.render_a4_cover_page(state.cover_plan, book_id=state.book_plan.title.lower().replace(" ", "-"))

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

        # Ensure canonical HTML is rendered for all pages prior to MongoDB persistence & export
        for p in state.pages:
            if p.layout != LayoutType.COVER.value or not p.html:
                p.html = self.html_renderer.render_page(p, state.book_plan.title, topic)

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
                    save_raster_image=False,
                )
                book_entity.cover_id = cover_entity.id
                state.cover = cover_entity
            except Exception as e:
                logger.warning(f"MongoDB persistence encountered error (continuing file export): {e}")
                state.errors.append(f"MongoDB: {e}")

        # Stage 7: Assembly & PDF Export
        logger.info("Stage 7/7: Assembling Final Book HTML and Exporting PDF...")
        state.assembled_html = self.html_renderer.render_book(
            pages=state.pages,
            book_title=state.book_plan.title,
            book_topic=topic,
            auto_repair=False,
        )

        book_html_path = out_dir / "book.html"
        book_html_path.write_text(state.assembled_html, encoding="utf-8")
        state.artifacts["book_html"] = str(book_html_path)

        # Export individual page HTMLs
        for idx, p in enumerate(state.pages):
            single_page_html = self.html_renderer.render_page(p, state.book_plan.title, topic)
            p_file = pages_dir / f"page_{idx + 1:03d}.html"
            p_file.write_text(single_page_html, encoding="utf-8")

        state.artifacts["pages_dir"] = str(pages_dir)

        # Cover source artwork HTML & optional raster PNG
        cover_html_path = out_dir / "cover.html"
        cover_html = self.cover_renderer.render_source_artwork(state.cover_plan)
        cover_html_path.write_text(cover_html, encoding="utf-8")
        state.artifacts["cover_html"] = str(cover_html_path)

        cover_img_path = out_dir / "cover.png"
        if save_raster_cover:
            try:
                cover_service = CoverService(self.settings, self.cover_renderer)
                await cover_service.save_raster(cover_html, cover_img_path)
                state.artifacts["cover_png"] = str(cover_img_path)
            except Exception as e:
                logger.warning(f"Could not export raster cover PNG: {e}")

        # PDF Compilation
        if generate_pdf:
            pdf_path = out_dir / "book.pdf"
            try:
                await self.pdf_renderer.render_html_to_pdf(state.assembled_html, pdf_path)
                state.pdf_path = str(pdf_path)
                state.artifacts["book_pdf"] = str(pdf_path)
                logger.info(f"PDF Successfully rendered: {pdf_path}")
            except Exception as e:
                logger.warning(f"PDF rendering failed: {e}")
                state.errors.append(f"PDF: {e}")

        logger.info(f"Pipeline Completed! Total Pages: {len(state.pages)}")
        return state
