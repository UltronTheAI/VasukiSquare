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
        category: str = "Computer Science",
        tone: str = "authoritative",
        audience: str = "Engineers and Architects",
        technical_depth: str = "advanced",
        seed: Optional[int] = None,
        previous_cover: Optional[Union[CoverDesignPlan, dict]] = None,
    ) -> CoverDesignPlan:
        """Create a tailored, unique CoverDesignPlan using Groq or Ollama LLM with variation seed."""
        cover_seed = seed if seed is not None else random.randint(100000, 999999)

        if self.settings.vasukisquare_mock_mode:
            plan = self._heuristic_cover_plan(
                title=title,
                subtitle=subtitle,
                category=category,
                tone=tone,
                audience=audience,
                technical_depth=technical_depth,
                seed=cover_seed,
                previous_cover=previous_cover,
            )
            self._log_cover_result(plan, previous_cover)
            return plan

        prev_plan_obj: Optional[CoverDesignPlan] = None
        if isinstance(previous_cover, CoverDesignPlan):
            prev_plan_obj = previous_cover
        elif isinstance(previous_cover, dict):
            try:
                prev_plan_obj = CoverDesignPlan(**previous_cover)
            except Exception:
                pass

        prev_summary = ""
        if prev_plan_obj:
            prev_summary = (
                f"\n\nPREVIOUS COVER CHARACTERISTICS (DO NOT REUSE):\n"
                f"- Concept: {prev_plan_obj.concept_name}\n"
                f"- Composition style: {prev_plan_obj.composition_style}\n"
                f"- Title alignment: {prev_plan_obj.title_alignment}\n"
                f"- Title position: {prev_plan_obj.title_position}\n"
                f"- Icon strategy: {prev_plan_obj.icon_strategy}\n"
                f"- Border strategy: {prev_plan_obj.border_strategy}\n"
                f"- Decorative geometry: {prev_plan_obj.decorative_geometry}\n"
                f"INSTRUCTION: Art-direct a SUBSTANTIALLY DIFFERENT composition from the previous cover.\n"
            )

        system_prompt = (
            "You are a world-class executive art director for prestigious technical and editorial books. "
            "Design a distinctive, high-contrast, professional A4 cover layout following the VasukiSquare DESIGN.md system.\n\n"
            "DESIGN SPECIFICATIONS:\n"
            "1. Composition Families: choose one of [asymmetric_left, centered_editorial, bottom_weighted, top_heavy_minimal, "
            "large_typography, vertical_split, framed_technical, geometric_grid, diagonal_accent, icon_led, typography_only, "
            "split_panel, sparse_luxury, dense_blueprint, numeric_motif, abstract_lines].\n"
            "2. Title & Subtitle hierarchy: ensure the title is the commanding focal point. Scale typography according to title length.\n"
            "3. Icon Strategy: choose from [hero_top, integrated_badge, watermarked_background, bottom_corner, inline_prefix, none]. "
            "Some covers should be typography-only (icon_strategy='none').\n"
            "4. Decorative Geometry: choose topic-aligned geometry [database_nodes, circuit_grid, structural_rings, "
            "abstract_matrix, angular_lines, code_terminal_frame, dense_blueprint, orthogonal_axes, none].\n"
            "5. Palette Tokens: strictly map colors to DESIGN.md palette (brand_dark, deep_teal, accent_purple, accent_orange, accent_blue) "
            "with high contrast against dark backgrounds."
        )

        user_prompt = (
            f"Book Title: {title}\n"
            f"Subtitle: {subtitle or 'None'}\n"
            f"Category / Genre: {category}\n"
            f"Tone: {tone}\n"
            f"Target Audience: {audience}\n"
            f"Technical Depth: {technical_depth}\n"
            f"Variation Seed: {cover_seed}\n"
            f"{prev_summary}\n"
            f"Create the bespoke CoverDesignPlan for this book."
        )

        plan = None
        max_retries = self.settings.cover_max_retries if self.settings.cover_variation_enabled else 0

        for attempt in range(max_retries + 1):
            try:
                plan = await self.llm_client.invoke_structured(
                    schema=CoverDesignPlan,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    stage="cover_design_planning",
                    temperature=self.settings.cover_temperature,
                )

                plan.title = title
                plan.subtitle = subtitle
                plan.category = category
                plan.tone = tone
                plan.audience = audience
                plan.cover_seed = cover_seed

                # Diversity check against previous cover
                if prev_plan_obj and attempt < max_retries:
                    similarity = self.compute_similarity(plan, prev_plan_obj)
                    if similarity > 0.60:
                        logger.warning(
                            f"Cover plan attempt {attempt + 1} similarity {similarity:.2f} > 0.60 to previous cover. Retrying..."
                        )
                        user_prompt += (
                            f"\n\nFEEDBACK: The previous proposed concept '{plan.concept_name}' with composition '{plan.composition_style}' "
                            f"is too similar to the prior design (similarity: {similarity:.2f}). "
                            f"Please select an entirely different composition style and geometry!"
                        )
                        continue

                break

            except Exception as e:
                logger.warning(f"Cover design LLM call attempt {attempt + 1} failed: {e}")
                if attempt >= max_retries:
                    break

        if not plan:
            plan = self._heuristic_cover_plan(
                title=title,
                subtitle=subtitle,
                category=category,
                tone=tone,
                audience=audience,
                technical_depth=technical_depth,
                seed=cover_seed,
                previous_cover=previous_cover,
            )

        self._log_cover_result(plan, prev_plan_obj)
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

        # Shift choice using robust 32-bit golden ratio hash mixer of seed and title
        seed_hash = ((abs(seed) * 2654435761) ^ (len(title) * 97)) & 0xFFFFFFFF
        style_idx = seed_hash % len(styles)
        comp_style = styles[style_idx]

        # If previous cover had the same composition, rotate to next
        if previous_cover:
            prev_style = getattr(previous_cover, "composition_style", None) or (
                previous_cover.get("composition_style") if isinstance(previous_cover, dict) else None
            )
            if prev_style == comp_style:
                comp_style = styles[(style_idx + 1) % len(styles)]

        # Theme & Accents
        if any(w in t_lower for w in ["database", "storage", "vector", "distributed", "liorandb", "sql", "nosql"]):
            palette = "deep_teal"
            accent = ColorToken.BRAND_GREEN.value
            bg = ColorToken.BRAND_TEAL_DEEP.value
            hero_icon = "database"
            geometry = "database_nodes"
            concept = "Distributed Data Architecture"
        elif any(w in t_lower for w in ["ai", "neural", "learning", "model", "intelligence", "gpt", "llm"]):
            palette = "accent_purple"
            accent = ColorToken.ACCENT_PURPLE.value
            bg = ColorToken.BRAND_TEAL_DEEP.value
            hero_icon = "sparkles"
            geometry = "abstract_mesh"
            concept = "Neural Matrix Synthesis"
        elif any(w in t_lower for w in ["code", "programming", "python", "rust", "go", "typescript", "developer"]):
            palette = "brand_dark"
            accent = ColorToken.BRAND_GREEN.value
            bg = ColorToken.BRAND_TEAL_DEEP.value
            hero_icon = "code"
            geometry = "code_terminal_frame"
            concept = "Syntax & Runtime Blueprint"
        elif any(w in t_lower for w in ["cloud", "network", "system", "architecture", "sre", "kubernetes"]):
            palette = "accent_orange"
            accent = ColorToken.ACCENT_ORANGE.value
            bg = ColorToken.BRAND_TEAL_DEEP.value
            hero_icon = "layers"
            geometry = "circuit_grid"
            concept = "Cloud Topology Framework"
        else:
            palette = "brand_dark"
            accent = ColorToken.BRAND_GREEN.value
            bg = ColorToken.BRAND_TEAL_DEEP.value
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
            background_style="solid_dark",
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
            contrast_mode="high_contrast_dark",
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


