"""Cover Planner Agent designing bespoke, topic-aware covers across 10 style families."""

import logging
import random
from typing import Optional, Union
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.models import BookIntent, CoverDesignPlan
from vasukisquare.cover.styles import (
    ALL_COVER_STYLES,
    COVER_LIGHT_PALETTES,
    CoverStyle,
    select_cover_style,
)
from vasukisquare.design.tokens import ColorToken
from vasukisquare.llm.client import LLMClient
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger(__name__)


class CoverPlannerAgent:
    """Agent responsible for planning bespoke, diverse, subject-aware cover designs."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self.llm_client = llm_client or LLMClient(self.settings, self.metrics)

    def _derive_category_badge(self, topic: str, intent: Optional[BookIntent] = None) -> Optional[str]:
        """Derive a clean, professional category badge from BookIntent if appropriate."""
        if not intent:
            return None
        book_type = (intent.book_type or "").lower()
        t_lower = topic.lower()

        if "beginner" in book_type or "beginner" in t_lower:
            return "BEGINNER'S GUIDE"
        if "practical" in book_type or any(k in t_lower for k in ["habit", "routine", "productivity"]):
            return "PRACTICAL GUIDE"
        if "handbook" in book_type:
            return "TECHNICAL HANDBOOK"
        if "deep_dive" in book_type or intent.is_technical:
            return "TECHNICAL REFERENCE"
        if any(k in t_lower for k in ["leadership", "management", "business"]):
            return "EXECUTIVE BRIEFING"
        if any(k in t_lower for k in ["mindset", "life", "discipline", "growth"]):
            return "PERSONAL DEVELOPMENT"
        if any(k in t_lower for k in ["history", "civilization"]):
            return "HISTORICAL OVERVIEW"
        if any(k in t_lower for k in ["essay", "philosophy"]):
            return "ESSAYS & REFLECTIONS"
        return None

    def plan_cover(
        self,
        title: str,
        subtitle: Optional[str] = None,
        category: str = "General",
        tone: str = "authoritative",
        audience: str = "General Practitioners and Professionals",
        technical_depth: str = "intermediate",
        seed: Optional[int] = None,
        intent: Optional[BookIntent] = None,
        style_override: Optional[str] = None,
        author: str = "Vasuki",
        previous_cover: Optional[Union[CoverDesignPlan, dict]] = None,
    ) -> CoverDesignPlan:
        """Create a bespoke CoverDesignPlan across the 10 cover families with seeded determinism."""
        cover_seed = seed if seed is not None else random.randint(100000, 999999)
        rng = random.Random(cover_seed)

        # Style Selection
        if style_override and style_override in ALL_COVER_STYLES:
            cover_style = style_override
        else:
            cover_style = select_cover_style(topic=title, intent=intent, seed=cover_seed)

        # Ensure we rotate style if identical to previous cover
        if previous_cover:
            prev_style = getattr(previous_cover, "cover_style", None) or (
                previous_cover.get("cover_style") if isinstance(previous_cover, dict) else None
            )
            if prev_style == cover_style:
                available = [s for s in ALL_COVER_STYLES if s != prev_style]
                cover_style = rng.choice(available)

        # Background palette selection
        palette_choice = COVER_LIGHT_PALETTES[cover_seed % len(COVER_LIGHT_PALETTES)]
        bg_color = palette_choice["bg"]

        # Category badge derivation
        category_badge = self._derive_category_badge(topic=title, intent=intent)

        # Concept & Visual Subject derivation based on style
        t_lower = title.lower()
        if cover_style == CoverStyle.MOUNTAIN_LANDSCAPE.value:
            concept_name = "Monochrome Mountain Range"
            visual_subject = "Layered mountain ridge polygons with rising sun in negative space"
            mood = "expansive and enduring"
            title_align = rng.choice(["left", "center"])
            title_pos = "top"
        elif cover_style == CoverStyle.OCEAN_HORIZON.value:
            concept_name = "Minimalist Ocean Horizon"
            visual_subject = "Horizon divide with vector wave contours and subtle celestial reflection"
            mood = "calm and profound"
            title_align = "left"
            title_pos = "top"
        elif cover_style == CoverStyle.SKY_CLOUDS.value:
            concept_name = "Editorial Sky & Clouds"
            visual_subject = "Atmospheric cloud silhouettes with stars and birds in open sky"
            mood = "visionary and open"
            title_align = "left"
            title_pos = "middle"
        elif cover_style == CoverStyle.ABSTRACT_GEOMETRIC.value:
            concept_name = "Bauhaus Geometric Structure"
            visual_subject = "Concentric arcs, orthogonal precision grids, and intersecting geometry"
            mood = "analytical and rigorous"
            title_align = rng.choice(["left", "center"])
            title_pos = "middle"
        elif cover_style == CoverStyle.TYPOGRAPHIC_POSTER.value:
            concept_name = "Editorial Typographic Poster"
            visual_subject = "Oversized bold typography, architectural framing rules, and subtle numeral watermark"
            mood = "authoritative and commanding"
            title_align = "left"
            title_pos = "middle"
        elif cover_style == CoverStyle.BOTANICAL_ORGANIC.value:
            concept_name = "Botanical Line Art"
            visual_subject = "Monochrome curving stems and delicate stylized leaves"
            mood = "organic and reflective"
            title_align = "left"
            title_pos = "top"
        elif cover_style == CoverStyle.TERRAIN_JOURNEY.value:
            concept_name = "Perspective Horizon Path"
            visual_subject = "Winding perspective ribbon path through rolling hills toward sunrise"
            mood = "optimistic and purposeful"
            title_align = "left"
            title_pos = "top"
        elif cover_style == CoverStyle.SYMBOLIC_OBJECT.value:
            # Pick topic-relevant hero symbol
            if any(k in t_lower for k in ["habit", "routine", "time", "day", "calendar", "productivity"]):
                sym = "habit_loop"
                visual_subject = "Interlocking circular habit loop with calendar progression markers"
            elif any(k in t_lower for k in ["code", "python", "programming", "rust", "terminal", "software", "api"]):
                sym = "terminal_code"
                visual_subject = "Minimalist executable code terminal frame"
            elif any(k in t_lower for k in ["ai", "neural", "network", "system", "data", "graph"]):
                sym = "neural_nodes"
                visual_subject = "Interconnected node cluster"
            elif any(k in t_lower for k in ["law", "balance", "ethics", "justice", "finance"]):
                sym = "balance_scale"
                visual_subject = "Precision balance scale silhouette"
            elif any(k in t_lower for k in ["guide", "learn", "study", "read", "book"]):
                sym = "open_book"
                visual_subject = "Open architectural book silhouette"
            else:
                sym = "compass"
                visual_subject = "Navigation compass rose"

            concept_name = f"Hero Symbol: {sym.replace('_', ' ').title()}"
            mood = "focused and symbolic"
            title_align = "left"
            title_pos = "top"
        elif cover_style == CoverStyle.CINEMATIC_LANDSCAPE.value:
            concept_name = "Cinematic Horizon Silhouette"
            visual_subject = "80% open negative sky with tiny 20% low horizon silhouette and lone tree"
            mood = "cinematic and atmospheric"
            title_align = "left"
            title_pos = "middle"
        else:  # editorial_minimal
            concept_name = "Editorial Whitespace & Geometry"
            visual_subject = "Expansive negative space, fine column guide, and subtle geometric anchor"
            mood = "restrained and literary"
            title_align = "left"
            title_pos = "middle"

        plan = CoverDesignPlan(
            concept_name=concept_name,
            cover_style=cover_style,
            visual_subject=visual_subject,
            mood=mood,
            composition_style=cover_style,
            background_style="solid_light",
            title_alignment=title_align,
            title_position=title_pos,
            subtitle_position="below_title",
            typography_style="modern_technical",
            accent_elements=["horizontal_rule"],
            icon_strategy="none",
            hero_icon=None,
            border_strategy="none",
            spacing_strategy="expansive_negative_space",
            visual_density="moderate",
            density="minimal",
            contrast_mode="high_contrast_light",
            decorative_geometry=cover_style,
            category_badge=category_badge,
            rationale=f"Cover planned for '{title}' in {cover_style} style with seed {cover_seed}.",
            palette_theme=palette_choice["name"],
            accent_color=ColorToken.BRAND_TEAL.value,
            background_color=bg_color,
            title=title,
            subtitle=subtitle,
            category=category,
            tone=tone,
            audience=audience,
            author=author or "Vasuki",
            cover_seed=cover_seed,
        )

        logger.info(
            f"[COVER] style={plan.cover_style} seed={plan.cover_seed} "
            f"bg={plan.background_color} author={plan.author} title='{plan.title}'"
        )
        return plan

