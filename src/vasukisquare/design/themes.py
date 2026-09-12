"""Centralized dynamic theme and color generation system for VasukiSquare books.

Generates a deterministic, high-contrast color palette once per book run, featuring
15 light backgrounds, 15 dark backgrounds, light-mode cover enforcement, and alternating chapter themes.
"""

import random
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


LIGHT_BACKGROUND_COLORS: List[str] = [
    "#F8FAFC",
    "#F1F5F9",
    "#FAFAF9",
    "#FFF7ED",
    "#FEFCE8",
    "#F0FDF4",
    "#ECFDF5",
    "#F0FDFA",
    "#ECFEFF",
    "#EFF6FF",
    "#EEF2FF",
    "#F5F3FF",
    "#FAF5FF",
    "#FDF2F8",
    "#FFF1F2",
]

DARK_BACKGROUND_COLORS: List[str] = [
    "#0F172A",
    "#111827",
    "#18181B",
    "#1C1917",
    "#172033",
    "#102A2E",
    "#11221A",
    "#18251D",
    "#102030",
    "#172554",
    "#1E1B4B",
    "#2E1065",
    "#3B0A45",
    "#3F172B",
    "#30151B",
]

# High-contrast accent palettes for Light and Dark modes
LIGHT_ACCENT_COLORS = [
    "#00684A",  # Deep brand green
    "#008C34",  # Forest green
    "#0284C7",  # Vibrant sky blue
    "#2563EB",  # Royal blue
    "#7C3AED",  # Deep purple
    "#C026D3",  # Fuchsia
    "#EA580C",  # Vibrant orange
    "#DC2626",  # Crimson
    "#0D9488",  # Teal
]

DARK_ACCENT_COLORS = [
    "#00ED64",  # Bright brand green
    "#38BDF8",  # Light sky
    "#818CF8",  # Indigo light
    "#A855F7",  # Purple bright
    "#F472B6",  # Pink
    "#FB923C",  # Orange bright
    "#34D399",  # Mint green
    "#2DD4BF",  # Cyan teal
    "#FBBF24",  # Amber
]


class SectionTheme(BaseModel):
    """Theme specification for an individual page or chapter section."""

    mode: str = Field(description="'light' or 'dark'")
    background: str = Field(description="Background hex color")
    foreground: str = Field(description="Primary text hex color")
    muted: str = Field(description="Secondary/muted text hex color")
    accent: str = Field(description="Accent highlight hex color")
    border: str = Field(description="Subtle border/divider hex color")
    surface: str = Field(description="Card/panel background hex color")


class BookThemeMap(BaseModel):
    """Deterministic theme map for the entire book, generated once before rendering."""

    cover: SectionTheme
    frontmatter: SectionTheme
    chapters: Dict[int, SectionTheme] = Field(default_factory=dict)
    acknowledgement: SectionTheme
    thank_you: SectionTheme
    seed: int = 42


def _build_light_theme(bg_color: str, accent_color: str) -> SectionTheme:
    return SectionTheme(
        mode="light",
        background=bg_color,
        foreground="#0F172A",
        muted="#64748B",
        accent=accent_color,
        border="rgba(15, 23, 42, 0.12)",
        surface="#FFFFFF",
    )


def _build_dark_theme(bg_color: str, accent_color: str) -> SectionTheme:
    return SectionTheme(
        mode="dark",
        background=bg_color,
        foreground="#F8FAFC",
        muted="#94A3B8",
        accent=accent_color,
        border="rgba(255, 255, 255, 0.14)",
        surface="rgba(255, 255, 255, 0.05)",
    )


def generate_book_theme(num_chapters: int = 6, seed: Optional[int] = None) -> BookThemeMap:
    """Generate the entire color/theme map for the book ONCE before page rendering begins.
    
    Rules:
    - Cover page: ALWAYS Light mode, selected from LIGHT_BACKGROUND_COLORS.
    - Chapters alternate:
        Chapter 1 = Dark
        Chapter 2 = Light
        Chapter 3 = Dark
        Chapter 4 = Light, etc.
    - Dark chapters use DARK_BACKGROUND_COLORS.
    - Light chapters use LIGHT_BACKGROUND_COLORS.
    - Consecutive section-opening pages avoid identical backgrounds.
    - Deterministic per seed.
    """
    actual_seed = seed if seed is not None else random.randint(100000, 999999)
    rng = random.Random(actual_seed)

    # 1. Cover: ALWAYS Light Mode
    cover_bg = rng.choice(LIGHT_BACKGROUND_COLORS)
    cover_accent = rng.choice(LIGHT_ACCENT_COLORS)
    cover_theme = _build_light_theme(cover_bg, cover_accent)

    # 2. Frontmatter (Title, Copyright, TOC)
    # Pick a light background distinct from cover if possible
    available_fm_bgs = [c for c in LIGHT_BACKGROUND_COLORS if c != cover_bg] or LIGHT_BACKGROUND_COLORS
    fm_bg = rng.choice(available_fm_bgs)
    fm_accent = cover_accent
    frontmatter_theme = _build_light_theme(fm_bg, fm_accent)

    # 3. Chapters (Alternating Dark / Light)
    chapters_map: Dict[int, SectionTheme] = {}
    last_dark_bg: Optional[str] = None
    last_light_bg: Optional[str] = fm_bg

    for ch_num in range(1, num_chapters + 1):
        if ch_num % 2 == 1:
            # Odd Chapter = Dark Mode
            available_dark = [c for c in DARK_BACKGROUND_COLORS if c != last_dark_bg] or DARK_BACKGROUND_COLORS
            ch_bg = rng.choice(available_dark)
            last_dark_bg = ch_bg
            ch_accent = rng.choice(DARK_ACCENT_COLORS)
            chapters_map[ch_num] = _build_dark_theme(ch_bg, ch_accent)
        else:
            # Even Chapter = Light Mode
            available_light = [c for c in LIGHT_BACKGROUND_COLORS if c != last_light_bg] or LIGHT_BACKGROUND_COLORS
            ch_bg = rng.choice(available_light)
            last_light_bg = ch_bg
            ch_accent = rng.choice(LIGHT_ACCENT_COLORS)
            chapters_map[ch_num] = _build_light_theme(ch_bg, ch_accent)

    # 4. Acknowledgements (Light or Soft Dark)
    ack_bg = rng.choice([c for c in LIGHT_BACKGROUND_COLORS if c != last_light_bg] or LIGHT_BACKGROUND_COLORS)
    ack_theme = _build_light_theme(ack_bg, rng.choice(LIGHT_ACCENT_COLORS))

    # 5. Thank You / Final Page (Warm Dark or Elegant Light)
    thank_you_bg = rng.choice(DARK_BACKGROUND_COLORS)
    thank_you_theme = _build_dark_theme(thank_you_bg, rng.choice(DARK_ACCENT_COLORS))

    return BookThemeMap(
        cover=cover_theme,
        frontmatter=frontmatter_theme,
        chapters=chapters_map,
        acknowledgement=ack_theme,
        thank_you=thank_you_theme,
        seed=actual_seed,
    )

