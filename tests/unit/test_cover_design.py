"""Unit tests for CoverDesignPlan model, geometric pattern generator, and CoverPlannerAgent."""

import asyncio
import pytest
from vasukisquare.book.models import CoverDesignPlan
from vasukisquare.config import Settings
from vasukisquare.design.cover_patterns import CoverPatternGenerator
from vasukisquare.design.tokens import ColorToken
from vasukisquare.agents.cover import CoverPlannerAgent


def test_cover_design_plan_validation():
    """1. Verify CoverDesignPlan validates all structured fields and token colors correctly."""
    plan = CoverDesignPlan(
        concept_name="Distributed Mesh Architecture",
        composition_style="asymmetric_left",
        background_style="solid_dark",
        title_alignment="left",
        title_position="middle",
        subtitle_position="below_title",
        typography_style="modern_technical",
        accent_elements=["vertical_accent_bar"],
        icon_strategy="hero_top",
        hero_icon="database",
        border_strategy="left_accent_stripe",
        spacing_strategy="balanced_editorial",
        visual_density="moderate",
        contrast_mode="high_contrast_dark",
        decorative_geometry="database_nodes",
        rationale="Designed specifically for distributed databases.",
        palette_theme="deep_teal",
        accent_color=ColorToken.BRAND_GREEN.value,
        background_color=ColorToken.BRAND_TEAL_DEEP.value,
        title="High-Performance Database Internals",
        subtitle="Storage Engines, B-Trees, and LSM Trees",
        category="Database Systems",
        author="VasukiSquare AI Systems",
        cover_seed=948271,
    )
    assert plan.concept_name == "Distributed Mesh Architecture"
    assert plan.composition_style == "asymmetric_left"
    assert plan.layout_style == "asymmetric_left"
    assert plan.hero_icon == "database"
    assert plan.accent_color == "#00ed64"
    assert plan.background_color == "#001e2b"
    assert plan.cover_seed == 948271


def test_cover_plan_rejects_arbitrary_colors():
    """Verify CoverDesignPlan rejects non-DESIGN.md token colors."""
    with pytest.raises(ValueError):
        CoverDesignPlan(
            title="Invalid Colors Book",
            accent_color="#abcdef",  # Arbitrary color
            background_color="#123456",
        )


def test_different_seeds_produce_different_design_plans():
    """2. Verify different seeds generate different composition styles and design plans."""
    agent = CoverPlannerAgent(settings=Settings(vasukisquare_mock_mode=True))

    async def _test():
        plan1 = await agent.plan_cover(
            title="LioranDB for Noobs: From Zero Knowledge to Building Real Apps",
            category="Database Engineering",
            seed=111111,
        )
        plan2 = await agent.plan_cover(
            title="LioranDB for Noobs: From Zero Knowledge to Building Real Apps",
            category="Database Engineering",
            seed=999999,
        )
        assert plan1.cover_seed != plan2.cover_seed
        assert plan1.composition_style != plan2.composition_style or plan1.border_strategy != plan2.border_strategy

    asyncio.run(_test())


def test_similarity_score_and_diversity_detection():
    """7. Verify similarity score detects identical and distinct design plans."""
    plan_a = CoverDesignPlan(
        title="Python Guide",
        composition_style="asymmetric_left",
        title_alignment="left",
        icon_strategy="hero_top",
        border_strategy="left_accent_stripe",
        decorative_geometry="code_terminal_frame",
        title_position="middle",
        visual_density="moderate",
    )
    # Identical structure
    plan_b = CoverDesignPlan(
        title="Python Guide",
        composition_style="asymmetric_left",
        title_alignment="left",
        icon_strategy="hero_top",
        border_strategy="left_accent_stripe",
        decorative_geometry="code_terminal_frame",
        title_position="middle",
        visual_density="moderate",
    )
    # Very different structure
    plan_c = CoverDesignPlan(
        title="Python Guide",
        composition_style="centered_editorial",
        title_alignment="center",
        icon_strategy="none",
        border_strategy="none",
        decorative_geometry="dense_blueprint",
        title_position="top",
        visual_density="sparse",
    )

    sim_ab = CoverPlannerAgent.compute_similarity(plan_a, plan_b)
    sim_ac = CoverPlannerAgent.compute_similarity(plan_a, plan_c)

    assert sim_ab == 1.0
    assert sim_ac <= 0.15


def test_typography_only_and_icon_led_cover_modes():
    """10 & 11. Verify typography-only and icon-led cover configurations."""
    typo_plan = CoverDesignPlan(
        title="The Art of Software Engineering",
        composition_style="typography_only",
        icon_strategy="none",
        hero_icon=None,
    )
    assert typo_plan.icon_strategy == "none"
    assert typo_plan.hero_icon is None

    icon_plan = CoverDesignPlan(
        title="Vector Database Architecture",
        composition_style="icon_led",
        icon_strategy="hero_top",
        hero_icon="database",
    )
    assert icon_plan.icon_strategy == "hero_top"
    assert icon_plan.hero_icon == "database"


def test_geometric_pattern_generator_all_motifs():
    """Verify all parametric geometric SVG styles render valid SVG markup."""
    styles = [
        "orbital_rings",
        "tech_matrix",
        "layered_bands",
        "abstract_mesh",
        "minimal_geometric",
        "database_nodes",
        "circuit_grid",
        "dense_blueprint",
        "code_terminal_frame",
        "orthogonal_axes",
    ]
    for s in styles:
        svg = CoverPatternGenerator.generate_pattern(
            style=s,
            accent_color=ColorToken.BRAND_GREEN.value,
            secondary_color=ColorToken.BRAND_TEAL.value,
            canvas_size=(1600, 2560),
        )
        assert len(svg) > 20
        assert f"stroke=\"{ColorToken.BRAND_GREEN.value}\"" in svg or f"fill=\"{ColorToken.BRAND_GREEN.value}\"" in svg


