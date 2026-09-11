"""Design token definitions, font fallbacks, and CSS generator parsed from DESIGN.md."""

from enum import Enum
from typing import Dict, Optional, Set
from pydantic import BaseModel, Field


class ColorToken(str, Enum):
    """Design color tokens as specified in DESIGN.md."""

    # Brand & Primary
    PRIMARY = "#00ed64"
    PRIMARY_DEEP = "#00b545"
    PRIMARY_PRESSED = "#008c34"
    ON_PRIMARY = "#001e2b"

    BRAND_GREEN = "#00ed64"
    BRAND_GREEN_DARK = "#00684a"
    BRAND_GREEN_MID = "#00a35c"
    BRAND_GREEN_SOFT = "#c3f0d2"

    BRAND_TEAL_DEEP = "#001e2b"
    BRAND_TEAL = "#003d4f"
    BRAND_TEAL_MID = "#00684a"

    # Category Accents (Course/Topic tags)
    ACCENT_PURPLE = "#7b3ff2"
    ACCENT_ORANGE = "#fa6e39"
    ACCENT_PINK = "#f06bb8"
    ACCENT_BLUE = "#3d4f9f"

    # Semantic
    SEMANTIC_WARNING_BG = "#fff8e0"
    SEMANTIC_WARNING_TEXT = "#946f3f"

    # Surfaces & Canvas
    CANVAS = "#ffffff"
    CANVAS_DARK = "#001e2b"
    SURFACE = "#f9fbfa"
    SURFACE_SOFT = "#f4f7f6"
    SURFACE_FEATURE = "#e3fcef"

    # Borders & Dividers
    HAIRLINE = "#e1e5e8"
    HAIRLINE_SOFT = "#eceff1"
    HAIRLINE_STRONG = "#c1ccd6"
    HAIRLINE_DARK = "#1c2d38"

    # Text / Typography
    INK = "#001e2b"
    CHARCOAL = "#1c2d38"
    SLATE = "#3d4f5b"
    STEEL = "#5c6c7a"
    STONE = "#7c8c9a"
    MUTED = "#a8b3bc"

    ON_DARK = "#ffffff"
    ON_DARK_MUTED = "#a8b3bc"

    # Semantic Text Tokens (Light Theme)
    TEXT_PRIMARY = "#001e2b"       # Ink - 100% contrast on light canvas
    TEXT_SECONDARY = "#3d4f5b"     # Slate - High-contrast secondary text
    TEXT_MUTED = "#5c6c7a"         # Steel - Readable captions and running headers
    TEXT_SUBTLE = "#7c8c9a"        # Stone - Subtle metadata / borders

    # Semantic Text Tokens (Dark Theme)
    TEXT_PRIMARY_DARK = "#ffffff"  # On-Dark - 100% contrast on dark canvas
    TEXT_SECONDARY_DARK = "#e1e5e8"# Hairline - High-contrast secondary text on dark
    TEXT_MUTED_DARK = "#c1ccd6"    # Hairline-Strong - Readable captions & headers on dark
    TEXT_SUBTLE_DARK = "#a8b3bc"   # On-Dark Muted - Subtle metadata on dark


VALID_COLOR_VALUES: Set[str] = {c.value.lower() for c in ColorToken}


def validate_color_token(color: str) -> ColorToken:
    """Validate that a hex color string belongs strictly to DESIGN.md tokens."""
    c_clean = color.strip().lower()
    for token in ColorToken.__members__.values():
        if token.value.lower() == c_clean:
            return token
    raise ValueError(f"Color '{color}' is not a valid design token from DESIGN.md. Arbitrary colors are prohibited.")


class SpacingToken(str, Enum):
    """Spacing scale defined in DESIGN.md."""

    XXS = "4px"
    XS = "8px"
    SM = "12px"
    MD = "16px"
    LG = "20px"
    XL = "24px"
    XXL = "32px"
    XXXL = "40px"
    SECTION_SM = "48px"
    SECTION = "64px"
    SECTION_LG = "96px"
    HERO = "120px"


class RadiusToken(str, Enum):
    """Corner radii defined in DESIGN.md."""

    XS = "4px"
    SM = "6px"
    MD = "8px"
    LG = "12px"
    XL = "16px"
    XXL = "24px"
    FULL = "9999px"


# Configured open-source font stack replacing proprietary fonts while preserving geometry & metrics
FONT_DISPLAY_STACK = "'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_BODY_STACK = "'Inter', 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_CODE_STACK = "'JetBrains Mono', 'Fira Code', 'Source Code Pro', monospace"


class TypographySpec(BaseModel):
    """Typography specification rule."""

    font_family: str = FONT_BODY_STACK
    font_size: str
    font_weight: int = 400
    line_height: float
    letter_spacing: str = "normal"


TYPOGRAPHY_SPECS: Dict[str, TypographySpec] = {
    "hero-display": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="72px", font_weight=500, line_height=1.10, letter_spacing="-1.5px"),
    "display-lg": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="56px", font_weight=500, line_height=1.15, letter_spacing="-1px"),
    "heading-1": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="48px", font_weight=500, line_height=1.20, letter_spacing="-0.5px"),
    "heading-2": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="36px", font_weight=500, line_height=1.25, letter_spacing="-0.5px"),
    "heading-3": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="28px", font_weight=500, line_height=1.30, letter_spacing="normal"),
    "heading-4": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="22px", font_weight=500, line_height=1.35, letter_spacing="normal"),
    "heading-5": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="18px", font_weight=600, line_height=1.40, letter_spacing="normal"),
    "subtitle": TypographySpec(font_family=FONT_BODY_STACK, font_size="18px", font_weight=400, line_height=1.50, letter_spacing="normal"),
    "body-md": TypographySpec(font_family=FONT_BODY_STACK, font_size="16px", font_weight=400, line_height=1.55, letter_spacing="normal"),
    "body-md-medium": TypographySpec(font_family=FONT_BODY_STACK, font_size="16px", font_weight=500, line_height=1.55, letter_spacing="normal"),
    "body-sm": TypographySpec(font_family=FONT_BODY_STACK, font_size="14px", font_weight=400, line_height=1.50, letter_spacing="normal"),
    "body-sm-medium": TypographySpec(font_family=FONT_BODY_STACK, font_size="14px", font_weight=500, line_height=1.50, letter_spacing="normal"),
    "caption": TypographySpec(font_family=FONT_BODY_STACK, font_size="13px", font_weight=400, line_height=1.40, letter_spacing="normal"),
    "caption-bold": TypographySpec(font_family=FONT_BODY_STACK, font_size="13px", font_weight=600, line_height=1.40, letter_spacing="normal"),
    "micro": TypographySpec(font_family=FONT_BODY_STACK, font_size="12px", font_weight=500, line_height=1.40, letter_spacing="normal"),
    "micro-uppercase": TypographySpec(font_family=FONT_BODY_STACK, font_size="11px", font_weight=600, line_height=1.40, letter_spacing="1px"),
    "button-md": TypographySpec(font_family=FONT_DISPLAY_STACK, font_size="14px", font_weight=600, line_height=1.30, letter_spacing="normal"),
    "code-md": TypographySpec(font_family=FONT_CODE_STACK, font_size="13px", font_weight=400, line_height=1.55, letter_spacing="normal"),
}

# Semantic typography aliases mapped directly to DESIGN.md hierarchy tokens
SEMANTIC_TYPOGRAPHY_ALIASES: Dict[str, str] = {
    "page-title": "heading-1",
    "section-title": "heading-2",
    "subsection-title": "heading-3",
    "body": "body-md",
    "lead": "subtitle",
    "caption": "caption",
    "eyebrow": "micro-uppercase",
    "quote": "heading-4",
    "stat-number": "hero-display",
    "source-label": "caption-bold",
    "code": "code-md",
}


def resolve_typography_role(role: Optional[str]) -> TypographySpec:
    """Resolve a semantic typography role alias or token name to its TypographySpec."""
    if not role:
        return TYPOGRAPHY_SPECS["body-md"]
    role_key = role.strip().lower().replace("_", "-")
    target_token = SEMANTIC_TYPOGRAPHY_ALIASES.get(role_key, role_key)
    return TYPOGRAPHY_SPECS.get(target_token, TYPOGRAPHY_SPECS["body-md"])


class DesignTokens(BaseModel):
    """Complete container for the VasukiSquare design system."""

    colors: type[ColorToken] = ColorToken
    spacing: type[SpacingToken] = SpacingToken
    radii: type[RadiusToken] = RadiusToken
    typography: Dict[str, TypographySpec] = Field(default_factory=lambda: dict(TYPOGRAPHY_SPECS))
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0
    cover_width_px: int = 1600
    cover_height_px: int = 2560

    @classmethod
    def generate_css_variables(cls) -> str:
        """Generate standardized CSS custom properties from all design tokens."""
        lines = [":root {"]
        # Colors (iterating over all member names)
        seen_names = set()
        for name, token in ColorToken.__members__.items():
            clean_name = name.lower().replace("_", "-")
            if clean_name not in seen_names:
                seen_names.add(clean_name)
                lines.append(f"  --color-{clean_name}: {token.value};")

        # Spacing
        for name, token in SpacingToken.__members__.items():
            clean_name = name.lower().replace("_", "-")
            lines.append(f"  --spacing-{clean_name}: {token.value};")

        # Radii
        for name, token in RadiusToken.__members__.items():
            clean_name = name.lower().replace("_", "-")
            lines.append(f"  --radius-{clean_name}: {token.value};")

        # Fonts
        lines.append(f"  --font-display: {FONT_DISPLAY_STACK};")
        lines.append(f"  --font-body: {FONT_BODY_STACK};")
        lines.append(f"  --font-code: {FONT_CODE_STACK};")

        # Page Dimensions
        lines.append("  --page-width-mm: 210mm;")
        lines.append("  --page-height-mm: 297mm;")
        lines.append("}")
        return "\n".join(lines)
