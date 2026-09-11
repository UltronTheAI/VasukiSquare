"""Page layout types and definitions."""

from enum import Enum


class LayoutType(str, Enum):
    """Layout templates supported by the VasukiSquare design system."""

    COVER = "cover"
    COPYRIGHT = "copyright"
    TOC = "toc"
    CHAPTER_OPENER = "chapter_opener"
    TEXT_HEAVY = "text_heavy"
    CODE = "code"
    COMPARISON = "comparison"
    REFERENCES = "references"
    THANK_YOU = "thank_you"

