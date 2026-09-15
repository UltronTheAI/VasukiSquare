"""Style definitions, color palettes, and topic-compatibility selector for VasukiSquare covers."""

import enum
import random
from typing import Dict, List, Optional
from vasukisquare.book.models import BookIntent
from vasukisquare.cover.contrast import get_contrasting_text_palette, CoverTextPalette


class CoverStyle(str, enum.Enum):
    """The 10 distinct cover style families."""

    EDITORIAL_MINIMAL = "editorial_minimal"
    MOUNTAIN_LANDSCAPE = "mountain_landscape"
    OCEAN_HORIZON = "ocean_horizon"
    SKY_CLOUDS = "sky_clouds"
    ABSTRACT_GEOMETRIC = "abstract_geometric"
    TYPOGRAPHIC_POSTER = "typographic_poster"
    BOTANICAL_ORGANIC = "botanical_organic"
    TERRAIN_JOURNEY = "terrain_journey"
    SYMBOLIC_OBJECT = "symbolic_object"
    CINEMATIC_LANDSCAPE = "cinematic_landscape"


ALL_COVER_STYLES = [s.value for s in CoverStyle]


# Curated Light Background Palettes (Full Bleed Light Canvas strictly from DESIGN.md tokens)
COVER_LIGHT_PALETTES = [
    {"name": "canvas_white", "bg": "#ffffff", "card_bg": "rgba(255,255,255,0.7)", "border": "rgba(17,24,39,0.10)"},
    {"name": "surface_pure", "bg": "#f9fbfa", "card_bg": "rgba(255,255,255,0.75)", "border": "rgba(17,24,39,0.10)"},
    {"name": "surface_soft", "bg": "#f4f7f6", "card_bg": "rgba(255,255,255,0.8)", "border": "rgba(17,24,39,0.09)"},
    {"name": "hairline_soft", "bg": "#eceff1", "card_bg": "rgba(255,255,255,0.8)", "border": "rgba(17,24,39,0.09)"},
    {"name": "surface_feature", "bg": "#e3fcef", "card_bg": "rgba(255,255,255,0.75)", "border": "rgba(17,24,39,0.10)"},
    {"name": "brand_green_soft", "bg": "#c3f0d2", "card_bg": "rgba(255,255,255,0.8)", "border": "rgba(17,24,39,0.09)"},
    {"name": "semantic_warning_bg", "bg": "#fff8e0", "card_bg": "rgba(255,255,255,0.7)", "border": "rgba(17,24,39,0.10)"},
]

# Monochrome Illustration Color Token Palette
MONO_PALETTE = {
    "black": "#111827",
    "charcoal": "#1f2937",
    "slate": "#374151",
    "muted_gray": "#6b7280",
    "light_gray": "#9ca3af",
    "subtle_border": "#e5e7eb",
    "pure_white": "#ffffff",
    "accent_dark": "#0f172a",
}


def get_style_weights_for_topic(topic: str, intent: Optional[BookIntent] = None) -> Dict[str, float]:
    """Calculate topic-compatibility weights for each cover style family."""
    t_lower = topic.lower()
    is_technical = intent.is_technical if intent else False
    book_type = intent.book_type.lower() if intent and intent.book_type else ""

    # Base neutral weights
    weights: Dict[str, float] = {
        CoverStyle.EDITORIAL_MINIMAL.value: 1.0,
        CoverStyle.MOUNTAIN_LANDSCAPE.value: 1.0,
        CoverStyle.OCEAN_HORIZON.value: 0.8,
        CoverStyle.SKY_CLOUDS.value: 0.8,
        CoverStyle.ABSTRACT_GEOMETRIC.value: 1.0,
        CoverStyle.TYPOGRAPHIC_POSTER.value: 1.0,
        CoverStyle.BOTANICAL_ORGANIC.value: 0.7,
        CoverStyle.TERRAIN_JOURNEY.value: 1.0,
        CoverStyle.SYMBOLIC_OBJECT.value: 1.2,
        CoverStyle.CINEMATIC_LANDSCAPE.value: 0.9,
    }

    # 1. Habits, Growth, Self-Improvement, Learning, Psychology
    if any(k in t_lower for k in ["habit", "growth", "discipline", "routine", "mindset", "productivity", "journey", "life", "success", "leader", "focus", "goal", "improve"]):
        weights[CoverStyle.TERRAIN_JOURNEY.value] = 3.5
        weights[CoverStyle.EDITORIAL_MINIMAL.value] = 2.5
        weights[CoverStyle.SYMBOLIC_OBJECT.value] = 2.5
        weights[CoverStyle.TYPOGRAPHIC_POSTER.value] = 2.0
        weights[CoverStyle.MOUNTAIN_LANDSCAPE.value] = 2.0
        weights[CoverStyle.BOTANICAL_ORGANIC.value] = 1.2
        weights[CoverStyle.OCEAN_HORIZON.value] = 1.0
        weights[CoverStyle.ABSTRACT_GEOMETRIC.value] = 0.5

    # 2. Software Engineering, Programming, Systems, AI, Data, Cloud, Architecture
    elif is_technical or any(k in t_lower for k in ["python", "rust", "go", "javascript", "code", "programming", "software", "system", "database", "ai", "machine learning", "cloud", "docker", "kubernetes", "network", "api", "architecture", "devops", "security"]):
        weights[CoverStyle.ABSTRACT_GEOMETRIC.value] = 3.5
        weights[CoverStyle.SYMBOLIC_OBJECT.value] = 3.0
        weights[CoverStyle.TYPOGRAPHIC_POSTER.value] = 2.5
        weights[CoverStyle.EDITORIAL_MINIMAL.value] = 2.0
        weights[CoverStyle.CINEMATIC_LANDSCAPE.value] = 1.0
        weights[CoverStyle.MOUNTAIN_LANDSCAPE.value] = 0.6
        weights[CoverStyle.TERRAIN_JOURNEY.value] = 0.5
        weights[CoverStyle.BOTANICAL_ORGANIC.value] = 0.1
        weights[CoverStyle.OCEAN_HORIZON.value] = 0.3
        weights[CoverStyle.SKY_CLOUDS.value] = 0.3

    # 3. Nature, Environment, Health, Wellness, Philosophy, Biology
    elif any(k in t_lower for k in ["nature", "garden", "biology", "health", "wellness", "meditation", "organic", "plant", "food", "environment", "climate", "forest", "peace"]):
        weights[CoverStyle.BOTANICAL_ORGANIC.value] = 3.5
        weights[CoverStyle.EDITORIAL_MINIMAL.value] = 2.5
        weights[CoverStyle.OCEAN_HORIZON.value] = 2.0
        weights[CoverStyle.MOUNTAIN_LANDSCAPE.value] = 2.0
        weights[CoverStyle.SKY_CLOUDS.value] = 1.8
        weights[CoverStyle.TERRAIN_JOURNEY.value] = 1.5
        weights[CoverStyle.ABSTRACT_GEOMETRIC.value] = 0.3

    # 4. History, Philosophy, Society, Economics, Finance, Essays
    elif any(k in t_lower for k in ["history", "philosophy", "economics", "finance", "money", "investing", "society", "essay", "culture", "civilization", "art", "music"]):
        weights[CoverStyle.EDITORIAL_MINIMAL.value] = 3.0
        weights[CoverStyle.TYPOGRAPHIC_POSTER.value] = 2.5
        weights[CoverStyle.SYMBOLIC_OBJECT.value] = 2.5
        weights[CoverStyle.CINEMATIC_LANDSCAPE.value] = 2.0
        weights[CoverStyle.MOUNTAIN_LANDSCAPE.value] = 1.5
        weights[CoverStyle.OCEAN_HORIZON.value] = 1.5
        weights[CoverStyle.ABSTRACT_GEOMETRIC.value] = 1.2

    # 5. Travel, Exploration, Astronomy, Future, Innovation
    elif any(k in t_lower for k in ["travel", "explore", "space", "sky", "astronomy", "universe", "future", "innovation", "science", "physics"]):
        weights[CoverStyle.SKY_CLOUDS.value] = 3.0
        weights[CoverStyle.CINEMATIC_LANDSCAPE.value] = 2.8
        weights[CoverStyle.MOUNTAIN_LANDSCAPE.value] = 2.2
        weights[CoverStyle.OCEAN_HORIZON.value] = 2.0
        weights[CoverStyle.ABSTRACT_GEOMETRIC.value] = 2.0
        weights[CoverStyle.SYMBOLIC_OBJECT.value] = 1.5

    return weights


def select_cover_style(topic: str, intent: Optional[BookIntent] = None, seed: Optional[int] = None) -> str:
    """Deterministically select a topic-compatible cover style using seeded random weights."""
    rng = random.Random(seed) if seed is not None else random.Random()
    weights_dict = get_style_weights_for_topic(topic, intent)

    styles = list(weights_dict.keys())
    weights = [weights_dict[s] for s in styles]

    return rng.choices(styles, weights=weights, k=1)[0]
