"""Unit tests for Lucide SVG icon handling and token styling."""

import pytest
from vasukisquare.design.icons import LucideIcon, render_lucide_icon
from vasukisquare.design.tokens import ColorToken


def test_lucide_icon_rendering():
    svg = render_lucide_icon("sparkles", color=ColorToken.BRAND_GREEN, size=24)
    assert "<svg" in svg
    assert 'class="lucide lucide-sparkles"' in svg
    assert f'stroke="{ColorToken.BRAND_GREEN.value}"' in svg
    assert 'width="24"' in svg
    assert 'height="24"' in svg


def test_lucide_icon_rejects_arbitrary_colors():
    with pytest.raises(ValueError):
        LucideIcon(name="sparkles", color="#123456")  # type: ignore


def test_custom_svg_path():
    icon = LucideIcon(
        name="custom",
        color=ColorToken.PRIMARY,
        custom_path='<circle cx="5" cy="5" r="5"/>',
    )
    svg = icon.to_svg()
    assert '<circle cx="5" cy="5" r="5"/>' in svg

