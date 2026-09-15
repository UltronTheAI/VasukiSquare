"""Central physical page geometry, safe zones, and component bounding box definitions for A4."""

from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, Field


# Standard ISO 216 Physical A4 Dimensions
PAGE_WIDTH_MM: float = 210.0
PAGE_HEIGHT_MM: float = 297.0

# Physical Page Margins
MARGIN_TOP_MM: float = 24.0
MARGIN_BOTTOM_MM: float = 24.0
MARGIN_LEFT_MM: float = 20.0
MARGIN_RIGHT_MM: float = 20.0

# Safe Zone Heights (Reserved exclusively for header & footer chrome)
HEADER_HEIGHT_MM: float = 12.0
HEADER_GAP_MM: float = 6.0
HEADER_RESERVED_HEIGHT_MM: float = HEADER_HEIGHT_MM + HEADER_GAP_MM  # 18.0mm
HEADER_SAFE_ZONE_MM: float = HEADER_RESERVED_HEIGHT_MM

FOOTER_HEIGHT_MM: float = 10.0
FOOTER_GAP_MM: float = 6.0
FOOTER_RESERVED_HEIGHT_MM: float = FOOTER_HEIGHT_MM + FOOTER_GAP_MM  # 16.0mm
FOOTER_SAFE_ZONE_MM: float = FOOTER_RESERVED_HEIGHT_MM

# Mandatory Bottom Breathing Safety Gap before footer
BOTTOM_SAFETY_GAP_MM: float = 8.0
MIN_FOOTER_BREATHING_GAP_MM: float = BOTTOM_SAFETY_GAP_MM

# Renderer Rounding Tolerance (Epsilon)
SAFE_BOTTOM_EPSILON_MM: float = 1.0

# Usable Page Dimensions (between physical sheet margins)
USABLE_PAGE_HEIGHT_MM: float = PAGE_HEIGHT_MM - (MARGIN_TOP_MM + MARGIN_BOTTOM_MM)  # 249.0mm
USABLE_PAGE_WIDTH_MM: float = PAGE_WIDTH_MM - (MARGIN_LEFT_MM + MARGIN_RIGHT_MM)   # 170.0mm

# Canonical Absolute Content Safe Area (from page origin y=0)
CONTENT_TOP_MM: float = MARGIN_TOP_MM + HEADER_RESERVED_HEIGHT_MM  # 42.0mm
CONTENT_BOTTOM_MM: float = PAGE_HEIGHT_MM - MARGIN_BOTTOM_MM - FOOTER_RESERVED_HEIGHT_MM - BOTTOM_SAFETY_GAP_MM  # 225.0mm
AVAILABLE_CONTENT_HEIGHT_MM: float = CONTENT_BOTTOM_MM - CONTENT_TOP_MM  # 183.0mm
CONTENT_SAFE_HEIGHT_MM: float = AVAILABLE_CONTENT_HEIGHT_MM

# Inter-block gap inside .page-content flex container (16px @ 96 DPI)
BLOCK_GAP_MM: float = 4.23

# DPI and Unit Conversions (Standard CSS/PDF 96 DPI: 1in = 25.4mm, 1mm = 96/25.4 px)
MM_TO_PX_96DPI: float = 96.0 / 25.4  # ~3.779527559 px/mm
PX_TO_MM_96DPI: float = 25.4 / 96.0


def mm_to_px(mm: float, dpi: float = 96.0) -> float:
    """Convert millimeters to pixels at specified DPI (default 96 DPI)."""
    return mm * (dpi / 25.4)


def px_to_mm(px: float, dpi: float = 96.0) -> float:
    """Convert pixels to millimeters at specified DPI (default 96 DPI)."""
    return px * (25.4 / dpi)


@dataclass
class BoundingBox:
    """Represents a 2D bounding box in mm coordinates relative to page origin (top-left)."""

    x: float
    y: float
    width: float
    height: float

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    def intersects(self, other: "BoundingBox") -> bool:
        """Check if this bounding box overlaps another bounding box."""
        if self.right <= other.left or other.right <= self.left:
            return False
        if self.bottom <= other.top or other.bottom <= self.top:
            return False
        return True


class PageGeometrySpec(BaseModel):
    """Canonical printable safe-area geometry specification container."""

    page_width_mm: float = PAGE_WIDTH_MM
    page_height_mm: float = PAGE_HEIGHT_MM
    margin_top_mm: float = MARGIN_TOP_MM
    margin_bottom_mm: float = MARGIN_BOTTOM_MM
    margin_left_mm: float = MARGIN_LEFT_MM
    margin_right_mm: float = MARGIN_RIGHT_MM
    header_reserved_height_mm: float = HEADER_RESERVED_HEIGHT_MM
    footer_reserved_height_mm: float = FOOTER_RESERVED_HEIGHT_MM
    bottom_safety_gap_mm: float = BOTTOM_SAFETY_GAP_MM
    safe_bottom_epsilon_mm: float = SAFE_BOTTOM_EPSILON_MM
    content_top_mm: float = CONTENT_TOP_MM
    content_bottom_mm: float = CONTENT_BOTTOM_MM
    available_content_height_mm: float = AVAILABLE_CONTENT_HEIGHT_MM
    usable_height_mm: float = USABLE_PAGE_HEIGHT_MM
    usable_width_mm: float = USABLE_PAGE_WIDTH_MM
    block_gap_mm: float = BLOCK_GAP_MM

    # Aliases for backward compatibility
    header_safe_zone_mm: float = HEADER_SAFE_ZONE_MM
    footer_safe_zone_mm: float = FOOTER_SAFE_ZONE_MM
    content_safe_height_mm: float = CONTENT_SAFE_HEIGHT_MM
    min_footer_gap_mm: float = MIN_FOOTER_BREATHING_GAP_MM


