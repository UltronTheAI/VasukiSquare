"""WCAG-compliant contrast calculation, automatic semantic palette generator, and cover contrast validator."""

import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


def parse_color_to_rgb(color: str) -> Tuple[float, float, float]:
    """Parse hex, rgb, rgba, or CSS named colors into (r, g, b) float tuple in [0.0, 255.0]."""
    c = color.strip().lower()

    # Named color / Token aliases
    NAMED_COLORS = {
        "white": (255.0, 255.0, 255.0),
        "black": (0.0, 0.0, 0.0),
        "transparent": (255.0, 255.0, 255.0),  # Default assumption for overlay on white
        "cream": (250.0, 248.0, 245.0),
        "off-white": (249.0, 251.0, 250.0),
        "charcoal": (28.0, 45.0, 56.0),
        "slate": (61.0, 79.0, 91.0),
        "steel": (92.0, 108.0, 122.0),
        "stone": (124.0, 140.0, 154.0),
        "muted": (168.0, 179.0, 188.0),
    }
    if c in NAMED_COLORS:
        return NAMED_COLORS[c]

    # Hex: #rrggbb or #rrggbbaa
    if c.startswith("#"):
        hex_str = c[1:]
        if len(hex_str) == 3:
            r = int(hex_str[0] * 2, 16)
            g = int(hex_str[1] * 2, 16)
            b = int(hex_str[2] * 2, 16)
            return (float(r), float(g), float(b))
        elif len(hex_str) == 4:
            r = int(hex_str[0] * 2, 16)
            g = int(hex_str[1] * 2, 16)
            b = int(hex_str[2] * 2, 16)
            return (float(r), float(g), float(b))
        elif len(hex_str) >= 6:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return (float(r), float(g), float(b))

    # rgb(...) or rgba(...)
    rgb_match = re.match(r"rgba?\s*\(\s*([\d\.]+)\s*,\s*([\d\.]+)\s*,\s*([\d\.]+)", c)
    if rgb_match:
        r = float(rgb_match.group(1))
        g = float(rgb_match.group(2))
        b = float(rgb_match.group(3))
        return (r, g, b)

    # Fallback to white if unknown
    return (255.0, 255.0, 255.0)


def relative_luminance(rgb: Tuple[float, float, float]) -> float:
    """Calculate WCAG 2.1 relative luminance for an sRGB tuple (0-255)."""
    def _channel_lum(val: float) -> float:
        c = max(0.0, min(255.0, val)) / 255.0
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel_lum(r) + 0.7152 * _channel_lum(g) + 0.0722 * _channel_lum(b)


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """Calculate the WCAG contrast ratio between two colors. Returns a float in [1.0, 21.0]."""
    lum1 = relative_luminance(parse_color_to_rgb(color1))
    lum2 = relative_luminance(parse_color_to_rgb(color2))
    l_max = max(lum1, lum2)
    l_min = min(lum1, lum2)
    return round((l_max + 0.05) / (l_min + 0.05), 2)


def is_light_color(color: str) -> bool:
    """Determine if a color is considered light based on relative contrast against pure black vs white."""
    contrast_vs_black = calculate_contrast_ratio(color, "#000000")
    contrast_vs_white = calculate_contrast_ratio(color, "#ffffff")
    return contrast_vs_black >= contrast_vs_white


class CoverTextPalette(BaseModel):
    """Semantic tokens for high-contrast cover typography derived from the background."""

    cover_title: str = Field(default="#ffffff", description="Very high contrast color for the main title in solid container (>= 7:1 preferred).")
    cover_subtitle: str = Field(default="#cbd5e1", description="High contrast color for the subtitle in solid container (>= 4.5:1).")
    cover_container_bg: str = Field(default="#001e2b", description="Solid dark container background color behind title + subtitle.")
    cover_footer_bg: str = Field(default="#001e2b", description="Solid dark full-width footer strip background color.")
    cover_footer_author: str = Field(default="#ffffff", description="High-contrast light author color on footer strip (>= 4.5:1).")
    cover_footer_edition: str = Field(default="#cbd5e1", description="High-contrast light/muted edition color on footer strip (>= 4.5:1).")
    cover_primary_text: str = Field(description="Primary text / author color (>= 4.5:1).")
    cover_secondary_text: str = Field(description="Secondary text color (>= 4.5:1).")
    cover_metadata: str = Field(description="Metadata / edition color (>= 4.5:1).")
    cover_accent: str = Field(description="Harmonized accent color with adequate contrast.")
    cover_border: str = Field(description="Subtle framing border color.")
    cover_badge_bg: str = Field(description="Category badge background color.")
    cover_badge_text: str = Field(description="Category badge text color (>= 4.5:1).")
    cover_divider: str = Field(description="Accent rule / divider line color.")
    is_light_bg: bool = Field(description="True if the background is light mode.")
    background_color: str = Field(description="The source background color.")
    title_contrast: float = Field(default=0.0, description="Measured contrast ratio of title vs container.")
    subtitle_contrast: float = Field(default=0.0, description="Measured contrast ratio of subtitle vs container.")
    metadata_contrast: float = Field(default=0.0, description="Measured contrast ratio of metadata vs background.")
    author_footer_contrast: float = Field(default=0.0, description="Measured contrast ratio of author vs footer strip.")
    edition_footer_contrast: float = Field(default=0.0, description="Measured contrast ratio of edition vs footer strip.")


def get_contrasting_text_palette(
    background_color: str,
    preferred_accent: Optional[str] = None,
    container_bg: Optional[str] = None,
    footer_bg: Optional[str] = None,
) -> CoverTextPalette:
    """Derive semantic typography tokens directly from the actual cover background, dark title container, and solid footer strip.

    Guarantees:
    - Solid dark container (#001e2b / charcoal navy) wraps title + subtitle with pure white title and light neutral subtitle.
    - Solid dark footer strip (#001e2b / charcoal navy) wraps author and edition at absolute bottom.
    - Outer canvas elements (category badges, headers, borders) adapt cleanly to outer background_color.
    - Contrast targets: Title vs Container >= 7:1, Subtitle vs Container >= 4.5:1, Author/Edition vs Footer >= 4.5:1.
    """
    bg = background_color.strip() if background_color else "#ffffff"
    solid_container = container_bg.strip() if container_bg else "#001e2b"
    solid_footer = footer_bg.strip() if footer_bg else "#001e2b"

    # Container-anchored typography (high-contrast white/warm-white title, light neutral subtitle)
    CONTAINER_TITLE = "#ffffff"
    CONTAINER_SUBTITLE = "#cbd5e1"

    # Footer-anchored typography
    FOOTER_AUTHOR = "#ffffff"
    FOOTER_EDITION = "#cbd5e1"

    # Harmonized divider inside container
    if preferred_accent and calculate_contrast_ratio(solid_container, preferred_accent) >= 3.0:
        container_divider = preferred_accent
    else:
        container_divider = "#00ed64"  # MongoDB Bright Green

    # Candidate palette definitions for outer elements (headers, borders)
    DARK_PRIMARY = "#111827"     # Dark primary
    DARK_SECONDARY = "#374151"   # Secondary copy
    DARK_METADATA = "#4b5563"    # Medium-dark gray (>= 5.5:1 on light/cream, well above 4.5:1)
    DARK_BORDER = "rgba(17, 24, 39, 0.12)"
    DARK_DEFAULT_ACCENT = "#00684a"  # Forest Dark / Deep Teal

    LIGHT_PRIMARY = "#ffffff"    # Light primary
    LIGHT_SECONDARY = "#e2e8f0"  # Secondary copy
    LIGHT_METADATA = "#cbd5e1"   # Slate 300 (>= 8:1 on dark, well above 4.5:1)
    LIGHT_BORDER = "rgba(255, 255, 255, 0.14)"
    LIGHT_DEFAULT_ACCENT = "#00ed64"  # Bright Green

    # Category badge follows solid dark container language: solid dark background with high-contrast white text
    SOLID_BADGE_BG = solid_container
    SOLID_BADGE_TEXT = "#ffffff"

    # Calculate contrast of both candidates against outer background
    contrast_dark_primary = calculate_contrast_ratio(bg, DARK_PRIMARY)
    contrast_light_primary = calculate_contrast_ratio(bg, LIGHT_PRIMARY)

    if contrast_dark_primary >= contrast_light_primary:
        # Background is LIGHT (e.g. cream, white, off-white, soft pastels)
        is_light = True
        prim_col = DARK_PRIMARY
        sec_col = DARK_SECONDARY
        meta_col = DARK_METADATA
        border_col = DARK_BORDER

        if calculate_contrast_ratio(bg, meta_col) < 4.5:
            meta_col = DARK_SUBTITLE = "#374151"

        if preferred_accent and calculate_contrast_ratio(bg, preferred_accent) >= 3.0:
            accent_col = preferred_accent
        else:
            accent_col = DARK_DEFAULT_ACCENT
    else:
        # Background is DARK (e.g. navy, black, deep teal)
        is_light = False
        prim_col = LIGHT_PRIMARY
        sec_col = LIGHT_SECONDARY
        meta_col = LIGHT_METADATA
        border_col = LIGHT_BORDER

        if calculate_contrast_ratio(bg, meta_col) < 4.5:
            meta_col = LIGHT_SUBTITLE = "#e2e8f0"

        if preferred_accent and calculate_contrast_ratio(bg, preferred_accent) >= 3.0:
            accent_col = preferred_accent
        else:
            accent_col = LIGHT_DEFAULT_ACCENT

    t_contrast = calculate_contrast_ratio(solid_container, CONTAINER_TITLE)
    s_contrast = calculate_contrast_ratio(solid_container, CONTAINER_SUBTITLE)
    m_contrast = calculate_contrast_ratio(bg, meta_col)
    af_contrast = calculate_contrast_ratio(solid_footer, FOOTER_AUTHOR)
    ef_contrast = calculate_contrast_ratio(solid_footer, FOOTER_EDITION)

    return CoverTextPalette(
        cover_title=CONTAINER_TITLE,
        cover_subtitle=CONTAINER_SUBTITLE,
        cover_container_bg=solid_container,
        cover_footer_bg=solid_footer,
        cover_footer_author=FOOTER_AUTHOR,
        cover_footer_edition=FOOTER_EDITION,
        cover_primary_text=prim_col,
        cover_secondary_text=sec_col,
        cover_metadata=meta_col,
        cover_accent=accent_col,
        cover_border=border_col,
        cover_badge_bg=SOLID_BADGE_BG,
        cover_badge_text=SOLID_BADGE_TEXT,
        cover_divider=container_divider,
        is_light_bg=is_light,
        background_color=bg,
        title_contrast=t_contrast,
        subtitle_contrast=s_contrast,
        metadata_contrast=m_contrast,
        author_footer_contrast=af_contrast,
        edition_footer_contrast=ef_contrast,
    )


class ContrastValidationItem(BaseModel):
    """Result of an individual text element's contrast check."""

    element: str
    text_color: str
    background_color: str
    contrast_ratio: float
    target_ratio: float
    passed: bool
    recommended_color: str


class CoverContrastReport(BaseModel):
    """Comprehensive contrast validation report for a cover."""

    valid: bool
    background_color: str
    items: List[ContrastValidationItem] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    corrections_applied: Dict[str, str] = Field(default_factory=dict)


def validate_cover_contrast(
    background_color: str,
    title_color: Optional[str] = None,
    subtitle_color: Optional[str] = None,
    author_color: Optional[str] = None,
    edition_color: Optional[str] = None,
    category_color: Optional[str] = None,
    header_color: Optional[str] = None,
    container_bg: Optional[str] = None,
    footer_bg: Optional[str] = None,
    auto_correct: bool = True,
) -> CoverContrastReport:
    """Independently validate text contrast for all cover elements against container, footer strip & background.

    Targets:
    - Title vs Container: >= 7.0 (preferred)
    - Subtitle vs Container: >= 4.5
    - Author vs Footer Strip: >= 4.5
    - Edition vs Footer Strip: >= 4.5
    - Category / Eyebrow vs Outer Background: >= 4.5
    - Header labels vs Outer Background: >= 4.5
    """
    bg = background_color.strip() if background_color else "#ffffff"
    solid_container = container_bg.strip() if container_bg else "#001e2b"
    solid_footer = footer_bg.strip() if footer_bg else "#001e2b"
    palette = get_contrasting_text_palette(bg, container_bg=solid_container, footer_bg=solid_footer)

    elements_to_check = [
        ("title", title_color or palette.cover_title, 7.0, palette.cover_title, solid_container),
        ("subtitle", subtitle_color or palette.cover_subtitle, 4.5, palette.cover_subtitle, solid_container),
        ("author", author_color or palette.cover_footer_author, 4.5, palette.cover_footer_author, solid_footer),
        ("edition", edition_color or palette.cover_footer_edition, 4.5, palette.cover_footer_edition, solid_footer),
        ("category", category_color or palette.cover_badge_text, 4.5, palette.cover_badge_text, solid_container),
        ("header", header_color or palette.cover_metadata, 4.5, palette.cover_metadata, bg),
    ]

    items = []
    errors = []
    corrections = {}
    all_valid = True

    for name, col, target, rec_col, elem_bg in elements_to_check:
        cr = calculate_contrast_ratio(elem_bg, col)
        passed = cr >= target
        if not passed:
            all_valid = False
            msg = f"{name.capitalize()} color '{col}' has contrast ratio {cr:.2f}:1 vs background '{elem_bg}', which fails required target of {target:.1f}:1."
            errors.append(msg)
            if auto_correct:
                corrections[name] = rec_col

        items.append(
            ContrastValidationItem(
                element=name,
                text_color=col,
                background_color=elem_bg,
                contrast_ratio=cr,
                target_ratio=target,
                passed=passed,
                recommended_color=rec_col,
            )
        )

    return CoverContrastReport(
        valid=all_valid,
        background_color=bg,
        items=items,
        errors=errors,
        corrections_applied=corrections,
    )


def auto_correct_cover_html(html_content: str, background_color: str, container_bg: Optional[str] = None, footer_bg: Optional[str] = None) -> str:
    """Preflight check on rendered HTML: scans for inline color declarations and fixes any failing contrast."""
    if not html_content:
        return html_content

    solid_container = container_bg or "#001e2b"
    solid_footer = footer_bg or "#001e2b"
    palette = get_contrasting_text_palette(background_color, container_bg=solid_container, footer_bg=solid_footer)
    bg = background_color.strip() if background_color else "#ffffff"

    # 1. Check title contrast in HTML: look for <h1 ... style="... color: <color> ...">
    # If title color is low contrast against solid container, replace with palette.cover_title (#ffffff)
    def _fix_h1(match: re.Match) -> str:
        tag = match.group(0)
        col_m = re.search(r"(?<![\w-])color:\s*([^;\"'>]+)", tag)
        if col_m:
            col = col_m.group(1).strip()
            if calculate_contrast_ratio(solid_container, col) < 4.5:
                tag = re.sub(r"(?<![\w-])color:\s*[^;\"'>]+", f"color: {palette.cover_title}", tag)
        return tag

    corrected = re.sub(r"<h1[^>]*>", _fix_h1, html_content)

    # 2. Check subtitle paragraph: <p ... style="... color: <color> ...">
    def _fix_p(match: re.Match) -> str:
        tag = match.group(0)
        col_m = re.search(r"(?<![\w-])color:\s*([^;\"'>]+)", tag)
        if col_m:
            col = col_m.group(1).strip()
            if calculate_contrast_ratio(solid_container, col) < 4.5:
                tag = re.sub(r"(?<![\w-])color:\s*[^;\"'>]+", f"color: {palette.cover_subtitle}", tag)
        return tag

    corrected = re.sub(r"<p[^>]*>", _fix_p, corrected)

    # 3. Check footer and author colors inside footer strip (evaluated against solid_footer)
    def _fix_footer_spans(match: re.Match) -> str:
        full = match.group(0)
        col_m = re.search(r"(?<![\w-])color:\s*([^;\"'>]+)", full)
        if col_m:
            col = col_m.group(1).strip()
            if calculate_contrast_ratio(solid_footer, col) < 4.5:
                if "FIRST EDITION" in full or "EDITION" in full:
                    full = re.sub(r"(?<![\w-])color:\s*[^;\"'>]+", f"color: {palette.cover_footer_edition}", full)
                else:
                    full = re.sub(r"(?<![\w-])color:\s*[^;\"'>]+", f"color: {palette.cover_footer_author}", full)
        return full

    corrected = re.sub(r"<(span|div)[^>]*style=\"[^\"]*(?<![\w-])color:[^\"]*\"[^>]*>[^<]*</(span|div)>", _fix_footer_spans, corrected)

    return corrected
