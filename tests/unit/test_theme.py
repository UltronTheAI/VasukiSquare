"""Unit tests for chapter theme selection."""

import pytest
from vasukisquare.design.theme import Theme, get_chapter_theme


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

