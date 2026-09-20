"""Tests for `visionarcade.ui.results.ResultsScreen`."""

from __future__ import annotations

import pygame

from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.results import ResultsScreen

DT = 1 / 60

_RESULTS = {
    "game_id": "catch",
    "score": 250,
    "outcome": "cleared",
    "lives_remaining": 2,
    "best_streak": 7,
    "elapsed_seconds": 90.0,
}


def test_on_enter_stores_results_and_best_flag():
    screen = ResultsScreen(1280, 720)
    screen.on_enter(_RESULTS, is_new_best=True)
    assert screen.results == _RESULTS
    assert screen.is_new_best is True


def test_enter_key_activates_first_focused_button():
    screen = ResultsScreen(1280, 720)
    screen.on_enter(_RESULTS, is_new_best=False)
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "play_again"


def test_navigating_to_last_button_activates_back_to_hub():
    screen = ResultsScreen(1280, 720)
    screen.on_enter(_RESULTS, is_new_best=False)
    for _ in range(len(screen._focus.items) - 1):
        screen.update(DT, None, False, [pygame.K_RIGHT])
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "back_to_hub"


def test_escape_returns_to_hub():
    screen = ResultsScreen(1280, 720)
    screen.on_enter(_RESULTS, is_new_best=False)
    result = screen.update(DT, None, False, [pygame.K_ESCAPE])
    assert result == "back_to_hub"


def test_pointer_confirm_activates_hovered_button():
    screen = ResultsScreen(1280, 720)
    screen.on_enter(_RESULTS, is_new_best=False)
    play_again_item = next(i for i in screen._focus.items if i.item_id == "play_again")
    screen.update(DT, play_again_item.rect.center, False, [])
    result = screen.update(DT, play_again_item.rect.center, True, [])
    assert result == "play_again"


def test_save_share_card_button_returns_its_action_id():
    screen = ResultsScreen(1280, 720)
    screen.on_enter(_RESULTS, is_new_best=False)
    screen.update(DT, None, False, [pygame.K_RIGHT])  # focus save_share_card (2nd item)
    result = screen.update(DT, None, False, [pygame.K_RETURN])
    assert result == "save_share_card"


def test_show_message_displays_and_expires():
    screen = ResultsScreen(1280, 720)
    screen.on_enter(_RESULTS, is_new_best=False)
    screen.show_message("Saved: test.png")
    assert screen._message_timer > 0
    for _ in range(1000):
        screen.update(DT, None, False, [])
        if screen._message_timer <= 0:
            break
    assert screen._message_timer == 0.0


def test_draw_with_active_message_does_not_raise(renderer):
    screen = ResultsScreen(renderer.surface.get_width(), renderer.surface.get_height())
    screen.on_enter(_RESULTS, is_new_best=False)
    screen.show_message("Saved: test.png")
    screen.draw(renderer.surface, Typography(), get_theme("dark"))


def test_draw_does_not_raise_for_cleared_outcome(renderer):
    screen = ResultsScreen(renderer.surface.get_width(), renderer.surface.get_height())
    screen.on_enter(_RESULTS, is_new_best=True)
    screen.draw(renderer.surface, Typography(), get_theme("dark"), game_title="Vision Catch")


def test_draw_does_not_raise_for_out_of_lives_outcome(renderer):
    screen = ResultsScreen(renderer.surface.get_width(), renderer.surface.get_height())
    results = dict(_RESULTS, outcome="out_of_lives")
    screen.on_enter(results, is_new_best=False)
    screen.draw(renderer.surface, Typography(), get_theme("neon"), game_title="Vision Catch")


def test_draw_does_not_raise_with_unknown_outcome(renderer):
    screen = ResultsScreen(renderer.surface.get_width(), renderer.surface.get_height())
    results = dict(_RESULTS, outcome="something_new")
    screen.on_enter(results, is_new_best=False)
    screen.draw(renderer.surface, Typography(), get_theme("dark"))
