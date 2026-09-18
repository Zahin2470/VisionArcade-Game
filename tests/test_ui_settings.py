"""Tests for `visionarcade.ui.settings.SettingsScreen`."""

from __future__ import annotations

import pygame

from visionarcade.persistence.settings import Settings
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.settings import SettingsScreen

DT = 1 / 60


def _screen(settings: Settings = None) -> SettingsScreen:
    return SettingsScreen(1280, 720, settings if settings is not None else Settings())


def _focus_row(screen: SettingsScreen, row_id: str) -> None:
    index = next(i for i, item in enumerate(screen._focus.items) if item.item_id == row_id)
    screen._focus._focus_index = index


def test_initial_focus_is_first_row():
    screen = _screen()
    assert screen._focus.focused_id == "theme"


def test_right_arrow_cycles_theme_forward():
    screen = _screen(Settings(theme="dark"))
    screen.update(DT, None, False, [pygame.K_RIGHT])
    assert screen.settings.theme == "light"


def test_left_arrow_cycles_theme_backward_and_wraps():
    screen = _screen(Settings(theme="dark"))
    screen.update(DT, None, False, [pygame.K_LEFT])
    assert screen.settings.theme == "mono"  # wraps to the last theme


def test_right_arrow_increases_master_volume():
    screen = _screen(Settings(master_volume=0.5))
    _focus_row(screen, "master_volume")
    screen.update(DT, None, False, [pygame.K_RIGHT])
    assert screen.settings.master_volume > 0.5


def test_volume_is_clamped_at_max():
    screen = _screen(Settings(master_volume=0.95))
    _focus_row(screen, "master_volume")
    screen.update(DT, None, False, [pygame.K_RIGHT])
    assert screen.settings.master_volume == 1.0


def test_enter_toggles_a_boolean_row():
    screen = _screen(Settings(muted=False))
    _focus_row(screen, "muted")
    screen.update(DT, None, False, [pygame.K_RETURN])
    assert screen.settings.muted is True


def test_pinch_confirm_toggles_focused_boolean_row():
    screen = _screen(Settings(high_contrast=False))
    _focus_row(screen, "high_contrast")
    screen.update(DT, None, True, [])  # pinch confirm, no keys
    assert screen.settings.high_contrast is True


def test_pinch_confirm_on_a_slider_row_steps_it_forward():
    screen = _screen(Settings(sensitivity=1.0))
    _focus_row(screen, "sensitivity")
    screen.update(DT, None, True, [])
    assert screen.settings.sensitivity > 1.0


def test_down_arrow_moves_focus_to_next_row():
    screen = _screen()
    screen.update(DT, None, False, [pygame.K_DOWN])
    assert screen._focus.focused_id == "master_volume"


def test_escape_returns_back():
    screen = _screen()
    result = screen.update(DT, None, False, [pygame.K_ESCAPE])
    assert result == "back"


def test_back_button_reachable_and_returns_back():
    screen = _screen()
    for _ in range(len(screen._focus.items) - 1):
        screen.update(DT, None, False, [pygame.K_DOWN])
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "back"


def test_reset_scores_row_returns_reset_scores():
    screen = _screen()
    _focus_row(screen, "reset_scores")
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "reset_scores"


def test_on_enter_loads_given_settings():
    screen = _screen()
    new_settings = Settings(theme="neon")
    screen.on_enter(new_settings)
    assert screen.settings.theme == "neon"


def test_draw_does_not_raise(renderer):
    screen = _screen()
    screen.draw(renderer.surface, Typography(), get_theme("dark"))
