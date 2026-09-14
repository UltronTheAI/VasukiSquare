"""HTML page and book rendering using Jinja2 templates, component blocks, and design system tokens."""

from pathlib import Path
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from vasukisquare.book.models import Page
from vasukisquare.design.icons import IconColorResolver, render_lucide_icon, resolve_topic_decorative_icon
from vasukisquare.renderer.components import ComponentRenderer
from vasukisquare.renderer.overflow import PageRepairEngine, OverflowDetector, estimate_page_utilization


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

    def _render_chapter_opener_html(self, page: Page, icon_svg: str) -> str:
        """Render one of 6 distinctive chapter opener layout templates."""
        ch_num = page.chapter_number or 1
        ch_title = page.chapter_title or (page.content and page.content.headline) or f"Chapter {ch_num}"
        ch_fmt = f"{ch_num:02d}"
        
        # Select opener template based on page.style.opener_template or rotate by chapter number
        template = (page.style and page.style.opener_template) or [
            "minimal_centered",
            "left_accent_banner",
            "split_contrast",
            "editorial_classic",
            "technical_blueprint",
            "icon_heroic",
        ][(ch_num - 1) % 6]

        if template == "left_accent_banner":
            return f"""
            <div class="chapter-opener-wrapper layout-left-accent">
              <div class="opener-left-stripe"></div>
              <div class="opener-content">
                <div class="opener-top-row">
                  <span class="opener-badge">CHAPTER {ch_fmt}</span>
                  <div class="opener-icon-corner">{icon_svg}</div>
                </div>
                <h1 class="opener-title">{ch_title}</h1>
                <div class="opener-divider"></div>
              </div>
            </div>
            """
        elif template == "split_contrast":
            return f"""
            <div class="chapter-opener-wrapper layout-split-contrast">
              <div class="opener-card">
                <div class="opener-card-header">
                  <div class="opener-icon-badge">{icon_svg}</div>
                  <span class="opener-badge">SECTION // CH.{ch_fmt}</span>
                </div>
                <h1 class="opener-title">{ch_title}</h1>
              </div>
            </div>
            """
        elif template == "editorial_classic":
            return f"""
            <div class="chapter-opener-wrapper layout-editorial-classic">
              <div class="opener-num-watermark">{ch_fmt}</div>
              <div class="opener-icon-top">{icon_svg}</div>
              <div class="opener-eyebrow">Chapter {ch_num}</div>
              <h1 class="opener-title">{ch_title}</h1>
              <div class="opener-divider-line"></div>
            </div>
            """
        elif template == "technical_blueprint":
            return f"""
            <div class="chapter-opener-wrapper layout-technical-blueprint">
              <div class="opener-blueprint-frame">
                <div class="corner-bracket top-left"></div>
                <div class="corner-bracket top-right"></div>
                <div class="corner-bracket bottom-left"></div>
                <div class="corner-bracket bottom-right"></div>
                <div class="opener-mono-tag">CHAPTER SPECIFICATION // {ch_fmt}</div>
                <div class="opener-icon-mid">{icon_svg}</div>
                <h1 class="opener-title">{ch_title}</h1>
              </div>
            </div>
            """
        elif template == "icon_heroic":
            return f"""
            <div class="chapter-opener-wrapper layout-icon-heroic">
              <div class="opener-hero-halo">
                {icon_svg}
              </div>
              <div class="opener-num-pill">Chapter {ch_num}</div>
              <h1 class="opener-title">{ch_title}</h1>
            </div>
            """
        else:  # minimal_centered
            return f"""
            <div class="chapter-opener-wrapper layout-minimal-centered">
              <div class="opener-icon-circle">{icon_svg}</div>
              <div class="chapter-num">Chapter {ch_num}</div>
              <h1 class="chapter-title">{ch_title}</h1>
              <div class="opener-divider"></div>
            </div>
            """

    def _render_thank_you_html(self, page: Page, icon_svg: str, book_title: str) -> str:
        """Render one of 3 distinctive finishing/thank-you layouts."""
        headline = (page.content and page.content.headline) or "THANK YOU"
        body_text = (page.content and page.content.body) or f"Thank you for reading {book_title}. May these architectures guide your engineering journey."
        
        variant = (page.style and page.style.layout_variant) or "classic_brand"
        
        if variant == "community_resources":
            return f"""
            <div class="thank-you-container layout-resources">
              <div class="thank-you-brand">
                <span>VASUKISQUARE TECHNICAL PRESS</span>
                <span>COMPLETION OF VOLUME</span>
              </div>
              <div class="thank-you-body">
                <div class="thank-you-icon">{icon_svg}</div>
                <h1 class="thank-you-title">{headline}</h1>
                <p class="thank-you-statement">{body_text}</p>
                <div class="thank-you-next-steps">
                  <h4>Next Steps & Community Resources</h4>
                  <p>Explore official documentation, verify production blueprints, and contribute back to open-source software ecosystems.</p>
                </div>
              </div>
              <div class="thank-you-footer">
                <span>{book_title}</span>
                <span>AUTONOMOUS PUBLISHING</span>
              </div>
            </div>
            """
        elif variant == "minimal_quote":
            return f"""
            <div class="thank-you-container layout-quote">
              <div class="thank-you-brand">
                <span>END OF VOLUME</span>
              </div>
              <div class="thank-you-body">
                <div class="thank-you-icon">{icon_svg}</div>
                <h1 class="thank-you-title">{headline}</h1>
                <p class="thank-you-quote">“The best way to understand a system is to build it with precision, clarity, and relentless curiosity.”</p>
                <div class="thank-you-divider"></div>
                <p class="thank-you-statement">{body_text}</p>
              </div>
              <div class="thank-you-footer">
                <span>VASUKISQUARE EDITORIAL</span>
                <span>2026 EDITION</span>
              </div>
            </div>
            """
        else:  # classic_brand
            return f"""
            <div class="thank-you-container layout-classic">
              <div class="thank-you-brand">
                <span>VASUKISQUARE TECHNICAL PUBLISHING</span>
                <span>END OF VOLUME</span>
              </div>
              <div class="thank-you-body">
                <div class="thank-you-icon">{icon_svg}</div>
                <div class="thank-you-divider"></div>
                <h1 class="thank-you-title">{headline}</h1>
                <p class="thank-you-statement">{body_text}</p>
              </div>
              <div class="thank-you-footer">
                <span>{book_title}</span>
                <span>FIRST EDITION</span>
              </div>
            </div>
            """

    def _render_page_blocks(self, page: Page) -> str:
        """Render all structured content blocks associated with a page."""
        if not page.content or not getattr(page.content, "blocks", None):
            return ""
        rendered_parts = []
        for block in page.content.blocks:
            rendered_parts.append(ComponentRenderer.render_block(block, theme=page.theme))
        return "\n".join(rendered_parts)

    def _get_page_inline_style(self, page: Page) -> str:
        """Compute custom CSS variables from page style."""
        styles = []
        if page.style:
            if page.style.background_color:
                styles.append(f"--theme-bg: {page.style.background_color}; background-color: {page.style.background_color};")
            if page.style.text_color:
                styles.append(f"--theme-text: {page.style.text_color}; color: {page.style.text_color};")
            if page.style.text_muted:
                styles.append(f"--theme-text-muted: {page.style.text_muted};")
            if page.style.border_color:
                styles.append(f"--theme-border: {page.style.border_color};")
            if page.style.accent_color:
                styles.append(f"--theme-accent: {page.style.accent_color};")
        return " ".join(styles)

    def _render_decorative_watermark(self, page: Page, book_topic: str, book_title: str) -> str:
        """Render subtle, non-intrusive background Lucide watermark icon if page has appropriate negative space."""
        p_type = getattr(page, "page_type", "") or page.layout_type.value
        if p_type in ("chapter_opener", "cover", "thank_you", "toc", "copyright", "imprint"):
            return ""

        # Only render watermark if page has ample negative space (utilization <= 0.85)
        util = estimate_page_utilization(page)
        if util.estimated_ratio > 0.85:
            return ""

        topic_str = f"{book_topic} {book_title} {page.chapter_title or ''} {getattr(page.content, 'headline', '')}"
        icon_name = resolve_topic_decorative_icon(topic_str, getattr(page.content, 'headline', ''))
        icon_color = IconColorResolver.resolve_color(page.theme, role="primary")
        icon_svg = render_lucide_icon(name=icon_name, color=icon_color, size=130)

        pos_class = "pos-bottom-right" if (page.page_number % 2 == 0) else "pos-bottom-left"
        return f'<div class="decorative-watermark-icon {pos_class}">{icon_svg}</div>'

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

        opener_html = ""
        if page.layout == "chapter_opener" or page.page_type == "chapter_opener":
            opener_html = self._render_chapter_opener_html(page, icon_svg)

        thank_you_html = ""
        if page.layout == "thank_you" or page.page_type == "thank_you":
            thank_you_html = self._render_thank_you_html(page, icon_svg, book_title)

        watermark_svg = self._render_decorative_watermark(page, book_topic, book_title)

        rendered = template.render(
            page=page,
            book_title=book_title,
            book_topic=book_topic,
            running_title=calc_running_title,
            styles=self._get_css(),
            icon_svg=icon_svg,
            blocks_html=blocks_html,
            opener_html=opener_html,
            thank_you_html=thank_you_html,
            watermark_svg=watermark_svg,
            custom_inline_style=self._get_page_inline_style(page),
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
            
            opener_html = ""
            if p.layout == "chapter_opener" or p.page_type == "chapter_opener":
                opener_html = self._render_chapter_opener_html(p, icon_svg)

            thank_you_html = ""
            if p.layout == "thank_you" or p.page_type == "thank_you":
                thank_you_html = self._render_thank_you_html(p, icon_svg, book_title)

            watermark_svg = self._render_decorative_watermark(p, book_topic, book_title)

            page_items.append({
                "page": p,
                "icon_svg": icon_svg,
                "blocks_html": blocks_html,
                "opener_html": opener_html,
                "thank_you_html": thank_you_html,
                "watermark_svg": watermark_svg,
                "custom_inline_style": self._get_page_inline_style(p),
            })

        rendered = template.render(
            page_items=page_items,
            book_title=book_title,
            book_topic=book_topic,
            running_title=calc_running_title,
            styles=self._get_css(),
        )
        return rendered


# Backward-compatible alias
HTMLRenderer = HtmlPageRenderer



