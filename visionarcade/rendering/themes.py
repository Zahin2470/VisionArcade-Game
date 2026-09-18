"""Color themes: dark, light, neon, and a high-contrast-friendly mono.

Every color a screen needs comes from a `Theme` instance rather than
being hard-coded in UI drawing code, so switching `Settings.theme`
(or enabling high-contrast) restyles every screen consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from visionarcade.constants import DEFAULT_THEME

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    """A named palette covering every color a UI screen needs."""

    name: str
    background: Color
    surface: Color  # card/panel background
    surface_focused: Color  # card/panel background when focused/hovered
    text_primary: Color
    text_secondary: Color
    accent: Color
    border: Color
    success: Color
    danger: Color


_THEMES: dict[str, Theme] = {
    "dark": Theme(
        name="dark",
        background=(12, 14, 20),
        surface=(24, 27, 38),
        surface_focused=(38, 42, 58),
        text_primary=(230, 233, 240),
        text_secondary=(150, 155, 170),
        accent=(90, 170, 255),
        border=(60, 65, 85),
        success=(110, 220, 140),
        danger=(230, 90, 90),
    ),
    "light": Theme(
        name="light",
        background=(245, 246, 250),
        surface=(255, 255, 255),
        surface_focused=(228, 236, 250),
        text_primary=(25, 28, 35),
        text_secondary=(95, 100, 115),
        accent=(40, 110, 220),
        border=(210, 214, 224),
        success=(30, 150, 80),
        danger=(200, 50, 50),
    ),
    "neon": Theme(
        name="neon",
        background=(8, 6, 20),
        surface=(24, 14, 46),
        surface_focused=(46, 20, 82),
        text_primary=(240, 235, 255),
        text_secondary=(180, 150, 220),
        accent=(255, 60, 200),
        border=(120, 40, 160),
        success=(70, 255, 190),
        danger=(255, 70, 110),
    ),
    "mono": Theme(
        name="mono",
        background=(0, 0, 0),
        surface=(30, 30, 30),
        surface_focused=(60, 60, 60),
        text_primary=(255, 255, 255),
        text_secondary=(200, 200, 200),
        accent=(255, 255, 255),
        border=(255, 255, 255),
        success=(255, 255, 255),
        danger=(255, 255, 255),
    ),
}


def get_theme(name: str) -> Theme:
    """Return the named theme, falling back to the default on an
    unknown name rather than raising — a corrupted settings file
    should never make the UI un-renderable."""
    return _THEMES.get(name, _THEMES[DEFAULT_THEME])


def theme_names() -> Tuple[str, ...]:
    return tuple(_THEMES.keys())
