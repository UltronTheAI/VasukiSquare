"""Unit tests for DESIGN.md tokens."""

from vasukisquare.design.tokens import ColorToken, DesignTokens


def test_color_tokens_values():
    assert ColorToken.PRIMARY.value == "#00ed64"
    assert ColorToken.BRAND_GREEN.value == "#00ed64"
    assert ColorToken.BRAND_TEAL_DEEP.value == "#001e2b"
    assert ColorToken.CANVAS.value == "#ffffff"
    assert ColorToken.CANVAS_DARK.value == "#001e2b"


def test_design_tokens_dimensions():
    tokens = DesignTokens()
    assert tokens.page_width_mm == 210.0
    assert tokens.page_height_mm == 297.0
    assert tokens.cover_width_px == 1600
    assert tokens.cover_height_px == 2560

