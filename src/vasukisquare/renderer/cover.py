"""Cover rendering and persistence service handling 1600x2560 canvas, A4 crop, and MongoDB linking."""

import logging
from pathlib import Path
from typing import Optional, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import Cover, CoverPlan, Page, PageContent, generate_id
from vasukisquare.design.cover_patterns import CoverPatternGenerator
from vasukisquare.design.icons import render_lucide_icon
from vasukisquare.design.tokens import ColorToken, validate_color_token
from vasukisquare.design.theme import Theme
from vasukisquare.database.repository import BookRepository, CoverRepository

logger = logging.getLogger(__name__)


class CoverRenderer:
    """Renders 1600x2560 source cover artwork and A4-adapted printable cover pages."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_source_artwork(self, plan: CoverPlan) -> str:
        """Render high-resolution 1600x2560 standalone cover HTML with SVG background."""
        template = self.env.get_template("cover.html")

        # Resolve accent and background tokens
        accent_token = validate_color_token(plan.accent_color)
        bg_token = validate_color_token(plan.background_color)
        sec_token = ColorToken.BRAND_TEAL.value

        # Generate geometric vector pattern
        geometric_svg = CoverPatternGenerator.generate_pattern(
            style=plan.layout_style,
            accent_color=accent_token.value,
            secondary_color=sec_token,
            canvas_size=(1600, 2560),
        )

        # Render central hero Lucide SVG
        hero_icon_svg = render_lucide_icon(
            name=plan.hero_icon,
            color=accent_token,
            size=110,
            stroke_width=2.2,
        )

        return template.render(
            plan=plan,
            geometric_svg=geometric_svg,
            hero_icon_svg=hero_icon_svg,
        )

    def render_a4_cover_page(self, plan: CoverPlan, book_id: str) -> Page:
        """Generate an A4 Page representation safely framing the cover artwork."""
        accent_token = validate_color_token(plan.accent_color)
        bg_token = validate_color_token(plan.background_color)
        sec_token = ColorToken.BRAND_TEAL.value
        icon_svg = render_lucide_icon(name=plan.hero_icon, color=accent_token, size=64, stroke_width=1.8)

        # Generate geometric vector pattern for A4 canvas (794 x 1123)
        geometric_svg = CoverPatternGenerator.generate_pattern(
            style=plan.layout_style,
            accent_color=accent_token.value,
            secondary_color=sec_token,
            canvas_size=(794, 1123),
        )

        html_content = f"""
        <div class="cover-hero cover-hero-solid" style="background-color: {bg_token.value}; padding: 48px 40px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
          <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.15; pointer-events: none; overflow: hidden;">
            {geometric_svg}
          </div>
          <div class="cover-brand-header" style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.15);">
            <span style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent_token.value};">VASUKISQUARE</span>
            <span style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: #a8b3bc;">{plan.category}</span>
          </div>
          <div class="cover-main-body" style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 20px;">
            <div class="cover-icon-wrapper" style="margin-bottom: 8px;">
              {icon_svg}
            </div>
            <div style="width: 60px; height: 3px; background-color: {accent_token.value}; margin: 6px 0;"></div>
            <h1 class="cover-title" style="font-size: 38px; font-weight: 700; line-height: 1.12; color: #ffffff; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
              {plan.title}
            </h1>
            {f'<p class="cover-subtitle" style="font-size: 15px; color: #c1ccd6; line-height: 1.45; margin: 0; max-width: 520px; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
          </div>
          <footer class="cover-footer" style="position: relative; z-index: 2; padding-top: 20px; width: 100%; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #a8b3bc; border-top: 1px solid rgba(255, 255, 255, 0.15);">
            <span style="color: #e1e5e8; font-weight: 600;">{plan.author}</span>
            <span style="letter-spacing: 0.5px;">VASUKISQUARE TECHNICAL PUBLISHING</span>
          </footer>
        </div>
        """

        return Page(
            id=generate_id(),
            book_id=book_id,
            page_number=1,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.DARK,
            icon=plan.hero_icon,
            html=html_content,
            content=PageContent(headline=plan.title, body=plan.subtitle),
        )



class CoverService:
    """Coordinates cover generation, MongoDB persistence, rasterization, and Book linking."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        renderer: Optional[CoverRenderer] = None,
        cover_repo: Optional[CoverRepository] = None,
        book_repo: Optional[BookRepository] = None,
    ):
        self.settings = settings or get_settings()
        self.renderer = renderer or CoverRenderer()
        self.cover_repo = cover_repo
        self.book_repo = book_repo

    async def save_raster(self, html_content: str, output_path: Union[str, Path]) -> Path:
        """Capture a 1600x2560 screenshot using Playwright Chromium."""
        from playwright.async_api import async_playwright

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.settings.chromium_headless)
            page = await browser.new_page(viewport={"width": 1600, "height": 2560})
            await page.set_content(html_content, wait_until="load")
            await page.screenshot(path=str(out_path), full_page=True)
            await browser.close()

        return out_path

    async def generate_and_persist_cover(
        self,
        book_id: str,
        plan: CoverPlan,
        save_raster_image: bool = False,
    ) -> Cover:
        """Generate high-res artwork, persist in MongoDB, and link back to Book."""
        # 1. Render 1600x2560 artwork HTML
        artwork_html = self.renderer.render_source_artwork(plan)

        cover_id = generate_id()
        image_path = None

        # 2. Optionally capture raster PNG
        if save_raster_image:
            raster_file = Path(self.settings.pdf_output_dir) / "covers" / f"{cover_id}.png"
            try:
                await self.save_raster(artwork_html, raster_file)
                image_path = str(raster_file)
            except Exception as e:
                logger.warning(f"Failed to capture raster screenshot for cover {cover_id}: {e}")

        # 3. Create Cover entity
        cover = Cover(
            id=cover_id,
            book_id=book_id,
            width=1600,
            height=2560,
            title=plan.title,
            design={
                "subtitle": plan.subtitle,
                "category": plan.category,
                "tone": plan.tone,
                "audience": plan.audience,
                "palette_theme": plan.palette_theme,
                "layout_style": plan.layout_style,
                "hero_icon": plan.hero_icon,
                "accent_color": plan.accent_color,
                "background_color": plan.background_color,
            },
            html=artwork_html,
            image_path=image_path,
        )

        # 4. Persist in MongoDB covers collection
        if self.cover_repo:
            self.cover_repo.create(cover)

        # 5. Link cover_id in Book collection
        if self.book_repo:
            self.book_repo.update_cover_id(book_id, cover.id)

        return cover

