"""Unit tests for chapter theme selection and dynamic BookThemeMap generation."""

import pytest
from vasukisquare.design.theme import Theme, get_chapter_theme
from vasukisquare.design.themes import (
    LIGHT_ACCENT_COLORS,
    LIGHT_BACKGROUND_COLORS,
    DARK_ACCENT_COLORS,
    DARK_BACKGROUND_COLORS,
    SectionTheme,
    generate_book_theme,
)


def test_odd_chapters_are_dark_theme():
    assert get_chapter_theme(1) == Theme.DARK
    assert get_chapter_theme(3) == Theme.DARK
    assert get_chapter_theme(5) == Theme.DARK


def test_even_chapters_are_light_theme():
    assert get_chapter_theme(2) == Theme.LIGHT
    assert get_chapter_theme(4) == Theme.LIGHT
    assert get_chapter_theme(6) == Theme.LIGHT


def test_invalid_chapter_number():
    with pytest.raises(ValueError):
        get_chapter_theme(0)
    with pytest.raises(ValueError):
        get_chapter_theme(-1)


def test_generate_book_theme_semantic_tokens_and_alternation():
    """Verify generated book theme map has complete semantic tokens and strict alternation."""
    theme_map = generate_book_theme(num_chapters=6, seed=42)

    # 1. Cover is ALWAYS light mode
    assert theme_map.cover.mode == "light"
    assert theme_map.cover.background in LIGHT_BACKGROUND_COLORS
    assert theme_map.cover.accent in LIGHT_ACCENT_COLORS
    assert theme_map.cover.foreground == "#0F172A"
    assert theme_map.cover.text_secondary == "#334155"
    assert theme_map.cover.text_muted == "#64748B"
    assert theme_map.cover.decorative.startswith("rgba(")

    # 2. Cover accent is never fluorescent / neon green
    assert theme_map.cover.accent.lower() != "#00ed64"
    assert theme_map.cover.accent.lower() != "#00ff00"

    # 3. Chapters alternate: 1=Dark, 2=Light, 3=Dark, 4=Light, 5=Dark, 6=Light
    assert theme_map.chapters[1].mode == "dark"
    assert theme_map.chapters[1].background in DARK_BACKGROUND_COLORS
    assert theme_map.chapters[1].accent in DARK_ACCENT_COLORS

    assert theme_map.chapters[2].mode == "light"
    assert theme_map.chapters[2].background in LIGHT_BACKGROUND_COLORS
    assert theme_map.chapters[2].accent in LIGHT_ACCENT_COLORS

    assert theme_map.chapters[3].mode == "dark"
    assert theme_map.chapters[4].mode == "light"
    assert theme_map.chapters[5].mode == "dark"
    assert theme_map.chapters[6].mode == "light"


def test_theme_properties_compatibility():
    """Verify SectionTheme property getters maintain backward compatibility."""
    sec = SectionTheme(
        mode="light",
        background="#FFFFFF",
        foreground="#001E2B",
        accent="#003D4F",
    )
    assert sec.background_color == "#FFFFFF"
    assert sec.accent_color == "#003D4F"
    assert sec.text_color == "#001E2B"
    assert sec.text_muted == "#64748B"
