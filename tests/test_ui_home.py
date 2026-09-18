"""Tests for `visionarcade.ui.home.HomeScreen`."""

from __future__ import annotations

import pygame

from visionarcade.config import KNOWN_GAMES
from visionarcade.persistence.profiles import PlayerProfile
from visionarcade.persistence.scores import ScoresStore
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.home import HomeScreen

DT = 1 / 60


def _screen():
    return HomeScreen(1280, 720, ScoresStore(), PlayerProfile())


def test_layout_has_a_card_per_known_game_plus_three_actions():
    screen = _screen()
    ids = [item.item_id for item in screen._focus.items]
    for game_id in KNOWN_GAMES:
        assert f"play:{game_id}" in ids
    assert "settings" in ids
    assert "calibration" in ids
    assert "quit" in ids


def test_keyboard_right_then_enter_activates_second_item():
    screen = _screen()
    result = screen.update(DT, None, False, [pygame.K_RIGHT])
    assert result is None
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    # Second item should be the second known game's card.
    second_game = KNOWN_GAMES[1]
    assert result == f"play:{second_game}"


def test_quit_button_reachable_and_activatable():
    screen = _screen()
    for _ in range(len(screen._focus.items) - 1):
        screen.update(DT, None, False, [pygame.K_RIGHT])
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "quit"


def test_pointer_hover_and_confirm_selects_settings():
    screen = _screen()
    settings_item = next(i for i in screen._focus.items if i.item_id == "settings")
    pointer = settings_item.rect.center
    screen.update(DT, pointer, False, [])  # hover only
    result = screen.update(DT, pointer, True, [])  # pinch confirms
    assert result == "calibration" or result == "settings"
    assert result == "settings"


def test_no_input_returns_none():
    screen = _screen()
    assert screen.update(DT, None, False, []) is None


def test_draw_does_not_raise(renderer):
    screen = _screen()
    screen.draw(renderer.surface, Typography(), get_theme("dark"))


def test_refresh_updates_displayed_scores_and_profile():
    screen = _screen()
    new_scores = ScoresStore()
    new_scores.record_score(KNOWN_GAMES[0], 99, timestamp=1.0)
    new_profile = PlayerProfile(display_name="Abrar")
    screen.refresh(new_scores, new_profile)
    assert screen.scores.best_score(KNOWN_GAMES[0]) == 99
    assert screen.profile.display_name == "Abrar"
