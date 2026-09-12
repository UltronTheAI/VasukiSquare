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

logger = logging.getLogger(__name__)


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

    def render_source_artwork(self, plan: CoverDesignPlan) -> str:
        """Render high-resolution 1600x2560 standalone cover HTML with SVG background."""
        template = self.env.get_template("cover.html")

        # Resolve accent and background tokens
        accent_token = validate_color_token(plan.accent_color)
        bg_token = validate_color_token(plan.background_color)
        sec_token = ColorToken.BRAND_TEAL.value

        # Generate geometric vector pattern
        geometric_svg = CoverPatternGenerator.generate_pattern(
            style=plan.decorative_geometry,
            accent_color=accent_token.value,
            secondary_color=sec_token,
            canvas_size=(1600, 2560),
        )

        hero_icon_svg = ""
        if plan.icon_strategy != "none" and plan.hero_icon:
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

    def render_a4_cover_page(self, plan: CoverDesignPlan, book_id: str) -> Page:
        """Generate an A4 Page representation safely framing the art-directed cover composition."""
        accent_token = validate_color_token(plan.accent_color)
        bg_token = validate_color_token(plan.background_color)
        sec_token = ColorToken.BRAND_TEAL.value

        # Generate geometric vector pattern for A4 canvas (794 x 1123)
        geometric_svg = CoverPatternGenerator.generate_pattern(
            style=plan.decorative_geometry,
            accent_color=accent_token.value,
            secondary_color=sec_token,
            canvas_size=(794, 1123),
        )

        icon_svg = ""
        if plan.icon_strategy != "none" and plan.hero_icon:
            icon_size = 72 if plan.composition_style == "icon_led" else 48
            icon_svg = render_lucide_icon(name=plan.hero_icon, color=accent_token, size=icon_size, stroke_width=2.0)

        title_size = self._get_title_font_size(plan.title)
        
        # Check if background is light
        bg_val = bg_token.value.lower()
        is_light = bg_val in ("#ffffff", "#fafbfc", "#f8fafc", "#f4f6f8", "#f0fdf4", "#f0fdfa", "#f0f9ff", "#eff6ff", "#eef2ff", "#f5f3ff", "#faf5ff", "#fdf2f8", "#fefce8", "#fffbeb", "#fff7ed", "#f9fbfa", "#f4f7f6") or plan.contrast_mode == "high_contrast_light"

        html_content = self._compose_a4_html(
            plan=plan,
            accent=accent_token.value,
            bg=bg_token.value,
            geometric_svg=geometric_svg,
            icon_svg=icon_svg,
            title_size=title_size,
            is_light=is_light,
        )

        return Page(
            id=generate_id(),
            book_id=book_id,
            page_number=1,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.LIGHT if is_light else Theme.DARK,
            icon=plan.hero_icon if plan.icon_strategy != "none" else None,
            html=html_content,
            content=PageContent(headline=plan.title, body=plan.subtitle),
        )

    def _compose_a4_html(
        self,
        plan: CoverDesignPlan,
        accent: str,
        bg: str,
        geometric_svg: str,
        icon_svg: str,
        title_size: int,
        is_light: bool = True,
    ) -> str:
        """Assemble deterministic, high-contrast HTML based on composition style."""
        style = plan.composition_style
        align = plan.title_alignment

        title_color = "#001e2b" if is_light else "#ffffff"
        subtitle_color = "#3d4f5b" if is_light else "#c1ccd6"
        meta_color = "#5c6c7a" if is_light else "#a8b3bc"
        border_color = "rgba(0,30,43,0.12)" if is_light else "rgba(255,255,255,0.12)"
        badge_bg = "rgba(0,30,43,0.06)" if is_light else "rgba(255,255,255,0.06)"
        watermark_color = "rgba(0,30,43,0.06)" if is_light else "rgba(255,255,255,0.06)"
        card_bg = "rgba(255,255,255,0.85)" if is_light else "rgba(0,0,0,0.3)"

        # 1. Asymmetric Left Heavy Composition
        if style == "asymmetric_left":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 56px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden; border-left: 10px solid {accent};">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.18; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {border_color}; padding-bottom: 20px;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">VASUKISQUARE</span>
                <span style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: {meta_color}; background: {badge_bg}; padding: 4px 10px; border-radius: 4px;">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 20px; text-align: left;">
                {f'<div class="cover-icon-wrapper" style="margin-bottom: 4px;">{icon_svg}</div>' if icon_svg else ''}
                <div style="width: 50px; height: 3px; background-color: {accent};"></div>
                <h1 style="font-size: {title_size}px; font-weight: 700; line-height: 1.14; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                  {plan.title}
                </h1>
                {f'<p style="font-size: 15px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 540px; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
              </div>
              <div style="position: relative; z-index: 2; border-top: 1px solid {border_color}; padding-top: 20px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {meta_color};">
                <span style="color: {title_color}; font-weight: 600;">{plan.author}</span>
                <span style="letter-spacing: 0.5px;">VASUKISQUARE PUBLISHING</span>
              </div>
            </div>
            """

        # 2. Centered Editorial Composition
        elif style == "centered_editorial":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 64px 52px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden; text-align: center;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.16; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: {accent};">VASUKISQUARE</span>
                <div style="width: 32px; height: 2px; background-color: {accent}; opacity: 0.8;"></div>
                <span style="font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: {meta_color};">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; align-items: center; gap: 24px; max-width: 580px;">
                {f'<div class="cover-icon-wrapper" style="background: {badge_bg}; padding: 18px; border-radius: 50%; border: 1px solid {border_color};">{icon_svg}</div>' if icon_svg else ''}
                <h1 style="font-size: {title_size}px; font-weight: 700; line-height: 1.15; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                  {plan.title}
                </h1>
                {f'<div style="width: 64px; height: 2px; background: {accent};"></div>' if plan.subtitle else ''}
                {f'<p style="font-size: 15px; color: {subtitle_color}; line-height: 1.5; margin: 0; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
              </div>
              <div style="position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: 11px; color: {meta_color};">
                <span style="color: {title_color}; font-weight: 600; letter-spacing: 1px;">{plan.author}</span>
                <span style="font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase;">Technical Handbook Series</span>
              </div>
            </div>
            """

        # 3. Framed Technical Handbook Composition
        elif style == "framed_technical":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 32px; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
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
                  <span style="font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">VASUKISQUARE // {plan.category}</span>
                  <span style="font-family: monospace; font-size: 11px; color: {meta_color};">REF: {plan.cover_seed}</span>
                </div>

                <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 20px;">
                  {f'<div style="margin-bottom: 6px;">{icon_svg}</div>' if icon_svg else ''}
                  <span style="font-family: monospace; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: {accent}; background: {badge_bg}; display: inline-block; padding: 4px 8px; border-radius: 2px; width: fit-content;">ENGINEERING GUIDE</span>
                  <h1 style="font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  {f'<p style="font-size: 15px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 520px; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>

                <div style="position: relative; z-index: 2; border-top: 1px solid {border_color}; padding-top: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {meta_color};">
                  <span style="color: {title_color}; font-weight: 600;">{plan.author}</span>
                  <span style="font-family: monospace; font-size: 10px;">RELEASE EDITION</span>
                </div>
              </div>
            </div>
            """

        # 4. Dense Blueprint Composition
        elif style == "dense_blueprint":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.22; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid {accent}; padding-bottom: 16px;">
                <div>
                  <div style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">VASUKISQUARE TECHNICAL ARCHITECTURE</div>
                  <div style="font-size: 11px; color: {meta_color}; margin-top: 4px;">SYSTEM SPECIFICATION & IMPLEMENTATION HANDBOOK</div>
                </div>
                <div style="font-family: monospace; font-size: 11px; color: {title_color}; background: {badge_bg}; padding: 6px 12px; border-radius: 4px; border: 1px solid {border_color};">
                  v1.0 // {plan.cover_seed}
                </div>
              </div>

              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 20px;">
                <div style="display: flex; align-items: center; gap: 16px;">
                  {f'<div>{icon_svg}</div>' if icon_svg else ''}
                  <div style="height: 32px; width: 2px; background: {border_color};"></div>
                  <span style="font-family: monospace; font-size: 12px; letter-spacing: 1px; color: {accent}; text-transform: uppercase;">{plan.category}</span>
                </div>
                <h1 style="font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                  {plan.title}
                </h1>
                {f'<p style="font-size: 15px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 520px; word-break: break-word; border-left: 2px solid {accent}; padding-left: 14px;">{plan.subtitle}</p>' if plan.subtitle else ''}
              </div>

              <div style="position: relative; z-index: 2; background: {card_bg}; border: 1px solid {border_color}; border-radius: 6px; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {meta_color};">
                <div>AUTHOR: <strong style="color: {title_color};">{plan.author}</strong></div>
                <div>AUDIENCE: <strong style="color: {title_color};">{plan.audience}</strong></div>
                <div style="color: {accent}; font-weight: 600;">VERIFIED</div>
              </div>
            </div>
            """

        # 5. Large Typography & Typography-Only Composition
        elif style in ("large_typography", "typography_only"):
            large_size = title_size + 8
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 60px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.12; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 14px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase; color: {accent};">VASUKISQUARE</span>
                <span style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {meta_color};">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 24px;">
                <div style="font-size: 72px; font-weight: 800; line-height: 0.9; color: {watermark_color}; letter-spacing: -2px; user-select: none;">
                  #01
                </div>
                <h1 style="font-size: {large_size}px; font-weight: 800; line-height: 1.08; color: {title_color}; margin: 0; letter-spacing: -1px; word-break: break-word;">
                  {plan.title}
                </h1>
                <div style="width: 80px; height: 4px; background: {accent};"></div>
                {f'<p style="font-size: 16px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 520px; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
              </div>
              <div style="position: relative; z-index: 2; border-top: 1px solid {border_color}; padding-top: 20px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {meta_color};">
                <span style="color: {title_color}; font-weight: 600;">{plan.author}</span>
                <span style="letter-spacing: 1px;">AUTONOMOUS PUBLISHING</span>
              </div>
            </div>
            """

        # 6. Bottom Weighted Composition
        elif style == "bottom_weighted":
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 56px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.22; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">VASUKISQUARE</span>
                <span style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {meta_color};">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin-top: auto; padding-top: 80px; display: flex; flex-direction: column; gap: 20px;">
                {f'<div class="cover-icon-wrapper">{icon_svg}</div>' if icon_svg else ''}
                <div style="width: 40px; height: 3px; background: {accent};"></div>
                <h1 style="font-size: {title_size}px; font-weight: 700; line-height: 1.12; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                  {plan.title}
                </h1>
                {f'<p style="font-size: 15px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 520px; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
              </div>
              <div style="position: relative; z-index: 2; margin-top: 32px; border-top: 1px solid {border_color}; padding-top: 20px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {meta_color};">
                <span style="color: {title_color}; font-weight: 600;">{plan.author}</span>
                <span style="letter-spacing: 0.5px;">VASUKISQUARE ARCHITECTURE</span>
              </div>
            </div>
            """

        # 7. Vertical Split / Split Panel Composition
        elif style in ("vertical_split", "split_panel"):
            sidebar_bg = "rgba(0,30,43,0.04)" if is_light else "rgba(0,0,0,0.35)"
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; display: flex; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <!-- Left Sidebar Band -->
              <div style="width: 90px; background: {sidebar_bg}; border-right: 2px solid {accent}; padding: 48px 16px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; position: relative; z-index: 3;">
                <div style="writing-mode: vertical-rl; transform: rotate(180deg); font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: {accent};">
                  VASUKISQUARE
                </div>
                {f'<div style="margin: 20px 0;">{icon_svg}</div>' if icon_svg else ''}
                <div style="writing-mode: vertical-rl; transform: rotate(180deg); font-size: 10px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: {meta_color};">
                  {plan.category}
                </div>
              </div>

              <!-- Main Content Body -->
              <div style="flex: 1; padding: 56px 48px; display: flex; flex-direction: column; justify-content: space-between; position: relative; z-index: 2;">
                <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.16; pointer-events: none; overflow: hidden;">
                  {geometric_svg}
                </div>
                <div style="position: relative; z-index: 2; text-align: right; font-size: 11px; color: {meta_color}; letter-spacing: 1px;">
                  EDITION // {plan.cover_seed}
                </div>
                <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 20px;">
                  <h1 style="font-size: {title_size}px; font-weight: 700; line-height: 1.14; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                    {plan.title}
                  </h1>
                  <div style="width: 60px; height: 3px; background: {accent};"></div>
                  {f'<p style="font-size: 15px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 480px; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
                </div>
                <div style="position: relative; z-index: 2; border-top: 1px solid {border_color}; padding-top: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {meta_color};">
                  <span style="color: {title_color}; font-weight: 600;">{plan.author}</span>
                  <span>TECHNICAL HANDBOOK</span>
                </div>
              </div>
            </div>
            """

        # 8. Default Modern Geometric Composition
        else:
            return f"""
            <div class="cover-hero cover-hero-solid" style="background-color: {bg}; padding: 56px 48px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; width: 100%; min-height: 297mm; max-height: 297mm; box-sizing: border-box; position: relative; overflow: hidden;">
              <div class="cover-pattern-layer" style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.18; pointer-events: none; overflow: hidden;">
                {geometric_svg}
              </div>
              <div style="position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {border_color}; padding-bottom: 20px;">
                <span style="font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {accent};">VASUKISQUARE</span>
                <span style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: {meta_color};">{plan.category}</span>
              </div>
              <div style="position: relative; z-index: 2; margin: auto 0; display: flex; flex-direction: column; gap: 20px; text-align: {align};">
                {f'<div class="cover-icon-wrapper" style="margin-bottom: 6px;">{icon_svg}</div>' if icon_svg else ''}
                <div style="width: 50px; height: 3px; background-color: {accent}; margin: 4px 0;"></div>
                <h1 style="font-size: {title_size}px; font-weight: 700; line-height: 1.14; color: {title_color}; margin: 0; letter-spacing: -0.5px; word-break: break-word;">
                  {plan.title}
                </h1>
                {f'<p style="font-size: 15px; color: {subtitle_color}; line-height: 1.45; margin: 0; max-width: 520px; word-break: break-word;">{plan.subtitle}</p>' if plan.subtitle else ''}
              </div>
              <div style="position: relative; z-index: 2; border-top: 1px solid {border_color}; padding-top: 20px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {meta_color};">
                <span style="color: {title_color}; font-weight: 600;">{plan.author}</span>
                <span style="letter-spacing: 0.5px;">VASUKISQUARE TECHNICAL PUBLISHING</span>
              </div>
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

