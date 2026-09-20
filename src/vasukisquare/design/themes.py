"""Centralized dynamic theme, semantic token, and color harmonization system for VasukiSquare books.

Generates a deterministic, high-contrast, editorial color palette once per book run, featuring
15 light backgrounds, 15 dark backgrounds, light-mode cover enforcement, and alternating chapter themes.
Accents are restrained, calm, and harmonized with the chosen canvas background.
"""

import random
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# 15 Refined Editorial Light Backgrounds
LIGHT_BACKGROUND_COLORS: List[str] = [
    "#F8FAFC",  # Slate 50 - clean crisp paper
    "#F1F5F9",  # Slate 100 - soft technical paper
    "#FAFAF9",  # Stone 50 - warm minimal paper
    "#FFF7ED",  # Orange 50 - warm cream
    "#FEFCE8",  # Yellow 50 - soft parchment
    "#F0FDF4",  # Green 50 - pale sage mint
    "#ECFDF5",  # Emerald 50 - subtle celadon
    "#F0FDFA",  # Teal 50 - pale mint teal
    "#ECFEFF",  # Cyan 50 - crisp ice blue
    "#EFF6FF",  # Blue 50 - calm technical mist
    "#EEF2FF",  # Indigo 50 - soft blueprint paper
    "#F5F3FF",  # Violet 50 - gentle iris
    "#FAF5FF",  # Purple 50 - calm lilac
    "#FDF2F8",  # Pink 50 - rose dusk
    "#FFF1F2",  # Rose 50 - warm alabaster
]

# 15 Editorial Dark Backgrounds
DARK_BACKGROUND_COLORS: List[str] = [
    "#0F172A",  # Slate 900 - deep navy ink
    "#111827",  # Gray 900 - dark carbon
    "#18181B",  # Zinc 900 - dark graphite
    "#1C1917",  # Stone 900 - warm obsidian
    "#172033",  # Deep midnight slate
    "#102A2E",  # Deep marine teal
    "#11221A",  # Deep forest pine
    "#18251D",  # Dark cypress
    "#102030",  # Dark abyss navy
    "#172554",  # Blue 950 - deep royal
    "#1E1B4B",  # Indigo 950 - midnight blueprint
    "#2E1065",  # Purple 950 - dark imperial
    "#3B0A45",  # Dark plum
    "#3F172B",  # Dark mahogany
    "#30151B",  # Dark wine charcoal
]

# Restrained Editorial Accent Palettes for Light Backgrounds (Never Neon)
LIGHT_ACCENT_COLORS: List[str] = [
    "#003D4F",  # Deep Brand Teal
    "#00684A",  # Forest Deep Green
    "#1E3A8A",  # Classic Navy
    "#334155",  # Slate Charcoal
    "#881337",  # Deep Burgundy
    "#C2410C",  # Warm Terracotta
    "#166534",  # Deep Forest
    "#6B21A8",  # Muted Royal Violet
    "#0D9488",  # Slate Teal
    "#78350F",  # Warm Editorial Brown
    "#2563EB",  # Muted Royal Blue
    "#1C2D38",  # Ink Charcoal
]

# High-Contrast Harmonious Accent Palettes for Dark Backgrounds
DARK_ACCENT_COLORS: List[str] = [
    "#38BDF8",  # Light Sky Blue
    "#818CF8",  # Indigo Soft
    "#A855F7",  # Purple Bright
    "#F472B6",  # Rose Quartz
    "#FB923C",  # Warm Amber Orange
    "#34D399",  # Soft Mint Green
    "#2DD4BF",  # Soft Cyan Teal
    "#FBBF24",  # Soft Gold Amber
    "#60A5FA",  # Cornflower Blue
    "#A78BFA",  # Lavender Iris
]


class SectionTheme(BaseModel):
    """Complete semantic color tokens for a page, chapter, or book section."""

    mode: str = Field(description="'light' or 'dark'")
    background: str = Field(description="Canvas background hex color")
    foreground: str = Field(description="Primary high-contrast text color")
    text_secondary: str = Field(default="#334155", description="Secondary readable text color")
    text_muted: str = Field(default="#64748B", description="Muted captions / running header color")
    text_subtle: str = Field(default="#94A3B8", description="Subtle metadata / rule color")
    accent: str = Field(description="Primary editorial accent highlight color")
    accent_secondary: str = Field(default="#719F98", description="Harmonized secondary accent tint")
    border: str = Field(default="rgba(15, 23, 42, 0.12)", description="Subtle hairline border color")
    border_strong: str = Field(default="rgba(15, 23, 42, 0.24)", description="Emphasized border color")
    surface: str = Field(default="#FFFFFF", description="Card / panel surface background")
    surface_alt: str = Field(default="#F8FAFC", description="Alternative subtle card surface")
    muted: str = Field(default="#E2E8F0", description="Muted pill / tag background")
    decorative: str = Field(default="rgba(15, 23, 42, 0.04)", description="Subtle watermark / decorative color")
    code_background: str = Field(default="#F1F5F9", description="Code block background")
    terminal_background: str = Field(default="#0F172A", description="Terminal console background")

    @property
    def background_color(self) -> str:
        return self.background

    @property
    def accent_color(self) -> str:
        return self.accent

    @property
    def text_color(self) -> str:
        return self.foreground

    @property
    def border_color(self) -> str:
        return self.border

    @property
    def surface_bg(self) -> str:
        return self.surface

    @property
    def decorative_color(self) -> str:
        return self.decorative


class BookThemeMap(BaseModel):
    """Deterministic theme map for the entire book, generated once before rendering."""

    cover: SectionTheme
    frontmatter: SectionTheme
    chapters: Dict[int, SectionTheme] = Field(default_factory=dict)
    acknowledgement: SectionTheme
    thank_you: SectionTheme
    seed: int = 42

    @property
    def backmatter(self) -> SectionTheme:
        return self.thank_you


def _build_light_theme(bg_color: str, accent_color: str) -> SectionTheme:
    """Construct a high-contrast editorial Light SectionTheme with complete semantic tokens."""
    return SectionTheme(
        mode="light",
        background=bg_color,
        foreground="#0F172A",          # Slate 900: 100% contrast on light canvas
        text_secondary="#334155",      # Slate 700: clear secondary text
        text_muted="#64748B",          # Slate 500: captions & headers
        text_subtle="#94A3B8",         # Slate 400: subtle labels
        accent=accent_color,
        accent_secondary=accent_color + "99" if len(accent_color) == 7 else accent_color,
        border="rgba(15, 23, 42, 0.12)",
        border_strong="rgba(15, 23, 42, 0.24)",
        surface="#FFFFFF",
        surface_alt="#F8FAFC",
        muted="#E2E8F0",
        decorative="rgba(15, 23, 42, 0.04)",  # Ultra-subtle watermark
        code_background="#F8FAFC",
        terminal_background="#0F172A",
    )


def _build_dark_theme(bg_color: str, accent_color: str) -> SectionTheme:
    """Construct a high-contrast editorial Dark SectionTheme with complete semantic tokens."""
    return SectionTheme(
        mode="dark",
        background=bg_color,
        foreground="#F8FAFC",          # Slate 50: 100% contrast on dark canvas
        text_secondary="#E2E8F0",      # Slate 200: high contrast secondary on dark
        text_muted="#94A3B8",          # Slate 400: readable captions & headers on dark
        text_subtle="#64748B",         # Slate 500: subtle metadata
        accent=accent_color,
        accent_secondary=accent_color + "99" if len(accent_color) == 7 else accent_color,
        border="rgba(255, 255, 255, 0.14)",
        border_strong="rgba(255, 255, 255, 0.28)",
        surface="rgba(255, 255, 255, 0.05)",
        surface_alt="rgba(255, 255, 255, 0.08)",
        muted="rgba(255, 255, 255, 0.10)",
        decorative="rgba(255, 255, 255, 0.04)",  # Ultra-subtle watermark on dark
        code_background="#0B1120",
        terminal_background="#0B1120",
    )


def generate_book_theme(num_chapters: int = 6, seed: Optional[int] = None) -> BookThemeMap:
    """Generate the entire color/theme map for the book ONCE before page rendering begins.

    Rules:
    - Cover page: ALWAYS Light mode, selected from LIGHT_BACKGROUND_COLORS with restrained editorial accents.
    - Chapters alternate:
        Chapter 1 = Dark
        Chapter 2 = Light
        Chapter 3 = Dark
        Chapter 4 = Light, etc.
    - Dark chapters use DARK_BACKGROUND_COLORS.
    - Light chapters use LIGHT_BACKGROUND_COLORS.
    - Consecutive section-opening pages avoid identical backgrounds.
    - Accents harmonize with backgrounds (calm, editorial, zero neon).
    - Deterministic per seed.
    """
    actual_seed = seed if seed is not None else random.randint(100000, 999999)
    rng = random.Random(actual_seed)

    # 1. Cover: ALWAYS Light Mode with restrained accent
    cover_bg = rng.choice(LIGHT_BACKGROUND_COLORS)
    cover_accent = rng.choice(LIGHT_ACCENT_COLORS)
    cover_theme = _build_light_theme(cover_bg, cover_accent)

    # 2. Frontmatter (Title, Copyright, TOC)
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
