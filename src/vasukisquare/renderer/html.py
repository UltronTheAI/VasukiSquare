"""HTML page rendering using Jinja2 templates and design system tokens."""

from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from vasukisquare.book.models import Page
from vasukisquare.design.icons import IconColorResolver, render_lucide_icon
from vasukisquare.design.tokens import ColorToken


class HtmlPageRenderer:
    """Renders Page models into standalone A4 HTML documents adhering to DESIGN.md."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self._css_cache: Optional[str] = None

    def _get_css(self) -> str:
        """Load and cache the base styles CSS."""
        if self._css_cache is None:
            css_file = self.templates_dir / "styles.css"
            if css_file.exists():
                self._css_cache = css_file.read_text(encoding="utf-8")
            else:
                self._css_cache = ""
        return self._css_cache

    def render_page(
        self,
        page: Page,
        book_title: str = "VasukiSquare Book",
        book_topic: str = "",
    ) -> str:
        """Render a single page into canonical HTML."""
        template = self.env.get_template("base.html")
        icon_svg = ""
        if page.icon_name:
            # Resolve icon color strictly from DESIGN.md tokens
            icon_color = IconColorResolver.resolve_color(page.theme, role="primary")
            icon_svg = render_lucide_icon(name=page.icon_name, color=icon_color, size=48)

        rendered = template.render(
            page=page,
            book_title=book_title,
            book_topic=book_topic,
            styles=self._get_css(),
            icon_svg=icon_svg,
        )
        return rendered
