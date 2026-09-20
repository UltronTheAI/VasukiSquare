"""Full-bleed HTML/SVG renderer for VasukiSquare covers supporting 10 distinct style families."""

import logging
import random
from pathlib import Path
from typing import List, Optional, Tuple, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape

from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import BookIntent, CoverDesignPlan, Page, PageContent, generate_id
from vasukisquare.cover.primitives import (
    generate_abstract_geometric,
    generate_botanical_foliage,
    generate_cinematic_landscape,
    generate_editorial_minimal,
    generate_mountain_scenery,
    generate_ocean_horizon,
    generate_sky_clouds,
    generate_symbolic_object,
    generate_terrain_journey,
    generate_typographic_poster_accents,
)
from vasukisquare.cover.styles import ALL_COVER_STYLES, CoverStyle
from vasukisquare.cover.contrast import (
    get_contrasting_text_palette,
    auto_correct_cover_html,
)
from vasukisquare.design.theme import Theme

logger = logging.getLogger(__name__)


class CoverRenderer:
    """Renders 1600x2560 high-resolution standalone artwork and A4 printable cover pages."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def _get_title_font_size(self, title: str, canvas_width: int = 1600) -> int:
        """Dynamically scale title font size to prevent overflow."""
        scale = canvas_width / 1600.0
        t_len = len(title)
        if t_len <= 25:
            base = 84
        elif t_len <= 50:
            base = 68
        elif t_len <= 75:
            base = 54
        else:
            base = 44
        return max(20, int(base * scale))

    def _generate_style_vector_svg(
        self,
        style: str,
        seed: int,
        canvas_size: Tuple[int, int],
        bg_color: str,
    ) -> str:
        """Generate deterministic procedural vector scenery for the selected cover style."""
        rng = random.Random(seed)
        colors = {"bg": bg_color}

        if style == CoverStyle.MOUNTAIN_LANDSCAPE.value:
            return generate_mountain_scenery(rng, canvas_size, colors)
        elif style == CoverStyle.OCEAN_HORIZON.value:
            return generate_ocean_horizon(rng, canvas_size, colors)
        elif style == CoverStyle.SKY_CLOUDS.value:
            return generate_sky_clouds(rng, canvas_size, colors)
        elif style == CoverStyle.ABSTRACT_GEOMETRIC.value:
            return generate_abstract_geometric(rng, canvas_size, colors)
        elif style == CoverStyle.TYPOGRAPHIC_POSTER.value:
            return generate_typographic_poster_accents(rng, canvas_size, colors)
        elif style == CoverStyle.BOTANICAL_ORGANIC.value:
            return generate_botanical_foliage(rng, canvas_size, colors)
        elif style == CoverStyle.TERRAIN_JOURNEY.value:
            return generate_terrain_journey(rng, canvas_size, colors)
        elif style == CoverStyle.SYMBOLIC_OBJECT.value:
            return generate_symbolic_object(rng, None, canvas_size, colors)
        elif style == CoverStyle.CINEMATIC_LANDSCAPE.value:
            return generate_cinematic_landscape(rng, canvas_size, colors)
        else:  # editorial_minimal
            return generate_editorial_minimal(rng, canvas_size, colors)

    def render_source_artwork(self, plan: CoverDesignPlan) -> str:
        """Render high-resolution 1600x2560 standalone cover HTML with solid dark title container."""
        canvas_w, canvas_h = 1600, 2560
        bg_color = plan.background_color or "#faf8f5"
        style = plan.cover_style or CoverStyle.EDITORIAL_MINIMAL.value

        # Derive automatic contrast-aware typography tokens directly from background & container
        palette = get_contrasting_text_palette(bg_color, plan.accent_color)
        container_bg = palette.cover_container_bg

        vector_svg = self._generate_style_vector_svg(
            style=style,
            seed=plan.cover_seed,
            canvas_size=(canvas_w, canvas_h),
            bg_color=bg_color,
        )

        title_size = self._get_title_font_size(plan.title, canvas_width=canvas_w)
        subtitle_size = max(22, int(title_size * 0.36))

        # Typography & layout configuration by style
        is_centered = style in (CoverStyle.MOUNTAIN_LANDSCAPE.value, CoverStyle.EDITORIAL_MINIMAL.value) and plan.title_alignment == "center"
        text_align = "center" if is_centered else "left"
        items_align = "center" if is_centered else "flex-start"
        container_align_self = "center" if is_centered else "flex-start"

        badge_text = plan.category_badge or getattr(plan, "category", None)
        category_badge_html = ""
        if badge_text:
            category_badge_html = f"""
            <div class="cover-category-badge" style="font-size: 16px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {palette.cover_badge_bg}; padding: 8px 18px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); display: inline-block;">
              {badge_text}
            </div>
            """

        subtitle_html = ""
        if plan.subtitle:
            subtitle_html = f"""
            <p class="cover-subtitle" style="font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif; font-size: {subtitle_size}px; font-weight: 400; line-height: 1.45; color: {palette.cover_subtitle}; max-width: 1080px; margin: 0; word-break: break-word; opacity: 0.95;">
              {plan.subtitle}
            </p>
            """

        from vasukisquare.config import get_app_config
        cfg = get_app_config()
        author_text = plan.author or cfg.branding.author_name
        edition_text = getattr(plan, "edition", None) or cfg.edition.name

        raw_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{plan.title} - Cover</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 1600px;
      height: 2560px;
      margin: 0;
      padding: 0;
      overflow: hidden;
      background-color: {bg_color};
      font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .cover-canvas {{
      position: relative;
      width: 1600px;
      height: 2560px;
      background-color: {bg_color};
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .vector-scenery-layer {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 1;
    }}
    .safe-content-area {{
      position: absolute;
      top: 220px;
      bottom: 160px;
      left: 180px;
      right: 180px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      z-index: 2;
    }}
    .cover-title-container {{
      background-color: {container_bg};
      padding: 48px 56px;
      border-radius: 6px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.45);
      display: flex;
      flex-direction: column;
      align-items: {items_align};
      text-align: {text_align};
      gap: 20px;
      width: fit-content;
      max-width: 100%;
      box-sizing: border-box;
      position: relative;
      z-index: 10;
      align-self: {container_align_self};
    }}
    .cover-footer-strip {{
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      width: 100%;
      background-color: {palette.cover_footer_bg};
      z-index: 10;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 40px 180px;
      box-sizing: border-box;
      border-top: 1px solid rgba(255, 255, 255, 0.12);
    }}
  </style>
</head>
<body>
  <div class="cover-canvas">
    <div class="vector-scenery-layer">
      {vector_svg}
    </div>
    <div class="safe-content-area">
      <header style="display: flex; justify-content: space-between; align-items: center;">
        {category_badge_html}
        <div></div>
      </header>

      <main style="margin: auto 0; display: flex; flex-direction: column; align-items: {items_align};">
        <div class="cover-title-container">
          <h1 class="cover-title" style="font-family: 'Newsreader', 'Lora', 'Merriweather', 'Playfair Display', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {palette.cover_title}; letter-spacing: -1px; max-width: 1140px; word-break: break-word; margin: 0;">
            {plan.title}
          </h1>
          <div class="cover-divider" style="width: 60px; height: 3px; background-color: {palette.cover_divider}; border-radius: 2px; opacity: 0.95; margin: 2px 0;"></div>
          {subtitle_html}
        </div>
      </main>
    </div>
    <footer class="cover-footer-strip">
      <div style="font-size: 22px; font-weight: 700; color: {palette.cover_footer_author}; letter-spacing: 0.5px;">
        {author_text}
      </div>
      <div style="font-size: 15px; font-weight: 500; color: {palette.cover_footer_edition}; letter-spacing: 1.5px; text-transform: uppercase;">
        {edition_text}
      </div>
    </footer>
  </div>
</body>
</html>"""

        return auto_correct_cover_html(raw_html, bg_color, container_bg=container_bg, footer_bg=palette.cover_footer_bg)

    def render_a4_cover_page(self, plan: CoverDesignPlan, book_id: str) -> Page:
        """Render A4-adapted printable page representation (794x1123) with solid dark title container and solid footer strip."""
        canvas_w, canvas_h = 794, 1123
        bg_color = plan.background_color or "#faf8f5"
        style = plan.cover_style or CoverStyle.EDITORIAL_MINIMAL.value

        # Derive automatic contrast-aware typography tokens directly from background & container
        palette = get_contrasting_text_palette(bg_color, plan.accent_color)
        container_bg = palette.cover_container_bg

        vector_svg = self._generate_style_vector_svg(
            style=style,
            seed=plan.cover_seed,
            canvas_size=(canvas_w, canvas_h),
            bg_color=bg_color,
        )

        title_size = self._get_title_font_size(plan.title, canvas_width=canvas_w)
        subtitle_size = max(13, int(title_size * 0.36))

        is_centered = style in (CoverStyle.MOUNTAIN_LANDSCAPE.value, CoverStyle.EDITORIAL_MINIMAL.value) and plan.title_alignment == "center"
        text_align = "center" if is_centered else "left"
        items_align = "center" if is_centered else "flex-start"
        container_align_self = "center" if is_centered else "flex-start"

        badge_text = plan.category_badge or getattr(plan, "category", None)
        category_badge_html = ""
        if badge_text:
            category_badge_html = f"""
            <div class="cover-category-badge" style="font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {palette.cover_badge_bg}; padding: 4px 10px; border-radius: 3px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); display: inline-block;">
              {badge_text}
            </div>
            """

        subtitle_html = ""
        if plan.subtitle:
            subtitle_html = f"""
            <p class="cover-subtitle" style="font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif; font-size: {subtitle_size}px; font-weight: 400; line-height: 1.45; color: {palette.cover_subtitle}; max-width: 540px; margin: 0; word-break: break-word; opacity: 0.95;">
              {plan.subtitle}
            </p>
            """

        from vasukisquare.config import get_app_config
        cfg = get_app_config()
        author_text = plan.author or cfg.branding.author_name
        edition_text = getattr(plan, "edition", None) or cfg.edition.name

        raw_html_content = f"""
        <div class="cover-hero cover-hero-solid" style="background-color: {bg_color}; padding: 48px 40px 96px 40px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
          <div class="vector-scenery-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1;">
            {vector_svg}
          </div>
          <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center;">
            {category_badge_html}
            <div></div>
          </div>
          <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; align-items: {items_align};">
            <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; align-items: {items_align}; text-align: {text_align}; gap: 12px; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10; align-self: {container_align_self};">
              <h1 class="cover-title" style="font-family: 'Newsreader', 'Lora', 'Merriweather', 'Playfair Display', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {palette.cover_title}; letter-spacing: -0.5px; max-width: 560px; word-break: break-word; margin: 0;">
                {plan.title}
              </h1>
              <div class="cover-divider" style="width: 36px; height: 2px; background-color: {palette.cover_divider}; border-radius: 1px; opacity: 0.95; margin: 1px 0;"></div>
              {subtitle_html}
            </div>
          </div>
          <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
            <span style="font-size: 13px; font-weight: 700; color: {palette.cover_footer_author}; letter-spacing: 0.5px;">{author_text}</span>
            <span style="font-size: 10px; font-weight: 500; color: {palette.cover_footer_edition}; letter-spacing: 1.5px; text-transform: uppercase;">{edition_text}</span>
          </footer>
        </div>
        """

        html_content = auto_correct_cover_html(raw_html_content, bg_color, container_bg=container_bg, footer_bg=palette.cover_footer_bg)

        return Page(
            id=generate_id(),
            book_id=book_id,
            page_number=1,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.LIGHT if palette.is_light_bg else Theme.DARK,
            icon=None,
            html=html_content,
            content=PageContent(headline=plan.title, body=plan.subtitle),
        )


def render_cover_gallery(
    topic: str,
    intent: Optional[BookIntent] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> List[Path]:
    """Render all 10 cover style previews for the given topic for QA visual inspection."""
    from vasukisquare.cover.planner import CoverPlannerAgent

    out_dir = Path(output_dir) if output_dir else Path("./output/cover_gallery")
    out_dir.mkdir(parents=True, exist_ok=True)

    planner = CoverPlannerAgent()
    renderer = CoverRenderer()
    generated_files: List[Path] = []

    for idx, style_name in enumerate(ALL_COVER_STYLES):
        seed = 1000 + idx * 77
        plan = planner.plan_cover(
            title=topic,
            subtitle="A Comprehensive Practical Guide",
            category="Practical Guide",
            seed=seed,
            intent=intent,
            style_override=style_name,
            author="Vasuki",
        )
        cover_html = renderer.render_source_artwork(plan)
        file_path = out_dir / f"cover_{idx+1:02d}_{style_name}.html"
        file_path.write_text(cover_html, encoding="utf-8")
        generated_files.append(file_path)

    logger.info(f"Generated {len(generated_files)} cover style previews in {out_dir}")
    return generated_files

