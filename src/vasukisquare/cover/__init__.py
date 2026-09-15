"""Cover Art System for VasukiSquare."""

from vasukisquare.cover.styles import ALL_COVER_STYLES, COVER_LIGHT_PALETTES, CoverStyle, select_cover_style
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
from vasukisquare.cover.planner import CoverPlannerAgent
from vasukisquare.cover.renderer import CoverRenderer, render_cover_gallery
from vasukisquare.cover.validator import CoverValidator, CoverValidationReport
from vasukisquare.cover.contrast import (
    CoverTextPalette,
    CoverContrastReport,
    ContrastValidationItem,
    calculate_contrast_ratio,
    get_contrasting_text_palette,
    validate_cover_contrast,
    auto_correct_cover_html,
    is_light_color,
)

__all__ = [
    "ALL_COVER_STYLES",
    "COVER_LIGHT_PALETTES",
    "CoverStyle",
    "select_cover_style",
    "CoverPlannerAgent",
    "CoverRenderer",
    "render_cover_gallery",
    "CoverValidator",
    "CoverValidationReport",
    "CoverTextPalette",
    "CoverContrastReport",
    "ContrastValidationItem",
    "calculate_contrast_ratio",
    "get_contrasting_text_palette",
    "validate_cover_contrast",
    "auto_correct_cover_html",
    "is_light_color",
    "generate_mountain_scenery",
    "generate_ocean_horizon",
    "generate_sky_clouds",
    "generate_abstract_geometric",
    "generate_typographic_poster_accents",
    "generate_botanical_foliage",
    "generate_terrain_journey",
    "generate_symbolic_object",
    "generate_cinematic_landscape",
    "generate_editorial_minimal",
]

