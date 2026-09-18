"""Tests for `visionarcade.rendering.themes`."""

from __future__ import annotations

from visionarcade.constants import THEMES
from visionarcade.rendering.themes import get_theme, theme_names


def test_theme_names_matches_constants_themes():
    assert set(theme_names()) == set(THEMES)


def test_get_theme_returns_the_requested_theme():
    theme = get_theme("neon")
    assert theme.name == "neon"


def test_get_theme_falls_back_to_default_on_unknown_name():
    theme = get_theme("not-a-real-theme")
    assert theme.name == "dark"


def test_every_theme_has_distinct_background_and_text_colors():
    for name in theme_names():
        theme = get_theme(name)
        assert theme.background != theme.text_primary
