"""Unit tests for DESIGN.md tokens, CSS generation, and color validation."""

import pytest
from vasukisquare.design.tokens import (
    ColorToken,
    SpacingToken,
    RadiusToken,
    DesignTokens,
    validate_color_token,
    TYPOGRAPHY_SPECS,
    FONT_DISPLAY_STACK,
    FONT_CODE_STACK,
)


def test_color_tokens_values():
    assert ColorToken.PRIMARY.value == "#00ed64"
    assert ColorToken.BRAND_GREEN.value == "#00ed64"
    assert ColorToken.BRAND_TEAL_DEEP.value == "#001e2b"
    assert ColorToken.CANVAS.value == "#ffffff"
    assert ColorToken.CANVAS_DARK.value == "#001e2b"
    assert ColorToken.ACCENT_PURPLE.value == "#7b3ff2"
    assert ColorToken.ACCENT_ORANGE.value == "#fa6e39"


def test_validate_color_token_valid():
    assert validate_color_token("#00ed64") == ColorToken.BRAND_GREEN
    assert validate_color_token("#001E2B") == ColorToken.BRAND_TEAL_DEEP


def test_validate_color_token_rejects_arbitrary():
    with pytest.raises(ValueError) as exc:
        validate_color_token("#123456")
    assert "not a valid design token" in str(exc.value)

    with pytest.raises(ValueError):
        validate_color_token("rgb(255, 0, 0)")


def test_spacing_and_radius_tokens():
    assert SpacingToken.XXS.value == "4px"
    assert SpacingToken.MD.value == "16px"
    assert SpacingToken.HERO.value == "120px"

    assert RadiusToken.XS.value == "4px"
    assert RadiusToken.LG.value == "12px"
    assert RadiusToken.FULL.value == "9999px"


def test_typography_font_fallbacks():
    assert "Plus Jakarta Sans" in FONT_DISPLAY_STACK
    assert "JetBrains Mono" in FONT_CODE_STACK
    assert "hero-display" in TYPOGRAPHY_SPECS
    assert TYPOGRAPHY_SPECS["hero-display"].font_size == "72px"


def test_generate_css_variables():
    css_vars = DesignTokens.generate_css_variables()
    assert ":root {" in css_vars
    assert "--color-brand-green: #00ed64;" in css_vars
    assert "--color-brand-teal-deep: #001e2b;" in css_vars
    assert "--spacing-xl: 24px;" in css_vars
    assert "--radius-lg: 12px;" in css_vars
    assert "--font-code:" in css_vars
