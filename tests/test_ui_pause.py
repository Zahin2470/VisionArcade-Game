"""Tests for `visionarcade.ui.pause.PauseScreen`."""

from __future__ import annotations

import pygame

from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.pause import PauseScreen

DT = 1 / 60


def test_on_enter_focuses_resume():
    screen = PauseScreen(1280, 720)
    screen._focus.move_focus(1)  # move away from resume first
    screen.on_enter()
    assert screen._focus.focused_id == "resume"


def test_enter_key_activates_focused_resume():
    screen = PauseScreen(1280, 720)
    screen.on_enter()
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "resume"


def test_escape_always_resumes_regardless_of_focus():
    screen = PauseScreen(1280, 720)
    screen.on_enter()
    screen._focus.move_focus(1)  # focus "restart"
    result = screen.update(DT, None, False, [pygame.K_ESCAPE])
    assert result == "resume"


def test_down_then_enter_activates_restart():
    screen = PauseScreen(1280, 720)
    screen.on_enter()
    screen.update(DT, None, False, [pygame.K_DOWN])
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "restart"


def test_pointer_confirm_activates_hovered_item():
    screen = PauseScreen(1280, 720)
    screen.on_enter()
    quit_item = next(i for i in screen._focus.items if i.item_id == "quit_to_hub")
    screen.update(DT, quit_item.rect.center, False, [])
    result = screen.update(DT, quit_item.rect.center, True, [])
    assert result == "quit_to_hub"


def test_no_input_returns_none():
    screen = PauseScreen(1280, 720)
    screen.on_enter()
    assert screen.update(DT, None, False, []) is None


def test_draw_does_not_raise(renderer):
    screen = PauseScreen(renderer.surface.get_width(), renderer.surface.get_height())
    screen.on_enter()
    screen.draw(renderer.surface, Typography(), get_theme("dark"))
