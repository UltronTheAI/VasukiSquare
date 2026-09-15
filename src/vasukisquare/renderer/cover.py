"""Cover rendering and persistence service handling 1600x2560 canvas, A4 crop, and MongoDB linking."""

import logging
from pathlib import Path
from typing import Optional, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import Cover, CoverDesignPlan, CoverPlan, Page, PageContent, generate_id
from vasukisquare.design.cover_patterns import CoverPatternGenerator
from vasukisquare.design.icons import render_lucide_icon
from vasukisquare.design.tokens import ColorToken, validate_color_token
from vasukisquare.design.theme import Theme
from vasukisquare.database.repository import BookRepository, CoverRepository

from vasukisquare.cover.contrast import (
    CoverTextPalette,
    get_contrasting_text_palette,
    auto_correct_cover_html,
    validate_cover_contrast,
)
from vasukisquare.cover.styles import ALL_COVER_STYLES


class CoverRenderer:
    """Renders 1600x2560 source cover artwork and A4-adapted printable cover pages across multiple composition families."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def _get_title_font_size(self, title: str) -> int:
        """Dynamically scale title font size to prevent overflow."""
        t_len = len(title)
        if t_len <= 30:
            return 44
        elif t_len <= 65:
            return 36
        elif t_len <= 100:
            return 30
        else:
            return 26

    def render_source_artwork(self, plan: Union[CoverPlan, CoverDesignPlan]) -> str:
        """Render high-resolution 1600x2560 standalone cover HTML with SVG vector scenery."""
        cover_style = getattr(plan, "cover_style", None)
        comp_style = getattr(plan, "composition_style", None)
        if cover_style in ALL_COVER_STYLES and (comp_style is None or comp_style == cover_style):
            from vasukisquare.cover.renderer import CoverRenderer as ModularCoverRenderer
            mod_renderer = ModularCoverRenderer(self.templates_dir)
            return mod_renderer.render_source_artwork(plan)

        accent = getattr(plan, "accent_color", None) or ColorToken.BRAND_GREEN.value
        bg = getattr(plan, "background_color", None) or ColorToken.BRAND_TEAL_DEEP.value

        palette = get_contrasting_text_palette(bg, accent)

        pattern_gen = CoverPatternGenerator()
        geom_type = getattr(plan, "decorative_geometry", "grid_overlay")
        geometric_svg = pattern_gen.generate_pattern(geom_type, accent)

        hero_icon = getattr(plan, "hero_icon", None)
        if hero_icon and hero_icon != "none":
            hero_icon_svg = render_lucide_icon(hero_icon, size=80, color=palette.cover_accent)
        else:
            hero_icon_svg = ""

        template = self.env.get_template("cover.html")
        raw_html = template.render(
            plan=plan,
            palette=palette,
            geometric_svg=geometric_svg,
            hero_icon_svg=hero_icon_svg,
        )
        return auto_correct_cover_html(raw_html, bg)

    def render_a4_cover_page(self, plan: Union[CoverPlan, CoverDesignPlan], book_id: str) -> Page:
        """Generate an A4 Page representation safely framing the art-directed cover composition."""
        cover_style = getattr(plan, "cover_style", None)
        comp_style = getattr(plan, "composition_style", None)
        if cover_style in ALL_COVER_STYLES and (comp_style is None or comp_style == cover_style):
            from vasukisquare.cover.renderer import CoverRenderer as ModularCoverRenderer
            mod_renderer = ModularCoverRenderer(self.templates_dir)
            return mod_renderer.render_a4_cover_page(plan, book_id)

        accent = getattr(plan, "accent_color", None) or ColorToken.BRAND_GREEN.value
        bg = getattr(plan, "background_color", None) or ColorToken.BRAND_TEAL_DEEP.value

        palette = get_contrasting_text_palette(bg, accent)

        pattern_gen = CoverPatternGenerator()
        geom_type = getattr(plan, "decorative_geometry", "grid_overlay")
        geometric_svg = pattern_gen.generate_pattern(geom_type, accent)

        hero_icon = getattr(plan, "hero_icon", None)
        if hero_icon and hero_icon != "none":
            icon_svg = render_lucide_icon(hero_icon, size=40, color=palette.cover_accent)
        else:
            icon_svg = ""

        title_size = self._get_title_font_size(plan.title)

        raw_html_body = self._compose_a4_html(
            plan=plan,
            accent=palette.cover_accent,
            bg=bg,
            geometric_svg=geometric_svg,
            icon_svg=icon_svg,
            title_size=title_size,
            palette=palette,
        )
        html_body = auto_correct_cover_html(raw_html_body, bg)

        return Page(
            id=generate_id(),
            book_id=book_id,
            page_number=1,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.LIGHT if palette.is_light_bg else Theme.DARK,
            content=PageContent(headline=plan.title, body=plan.subtitle or ""),
            html=html_body,
        )

    def _compose_a4_html(
        self,
        plan: CoverDesignPlan,
        accent: str,
        bg: str,
        geometric_svg: str,
        icon_svg: str,
        title_size: int,
        palette: Optional[CoverTextPalette] = None,
        is_light: Optional[bool] = None,
    ) -> str:
        """Assemble deterministic, high-contrast HTML based on composition style."""
        if palette is None:
            palette = get_contrasting_text_palette(bg, accent)

        style = plan.composition_style
        align = plan.title_alignment

        title_color = palette.cover_title
        subtitle_color = palette.cover_subtitle
        container_bg = palette.cover_container_bg
        meta_color = palette.cover_metadata
        border_color = palette.cover_border
        badge_bg = palette.cover_badge_bg
        divider_color = palette.cover_divider
        watermark_color = "rgba(0,30,43,0.06)" if palette.is_light_bg else "rgba(255,255,255,0.06)"
        card_bg = "rgba(255,255,255,0.85)" if palette.is_light_bg else "rgba(0,0,0,0.3)"

        from vasukisquare.config import get_app_config
        cfg = get_app_config()
        author_text = plan.author or cfg.branding.author_name
        edition_text = getattr(plan, "edition", None) or cfg.edition.name
        company_header = cfg.branding.company_name.upper()

        # 1. Asymmetric Left Heavy Composition
        if style == "asymmetric_left":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 56px 48px 96px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden; border-left: 4px solid {accent};">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.18; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {border_color}; padding-bottom: 20px;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">{company_header}</span>
                <span class="cover-category-badge" style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); position: relative; z-index: 10; display: inline-block;">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 16px; align-items: flex-start;">
                {f'<div class="cover-icon-wrapper" style="margin-bottom: 4px;">{icon_svg}</div>' if icon_svg else ''}
                <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; gap: 14px; text-align: left; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                  <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  <div class="cover-divider" style="width: 44px; height: 2px; background-color: {divider_color}; opacity: 0.95;"></div>
                  {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 14px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 520px; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>
              </div>
              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <span style="color: {palette.cover_footer_author}; font-weight: 700; font-size: 13px;">{author_text}</span>
                <span style="color: {palette.cover_footer_edition}; font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;">{edition_text}</span>
              </footer>
            </div>
            """

        # 2. Centered Editorial Composition
        elif style == "centered_editorial":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 64px 52px 96px 52px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden; text-align: center;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.16; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: {accent};">{company_header}</span>
                <div style="width: 32px; height: 2px; background-color: {accent}; opacity: 0.8;"></div>
                <span class="cover-category-badge" style="font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 4px 12px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); position: relative; z-index: 10; display: inline-block;">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; align-items: center; gap: 20px; max-width: 580px;">
                {f'<div class="cover-icon-wrapper" style="background: {badge_bg}; padding: 18px; border-radius: 50%; border: 1px solid {border_color};">{icon_svg}</div>' if icon_svg else ''}
                <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; align-items: center; text-align: center; gap: 14px; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                  <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.15; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  <div class="cover-divider" style="width: 44px; height: 2px; background-color: {divider_color}; opacity: 0.95;"></div>
                  {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 14px; color: {subtitle_color}; line-height: 1.5; margin: 0; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>
              </div>
              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <span style="color: {palette.cover_footer_author}; font-weight: 700; font-size: 13px;">{author_text}</span>
                <span style="color: {palette.cover_footer_edition}; font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;">{edition_text}</span>
              </footer>
            </div>
            """

        # 3. Framed Technical Handbook Composition
        elif style == "framed_technical":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 32px 32px 80px 32px; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div style="border: 1px solid {border_color}; height: 100%; width: 100%; box-sizing: border-box; padding: 40px; display: flex; flex-direction: column; justify-content: space-between; position: relative;">
                <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.16; pointer-events: none; overflow: hidden;">
                  {geometric_svg}
                </div>
                <!-- Technical Corner Brackets -->
                <div style="position: absolute; top: -1px; left: -1px; width: 16px; height: 16px; border-top: 3px solid {accent}; border-left: 3px solid {accent};"></div>
                <div style="position: absolute; top: -1px; right: -1px; width: 16px; height: 16px; border-top: 3px solid {accent}; border-right: 3px solid {accent};"></div>
                <div style="position: absolute; bottom: -1px; left: -1px; width: 16px; height: 16px; border-bottom: 3px solid {accent}; border-left: 3px solid {accent};"></div>
                <div style="position: absolute; bottom: -1px; right: -1px; width: 16px; height: 16px; border-bottom: 3px solid {accent}; border-right: 3px solid {accent};"></div>

                <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {border_color}; padding-bottom: 16px;">
                  <span style="font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">{company_header}</span>
                  <span class="cover-category-badge" style="font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); position: relative; z-index: 10; display: inline-block;">{plan.category}</span>
                </div>

                <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 16px; align-items: flex-start;">
                  {f'<div style="margin-bottom: 4px;">{icon_svg}</div>' if icon_svg else ''}
                  <span class="cover-category-badge" style="font-family: monospace; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; display: inline-block; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); width: fit-content; position: relative; z-index: 10;">ENGINEERING GUIDE</span>
                  <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; gap: 12px; text-align: left; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                    <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                      {plan.title}
                    </h1>
                    <div class="cover-divider" style="width: 40px; height: 2px; background-color: {divider_color}; opacity: 0.95;"></div>
                    {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 14px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 500px; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                  </div>
                </div>
              </div>
              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 18px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <span style="color: {palette.cover_footer_author}; font-weight: 700; font-size: 13px;">{author_text}</span>
                <span style="color: {palette.cover_footer_edition}; font-family: monospace; font-size: 10px;">{edition_text}</span>
              </footer>
            </div>
            """

        # 4. Dense Blueprint Composition
        elif style == "dense_blueprint":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 48px 48px 96px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.22; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid {accent}; padding-bottom: 16px;">
                <div>
                  <div style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">{company_header} TECHNICAL ARCHITECTURE</div>
                  <div style="font-size: 11px; color: {meta_color}; margin-top: 4px;">SYSTEM SPECIFICATION & IMPLEMENTATION HANDBOOK</div>
                </div>
                <div style="font-family: monospace; font-size: 11px; color: {palette.cover_primary_text}; background: {badge_bg}; padding: 6px 12px; border-radius: 4px; border: 1px solid {border_color};">
                  v1.0 // {plan.cover_seed}
                </div>
              </div>

              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 16px; align-items: flex-start;">
                <div style="display: flex; align-items: center; gap: 16px;">
                  {f'<div>{icon_svg}</div>' if icon_svg else ''}
                  <div style="height: 32px; width: 2px; background: {border_color};"></div>
                  <span class="cover-category-badge" style="font-family: monospace; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); text-transform: uppercase; position: relative; z-index: 10; display: inline-block;">{plan.category}</span>
                </div>
                <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; gap: 14px; text-align: left; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                  <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  <div class="cover-divider" style="width: 44px; height: 2px; background-color: {divider_color}; opacity: 0.95;"></div>
                  {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 14px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 500px; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>
              </div>

              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <div style="color: {palette.cover_footer_author}; font-size: 12px; font-weight: 700;">AUTHOR: {author_text}</div>
                <div style="color: {palette.cover_footer_edition}; font-weight: 600; font-size: 11px; letter-spacing: 1px;">{edition_text}</div>
              </footer>
            </div>
            """

        # 5. Large Typography & Typography-Only Composition
        elif style in ("large_typography", "typography_only"):
            large_size = title_size + 4
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 60px 48px 96px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.12; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 14px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase; color: {accent};">{company_header}</span>
                <span class="cover-category-badge" style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); position: relative; z-index: 10; display: inline-block;">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 16px; align-items: flex-start;">
                <div style="font-size: 64px; font-weight: 800; line-height: 0.9; color: {watermark_color}; letter-spacing: -2px; user-select: none;">
                  #01
                </div>
                <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; gap: 14px; text-align: left; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                  <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {large_size}px; font-weight: 700; line-height: 1.08; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  <div class="cover-divider" style="width: 56px; height: 3px; background-color: {divider_color}; opacity: 0.95;"></div>
                  {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 15px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 500px; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>
              </div>
              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <span style="color: {palette.cover_footer_author}; font-weight: 700; font-size: 13px;">{author_text}</span>
                <span style="color: {palette.cover_footer_edition}; font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;">{edition_text}</span>
              </footer>
            </div>
            """

        # 6. Bottom Weighted Composition
        elif style == "bottom_weighted":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 56px 48px 96px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.22; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">{company_header}</span>
                <span class="cover-category-badge" style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); position: relative; z-index: 10; display: inline-block;">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin-top: auto; padding-top: 40px; display: flex; flex-direction: column; gap: 16px; align-items: flex-start;">
                {f'<div class="cover-icon-wrapper">{icon_svg}</div>' if icon_svg else ''}
                <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; gap: 14px; text-align: left; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                  <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  <div class="cover-divider" style="width: 40px; height: 2px; background-color: {divider_color}; opacity: 0.95;"></div>
                  {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 14px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 500px; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>
              </div>
              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <span style="color: {palette.cover_footer_author}; font-weight: 700; font-size: 13px;">{author_text}</span>
                <span style="color: {palette.cover_footer_edition}; font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;">{edition_text}</span>
              </footer>
            </div>
            """

        # 7. Vertical Split / Split Panel Composition
        elif style in ("vertical_split", "split_panel"):
            sidebar_bg = "rgba(0,30,43,0.04)" if is_light else "rgba(0,0,0,0.35)"
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; display: flex; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <!-- Left Sidebar Band -->
              <div style="width: 90px; background: {sidebar_bg}; border-right: 2px solid {accent}; padding: 48px 16px 96px 16px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; position: relative; z-index: 3;">
                <div style="writing-mode: vertical-rl; transform: rotate(180deg); font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: {accent};">
                  {company_header}
                </div>
                {f'<div style="margin: 20px 0;">{icon_svg}</div>' if icon_svg else ''}
                <div class="cover-category-badge" style="writing-mode: vertical-rl; transform: rotate(180deg); font-size: 10px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 8px 6px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); position: relative; z-index: 10; display: inline-block;">
                  {plan.category}
                </div>
              </div>

              <!-- Main Content Body -->
              <div style="flex: 1; padding: 56px 48px 96px 48px; display: flex; flex-direction: column; justify-content: space-between; position: relative; z-index: 2;">
                <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.16; pointer-events: none; overflow: hidden;">
                  {geometric_svg}
                </div>
                <div style="position: relative; z-index: 2; text-align: right; font-size: 11px; color: {meta_color}; letter-spacing: 1px;">
                  EDITION // {plan.cover_seed}
                </div>
                <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 16px; align-items: flex-start;">
                  <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; gap: 14px; text-align: left; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                    <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.14; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                      {plan.title}
                    </h1>
                    <div class="cover-divider" style="width: 44px; height: 2px; background-color: {divider_color}; opacity: 0.95;"></div>
                    {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 14px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 460px; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                  </div>
                </div>
              </div>
              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <span style="color: {palette.cover_footer_author}; font-weight: 700; font-size: 13px;">{author_text}</span>
                <span style="color: {palette.cover_footer_edition}; font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;">{edition_text}</span>
              </footer>
            </div>
            """

        # 8. Default Modern Geometric Composition
        else:
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 56px 48px 96px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.18; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {border_color}; padding-bottom: 20px;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">{company_header}</span>
                <span class="cover-category-badge" style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: {palette.cover_badge_text}; background-color: {container_bg}; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); position: relative; z-index: 10; display: inline-block;">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 16px; align-items: {('center' if align == 'center' else 'flex-start')};">
                {f'<div class="cover-icon-wrapper" style="margin-bottom: 6px;">{icon_svg}</div>' if icon_svg else ''}
                <div class="cover-title-container" style="background-color: {container_bg}; padding: 24px 28px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 20px -8px rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; gap: 14px; text-align: {align}; width: fit-content; max-width: 100%; box-sizing: border-box; position: relative; z-index: 10;">
                  <h1 class="cover-title" style="font-family: \'Newsreader\', \'Lora\', \'Merriweather\', \'Playfair Display\', Georgia, serif; font-size: {title_size}px; font-weight: 700; line-height: 1.14; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  <div class="cover-divider" style="width: 44px; height: 2px; background-color: {divider_color}; margin: 2px 0; opacity: 0.95;"></div>
                  {f'<p class="cover-subtitle" style="font-family: \'Plus Jakarta Sans\', \'Inter\', sans-serif; font-size: 14px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 500px; word-break: break-word; opacity: 0.95;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>
              </div>
              <footer class="cover-footer-strip" style="position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background-color: {palette.cover_footer_bg}; z-index: 10; display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; box-sizing: border-box; border-top: 1px solid rgba(255, 255, 255, 0.12);">
                <span style="color: {palette.cover_footer_author}; font-weight: 700; font-size: 13px;">{author_text}</span>
                <span style="color: {palette.cover_footer_edition}; font-size: 10px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;">{edition_text}</span>
              </footer>
            </div>
            """




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
            subtitle=plan.subtitle,
            author=plan.author,
            design={
                "concept_name": getattr(plan, "concept_name", ""),
                "composition_style": plan.composition_style,
                "layout_style": plan.composition_style,
                "title_alignment": plan.title_alignment,
                "title_position": plan.title_position,
                "subtitle_position": plan.subtitle_position,
                "typography_style": plan.typography_style,
                "icon_strategy": plan.icon_strategy,
                "hero_icon": plan.hero_icon,
                "border_strategy": plan.border_strategy,
                "spacing_strategy": plan.spacing_strategy,
                "visual_density": plan.visual_density,
                "contrast_mode": plan.contrast_mode,
                "decorative_geometry": plan.decorative_geometry,
                "rationale": getattr(plan, "rationale", ""),
                "palette_theme": plan.palette_theme,
                "accent_color": plan.accent_color,
                "background_color": plan.background_color,
                "cover_seed": plan.cover_seed,
                "subtitle": plan.subtitle,
                "category": plan.category,
                "tone": plan.tone,
                "audience": plan.audience,
                "author": plan.author,
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

