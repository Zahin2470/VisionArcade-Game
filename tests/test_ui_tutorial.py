"""Tests for `visionarcade.ui.tutorial.TutorialScreen`."""

from __future__ import annotations

import pygame

from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.tutorial import TutorialScreen

DT = 1 / 60


def test_only_item_is_the_back_button():
    screen = TutorialScreen(1280, 720)
    ids = [item.item_id for item in screen._focus.items]
    assert ids == ["back"]


def test_enter_key_activates_back():
    screen = TutorialScreen(1280, 720)
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "back"


def test_escape_activates_back():
    screen = TutorialScreen(1280, 720)
    result = screen.update(DT, None, False, [pygame.K_ESCAPE])
    assert result == "back"


def test_pointer_confirm_on_back_button():
    screen = TutorialScreen(1280, 720)
    pointer = screen._back_rect.center
    screen.update(DT, pointer, False, [])
    result = screen.update(DT, pointer, True, [])
    assert result == "back"


def test_no_input_returns_none():
    screen = TutorialScreen(1280, 720)
    assert screen.update(DT, None, False, []) is None


def test_draw_does_not_raise(renderer):
    screen = TutorialScreen(renderer.surface.get_width(), renderer.surface.get_height())
    screen.draw(renderer.surface, Typography(), get_theme("dark"))


def test_draw_does_not_raise_for_every_theme(renderer):
    screen = TutorialScreen(renderer.surface.get_width(), renderer.surface.get_height())
    typography = Typography()
    for theme_name in ("dark", "light", "neon", "mono"):
        screen.draw(renderer.surface, typography, get_theme(theme_name))
