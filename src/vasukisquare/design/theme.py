"""Theme selection rules for chapters and pages."""

from enum import Enum


class Theme(str, Enum):
    """Theme variants."""

    DARK = "dark"
    LIGHT = "light"


def get_chapter_theme(chapter_number: int) -> Theme:
    """Determine chapter theme based on chapter number.
    
    Rule from AGENTS.md / DESIGN.md:
    - Odd chapters use dark theme.
    - Even chapters use light theme.
    """
    if chapter_number <= 0:
        raise ValueError("Chapter number must be a positive integer (>= 1).")
    return Theme.DARK if chapter_number % 2 == 1 else Theme.LIGHT

