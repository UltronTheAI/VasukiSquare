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
HEADER_SAFE_ZONE_MM: float = HEADER_HEIGHT_MM + HEADER_GAP_MM  # 18.0mm

FOOTER_HEIGHT_MM: float = 10.0
FOOTER_GAP_MM: float = 6.0
FOOTER_SAFE_ZONE_MM: float = FOOTER_HEIGHT_MM + FOOTER_GAP_MM  # 16.0mm

# Total Vertical Usable Space inside page margins
USABLE_PAGE_HEIGHT_MM: float = PAGE_HEIGHT_MM - (MARGIN_TOP_MM + MARGIN_BOTTOM_MM)  # 249.0mm
USABLE_PAGE_WIDTH_MM: float = PAGE_WIDTH_MM - (MARGIN_LEFT_MM + MARGIN_RIGHT_MM)   # 170.0mm

# Safe Content Height (Content region strictly between header and footer safe zones)
CONTENT_SAFE_HEIGHT_MM: float = USABLE_PAGE_HEIGHT_MM - (HEADER_SAFE_ZONE_MM + FOOTER_SAFE_ZONE_MM)  # 215.0mm

# Table & Component bottom breathing gap before footer safe zone
MIN_FOOTER_BREATHING_GAP_MM: float = 8.0


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
    """Geometry specification container for rendering inspection."""

    page_width_mm: float = PAGE_WIDTH_MM
    page_height_mm: float = PAGE_HEIGHT_MM
    margin_top_mm: float = MARGIN_TOP_MM
    margin_bottom_mm: float = MARGIN_BOTTOM_MM
    margin_left_mm: float = MARGIN_LEFT_MM
    margin_right_mm: float = MARGIN_RIGHT_MM
    header_safe_zone_mm: float = HEADER_SAFE_ZONE_MM
    footer_safe_zone_mm: float = FOOTER_SAFE_ZONE_MM
    usable_height_mm: float = USABLE_PAGE_HEIGHT_MM
    usable_width_mm: float = USABLE_PAGE_WIDTH_MM
    content_safe_height_mm: float = CONTENT_SAFE_HEIGHT_MM
    min_footer_gap_mm: float = MIN_FOOTER_BREATHING_GAP_MM

