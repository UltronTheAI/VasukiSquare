"""Unit tests for CoverPlan model, geometric pattern generator, and CoverPlannerAgent."""

import asyncio
import pytest
from vasukisquare.book.models import CoverPlan
from vasukisquare.design.cover_patterns import CoverPatternGenerator
from vasukisquare.design.tokens import ColorToken
from vasukisquare.agents.cover import CoverPlannerAgent


def test_cover_plan_validation():
    plan = CoverPlan(
        title="High-Performance Database Internals",
        subtitle="Storage Engines, B-Trees, and LSM Trees",
        category="Database Systems",
        palette_theme="deep_teal",
        layout_style="orbital_rings",
        hero_icon="database",
        accent_color=ColorToken.BRAND_GREEN.value,
        background_color=ColorToken.BRAND_TEAL_DEEP.value,
    )
    assert plan.title == "High-Performance Database Internals"
    assert plan.accent_color == "#00ed64"
    assert plan.background_color == "#001e2b"


def test_cover_plan_rejects_arbitrary_colors():
    with pytest.raises(ValueError):
        CoverPlan(
            title="Invalid Colors Book",
            accent_color="#abcdef",  # Arbitrary color
            background_color="#123456",
        )


def test_geometric_pattern_generator():
    styles = ["orbital_rings", "tech_matrix", "layered_bands", "abstract_mesh", "minimal_geometric"]
    for s in styles:
        svg = CoverPatternGenerator.generate_pattern(
            style=s,
            accent_color=ColorToken.BRAND_GREEN.value,
            secondary_color=ColorToken.BRAND_TEAL.value,
            canvas_size=(1600, 2560),
        )
        assert len(svg) > 20
        assert f"stroke=\"{ColorToken.BRAND_GREEN.value}\"" in svg or f"fill=\"{ColorToken.BRAND_GREEN.value}\"" in svg


def test_cover_planner_agent_heuristic_selection():
    agent = CoverPlannerAgent()

    async def _test():
        plan = await agent.plan_cover(
            title="Deep Learning with PyTorch and Transformers",
            category="Artificial Intelligence",
        )
        assert plan.layout_style == "abstract_mesh"
        assert plan.hero_icon == "sparkles"
        assert plan.accent_color == ColorToken.ACCENT_PURPLE.value

    asyncio.run(_test())

