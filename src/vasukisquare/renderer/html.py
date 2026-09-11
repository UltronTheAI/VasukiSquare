"""HTML page and book rendering using Jinja2 templates, component blocks, and design system tokens."""

from pathlib import Path
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from vasukisquare.book.models import Page
from vasukisquare.design.icons import IconColorResolver, render_lucide_icon
from vasukisquare.renderer.components import ComponentRenderer
from vasukisquare.renderer.overflow import PageRepairEngine, OverflowDetector


class HtmlPageRenderer:
    """Renders Page models and complete Book documents into canonical physical A4 HTML."""

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
        repair_engine: Optional[PageRepairEngine] = None,
    ):
        if templates_dir is None:
            templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self._css_cache: Optional[str] = None
        self.repair_engine = repair_engine or PageRepairEngine()

    def _get_css(self) -> str:
        """Load and cache the base styles CSS."""
        if self._css_cache is None:
            css_file = self.templates_dir / "styles.css"
            if css_file.exists():
                self._css_cache = css_file.read_text(encoding="utf-8")
            else:
                self._css_cache = ""
        return self._css_cache

    def _render_page_blocks(self, page: Page) -> str:
        """Render all structured content blocks associated with a page."""
        if not page.content or not getattr(page.content, "blocks", None):
            return ""
        rendered_parts = []
        for block in page.content.blocks:
            rendered_parts.append(ComponentRenderer.render_block(block, theme=page.theme))
        return "\n".join(rendered_parts)

    def render_page(
        self,
        page: Page,
        book_title: str = "VasukiSquare Book",
        book_topic: str = "",
        running_title: Optional[str] = None,
    ) -> str:
        """Render an individual page model into standalone A4 HTML."""
        template = self.env.get_template("base.html")
        icon_svg = ""
        if page.icon_name:
            icon_size = 64 if page.layout == "chapter_opener" or page.page_type == "chapter_opener" else 48
            icon_color = IconColorResolver.resolve_color(page.theme, role="primary")
            icon_svg = render_lucide_icon(name=page.icon_name, color=icon_color, size=icon_size)

        blocks_html = self._render_page_blocks(page)
        calc_running_title = running_title or (book_title.split(":", 1)[0].strip() if ":" in book_title else book_title)

        rendered = template.render(
            page=page,
            book_title=book_title,
            book_topic=book_topic,
            running_title=calc_running_title,
            styles=self._get_css(),
            icon_svg=icon_svg,
            blocks_html=blocks_html,
        )
        return rendered

    def render_book(
        self,
        pages: List[Page],
        book_title: str = "VasukiSquare Book",
        book_topic: str = "",
        running_title: Optional[str] = None,
        auto_repair: bool = True,
    ) -> str:
        """Assemble and render a sequence of pages into a single cohesive multi-page HTML document."""
        processed_pages = self.repair_engine.repair_pages(pages) if auto_repair else pages
        template = self.env.get_template("book.html")
        calc_running_title = running_title or (book_title.split(":", 1)[0].strip() if ":" in book_title else book_title)

        page_items = []
        for p in processed_pages:
            icon_svg = ""
            if p.icon_name:
                icon_size = 64 if p.layout == "chapter_opener" or p.page_type == "chapter_opener" else 48
                icon_color = IconColorResolver.resolve_color(p.theme, role="primary")
                icon_svg = render_lucide_icon(name=p.icon_name, color=icon_color, size=icon_size)
            blocks_html = self._render_page_blocks(p)
            page_items.append({"page": p, "icon_svg": icon_svg, "blocks_html": blocks_html})

        rendered = template.render(
            page_items=page_items,
            book_title=book_title,
            book_topic=book_topic,
            running_title=calc_running_title,
            styles=self._get_css(),
        )
        return rendered
