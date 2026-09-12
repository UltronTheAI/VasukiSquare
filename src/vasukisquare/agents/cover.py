"""AI-directed Cover Planner Agent designing custom, diverse covers conforming to DESIGN.md."""

import logging
import random
from typing import Optional, Union
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.models import CoverDesignPlan, CoverPlan
from vasukisquare.design.tokens import ColorToken
from vasukisquare.llm.client import LLMClient
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger(__name__)


# Design-token compliant palettes for cover backgrounds and accents
COVER_LIGHT_BACKGROUNDS = [
    ColorToken.CANVAS.value,
    ColorToken.SURFACE.value,
    ColorToken.SURFACE_SOFT.value,
    ColorToken.SURFACE_FEATURE.value,
    ColorToken.BRAND_GREEN_SOFT.value,
    ColorToken.SEMANTIC_WARNING_BG.value,
]

COVER_ACCENT_TOKENS = [
    ColorToken.BRAND_TEAL.value,       # Deep Teal (#003d4f)
    ColorToken.BRAND_GREEN_DARK.value,  # Forest Dark (#00684a)
    ColorToken.ACCENT_BLUE.value,        # Navy / Blue (#3d4f9f)
    ColorToken.SLATE.value,              # Slate (#3d4f5b)
    ColorToken.CHARCOAL.value,           # Charcoal (#1c2d38)
    ColorToken.ACCENT_PURPLE.value,      # Muted Purple (#7b3ff2)
    ColorToken.ACCENT_ORANGE.value,      # Terracotta / Amber (#fa6e39)
    ColorToken.ACCENT_PINK.value,        # Burgundy / Rose (#f06bb8)
]


# List of standard approved composition families
COMPOSITION_FAMILIES = [
    "asymmetric_left",
    "centered_editorial",
    "bottom_weighted",
    "top_heavy_minimal",
    "large_typography",
    "vertical_split",
    "framed_technical",
    "geometric_grid",
    "diagonal_accent",
    "icon_led",
    "typography_only",
    "split_panel",
    "sparse_luxury",
    "dense_blueprint",
    "numeric_motif",
    "abstract_lines",
]

# Motif icons mapped to technical domains
APPROVED_HERO_ICONS = [
    "sparkles",
    "database",
    "code",
    "cpu",
    "layers",
    "terminal",
    "shield-check",
    "zap",
    "git-branch",
    "compass",
    "book-open",
    "globe",
]


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

    @staticmethod
    def compute_similarity(plan1: CoverDesignPlan, plan2: CoverDesignPlan) -> float:
        """Calculate similarity score (0.0 to 1.0) between two cover design plans."""
        score = 0.0
        total_weights = 7.0

        if plan1.title_alignment == plan2.title_alignment:
            score += 1.0
        if plan1.composition_style == plan2.composition_style:
            score += 1.5
        if plan1.icon_strategy == plan2.icon_strategy:
            score += 1.0
        if plan1.border_strategy == plan2.border_strategy:
            score += 1.0
        if plan1.decorative_geometry == plan2.decorative_geometry:
            score += 1.0
        if plan1.title_position == plan2.title_position:
            score += 0.75
        if plan1.visual_density == plan2.visual_density:
            score += 0.75

        return round(score / total_weights, 3)

    async def plan_cover(
        self,
        title: str,
        subtitle: Optional[str] = None,
        category: str = "General",
        tone: str = "authoritative",
        audience: str = "General Practitioners and Professionals",
        technical_depth: str = "intermediate",
        seed: Optional[int] = None,
        author: str = "Vasuki",
        previous_cover: Optional[Union[CoverDesignPlan, dict]] = None,
    ) -> CoverDesignPlan:
        """Create a tailored, unique CoverDesignPlan with 10 cover families with variation seed."""
        from vasukisquare.cover.planner import CoverPlannerAgent as ModularCoverPlanner
        modular_planner = ModularCoverPlanner(self.settings, self.llm_client, self.metrics)
        plan = modular_planner.plan_cover(
            title=title,
            subtitle=subtitle,
            category=category,
            tone=tone,
            audience=audience,
            technical_depth=technical_depth,
            seed=seed,
            author=author or "Vasuki",
            previous_cover=previous_cover,
        )
        self._log_cover_result(plan, previous_cover if isinstance(previous_cover, CoverDesignPlan) else None)
        return plan

    def _log_cover_result(self, plan: CoverDesignPlan, prev_plan: Optional[CoverDesignPlan]):
        similarity = self.compute_similarity(plan, prev_plan) if prev_plan else 0.0
        provider = getattr(self.llm_client, "active_provider", "offline")
        model = getattr(self.llm_client, "active_model", "deterministic")
        logger.info(
            f"[COVER] provider={provider} model={model} seed={plan.cover_seed} "
            f"composition={plan.composition_style} title_alignment={plan.title_alignment} "
            f"icon_strategy={plan.icon_strategy} similarity_to_previous={similarity:.2f} success=true"
        )

    def _heuristic_cover_plan(
        self,
        title: str,
        subtitle: Optional[str] = None,
        category: str = "Computer Science",
        tone: str = "authoritative",
        audience: str = "Engineers and Architects",
        technical_depth: str = "advanced",
        seed: int = 42,
        previous_cover: Optional[Union[CoverDesignPlan, dict]] = None,
    ) -> CoverDesignPlan:
        """Deterministic yet richly varied heuristic cover plan driven by seed and topic keywords."""
        t_lower = (title + " " + (subtitle or "") + " " + category).lower()

        # Deterministic style pool rotated by seed
        styles = [
            "asymmetric_left",
            "centered_editorial",
            "dense_blueprint",
            "large_typography",
            "framed_technical",
            "vertical_split",
            "geometric_grid",
            "bottom_weighted",
            "typography_only",
            "diagonal_accent",
            "abstract_lines",
            "icon_led",
        ]

        # Shift choice using robust hash mixer of seed and title with bit-shift dispersion
        seed_hash = ((abs(seed) * 104729) + ((abs(seed) >> 3) * 7919) ^ (len(title) * 97)) & 0xFFFFFFFF
        style_idx = seed_hash % len(styles)
        comp_style = styles[style_idx]

        # If previous cover had the same composition, rotate to next
        if previous_cover:
            prev_style = getattr(previous_cover, "composition_style", None) or (
                previous_cover.get("composition_style") if isinstance(previous_cover, dict) else None
            )
            if prev_style == comp_style:
                comp_style = styles[(style_idx + 1) % len(styles)]

        # Background color selected deterministically from token-compliant light backgrounds
        bg = COVER_LIGHT_BACKGROUNDS[seed_hash % len(COVER_LIGHT_BACKGROUNDS)]
        accent = COVER_ACCENT_TOKENS[(seed_hash + 1) % len(COVER_ACCENT_TOKENS)]

        # Theme & Accents
        if any(w in t_lower for w in ["database", "storage", "vector", "distributed", "liorandb", "sql", "nosql"]):
            palette = "deep_teal"
            hero_icon = "database"
            geometry = "database_nodes"
            concept = "Distributed Data Architecture"
        elif any(w in t_lower for w in ["ai", "neural", "learning", "model", "intelligence", "gpt", "llm"]):
            palette = "accent_purple"
            hero_icon = "sparkles"
            geometry = "abstract_matrix"
            concept = "Neural Matrix Synthesis"
        elif any(w in t_lower for w in ["code", "programming", "python", "rust", "go", "typescript", "developer"]):
            palette = "brand_dark"
            hero_icon = "code"
            geometry = "code_terminal_frame"
            concept = "Syntax & Runtime Blueprint"
        elif any(w in t_lower for w in ["cloud", "network", "system", "architecture", "sre", "kubernetes"]):
            palette = "accent_orange"
            hero_icon = "layers"
            geometry = "circuit_grid"
            concept = "Cloud Topology Framework"
        else:
            palette = "brand_dark"
            hero_icon = "compass"
            geometry = "orthogonal_axes"
            concept = "Foundational Engineering Guide"

        icon_strategy = "none" if comp_style in ("typography_only", "large_typography") else "hero_top"
        title_align = "center" if comp_style in ("centered_editorial", "framed_technical") else "left"
        title_pos = "lower_third" if comp_style == "bottom_weighted" else ("top" if comp_style == "top_heavy_minimal" else "middle")
        border_strat = "technical_corner_brackets" if comp_style == "framed_technical" else ("left_accent_stripe" if comp_style == "asymmetric_left" else "none")

        return CoverDesignPlan(
            concept_name=concept,
            composition_style=comp_style,
            background_style="solid_light",
            title_alignment=title_align,
            title_position=title_pos,
            subtitle_position="below_title",
            typography_style="modern_technical",
            accent_elements=["vertical_accent_bar" if comp_style == "asymmetric_left" else "horizontal_rule"],
            icon_strategy=icon_strategy,
            hero_icon=hero_icon,
            border_strategy=border_strat,
            spacing_strategy="balanced_editorial",
            visual_density="moderate",
            contrast_mode="high_contrast_light",
            decorative_geometry=geometry,
            rationale=f"Heuristic composition selected for {category} with seed {seed}.",
            palette_theme=palette,
            accent_color=accent,
            background_color=bg,
            title=title,
            subtitle=subtitle,
            category=category,
            tone=tone,
            audience=audience,
            author="VasukiSquare AI",
            cover_seed=seed,
        )



