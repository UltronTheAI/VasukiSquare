"""Design token definitions mapped from DESIGN.md."""

from enum import Enum
from pydantic import BaseModel, Field


class ColorToken(str, Enum):
    """Design color tokens as specified in DESIGN.md."""

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

    ACCENT_PURPLE = "#7b3ff2"
    ACCENT_ORANGE = "#fa6e39"
    ACCENT_PINK = "#f06bb8"
    ACCENT_BLUE = "#3d4f9f"

    SEMANTIC_WARNING_BG = "#fff8e0"
    SEMANTIC_WARNING_TEXT = "#946f3f"

    CANVAS = "#ffffff"
    CANVAS_DARK = "#001e2b"

    SURFACE = "#f9fbfa"
    SURFACE_SOFT = "#f4f7f6"
    SURFACE_FEATURE = "#e3fcef"

    HAIRLINE = "#e1e5e8"
    HAIRLINE_SOFT = "#eceff1"
    HAIRLINE_STRONG = "#c1ccd6"
    HAIRLINE_DARK = "#1c2d38"

    INK = "#001e2b"
    CHARCOAL = "#1c2d38"
    SLATE = "#3d4f5b"
    STEEL = "#5c6c7a"
    STONE = "#7c8c9a"
    MUTED = "#a8b3bc"

    ON_DARK = "#ffffff"
    ON_DARK_MUTED = "#a8b3bc"


class TypographySpec(BaseModel):
    """Typography specification rule."""

    font_family: str = "Euclid Circular A"
    font_size: str
    font_weight: int = 400
    line_height: float
    letter_spacing: str = "normal"


class DesignTokens(BaseModel):
    """Complete design token container."""

    colors: type[ColorToken] = ColorToken
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0
    cover_width_px: int = 1600
    cover_height_px: int = 2560

