"""Tests for `visionarcade.arcade.games.catch.CatchGame`.

Deterministic throughout via a seeded `random.Random` injected as the
game's `rng` — spawn kind/position/timing jitter never depends on
real randomness, matching the project's "tests must be fast and
deterministic" rule. Visual-only screen-shake jitter uses a separate,
unseeded module-level RNG (see catch.py), so it never affects these
assertions.
"""

from __future__ import annotations

import random

from visionarcade.arcade.games.catch import CatchGame, _FallingObject, _Phase
from visionarcade.constants import (
    CATCH_COUNTDOWN_SECONDS,
    CATCH_GOOD_POINTS,
    CATCH_NEAR_MISS_DISTANCE,
    CATCH_ROUND_DURATION_SECONDS,
    CATCH_START_LIVES,
)
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent, HandIntent

WIDTH, HEIGHT = 1280, 720
DT = 1 / 60


def _game(seed: int = 1) -> CatchGame:
    return CatchGame(WIDTH, HEIGHT, get_theme("dark"), Typography(), rng=random.Random(seed))


def _intent_at(x: float, y: float) -> FrameIntent:
    right = HandIntent(handedness="Right", present=True, position=(x, y), index_tip=(x, y))
    return FrameIntent(left=HandIntent.absent("Left"), right=right)


def _no_hand() -> FrameIntent:
    return FrameIntent(left=HandIntent.absent("Left"), right=HandIntent.absent("Right"))


# --- Metadata / interface -----------------------------------------------------

def test_game_metadata():
    game = _game()
    assert game.id == "catch"
    assert game.title == "Vision Catch"
    assert game.objective


def test_starts_in_countdown_and_not_finished():
    game = _game()
    assert game._phase is _Phase.COUNTDOWN
    assert game.is_finished() is False


# --- Countdown -----------------------------------------------------------------

def test_countdown_transitions_to_playing():
    game = _game()
    game.handle_intent(_intent_at(0.5, 0.5))
    for _ in range(int(CATCH_COUNTDOWN_SECONDS / DT) + 5):
        game.update(DT)
    assert game._phase is _Phase.PLAYING


def test_catcher_can_be_positioned_during_countdown():
    game = _game()
    game.handle_intent(_intent_at(0.9, 0.5))
    game.update(DT)
    assert game._catcher_x > WIDTH / 2  # moved right, not stuck at center


# --- Catcher movement and bounds ----------------------------------------------

def test_catcher_is_clamped_within_play_area():
    game = _game()
    game.handle_intent(_intent_at(0.0, 0.5))  # far left
    game.update(DT)
    half_width = game._catcher_rect().width / 2
    assert game._catcher_x >= game.play_area.left + half_width - 1e-6


def test_catcher_position_unchanged_when_no_hand_present():
    game = _game()
    game.handle_intent(_intent_at(0.8, 0.5))
    game.update(DT)
    x_before = game._catcher_x
    game.handle_intent(_no_hand())
    game.update(DT)
    assert game._catcher_x == x_before


def _advance_past_countdown(game: CatchGame) -> None:
    game.handle_intent(_intent_at(0.5, 0.5))
    for _ in range(int(CATCH_COUNTDOWN_SECONDS / DT) + 2):
        game.update(DT)
    assert game._phase is _Phase.PLAYING


# --- Catching mechanics --------------------------------------------------------

def test_catching_a_good_object_scores_points_and_keeps_lives():
    game = _game()
    _advance_past_countdown(game)
    game._objects = [_FallingObject(x=game._catcher_x, y=game._catcher_rect().centery, kind="good")]
    lives_before = game._lives
    game.update(DT)
    # The first hit already carries ComboTracker's streak-1 multiplier (1.5x).
    assert game._score.score == round(CATCH_GOOD_POINTS * 1.5)
    assert game._lives == lives_before
    assert game._objects == []  # caught object is removed


def test_catching_a_hazard_costs_a_life_and_resets_combo():
    game = _game()
    _advance_past_countdown(game)
    game._combo.register_hit()
    game._objects = [_FallingObject(x=game._catcher_x, y=game._catcher_rect().centery, kind="hazard")]
    lives_before = game._lives
    game.update(DT)
    assert game._lives == lives_before - 1
    assert game._combo.streak == 0
    assert game._shake_time_remaining > 0


def test_catching_a_bonus_object_scores_flat_points():
    game = _game()
    _advance_past_countdown(game)
    game._objects = [_FallingObject(x=game._catcher_x, y=game._catcher_rect().centery, kind="bonus")]
    game.update(DT)
    from visionarcade.constants import CATCH_BONUS_POINTS

    assert game._score.score == CATCH_BONUS_POINTS


def test_missing_a_good_object_costs_a_life():
    game = _game()
    _advance_past_countdown(game)
    game._objects = [_FallingObject(x=game._catcher_x, y=game.play_area.bottom + 100, kind="good")]
    lives_before = game._lives
    game.update(DT)
    assert game._lives == lives_before - 1


def test_missing_a_bonus_object_has_no_penalty():
    game = _game()
    _advance_past_countdown(game)
    game._objects = [_FallingObject(x=game._catcher_x, y=game.play_area.bottom + 100, kind="bonus")]
    lives_before = game._lives
    game.update(DT)
    assert game._lives == lives_before


def test_avoiding_a_hazard_far_from_catcher_has_no_bonus():
    game = _game()
    _advance_past_countdown(game)
    far_x = game.play_area.left + 2  # far from wherever the catcher is
    game._catcher_x = game.play_area.right - 2
    game._objects = [_FallingObject(x=far_x, y=game.play_area.bottom + 100, kind="hazard")]
    score_before = game._score.score
    game.update(DT)
    assert game._score.score == score_before


def test_near_miss_on_a_hazard_grants_a_small_bonus():
    game = _game()
    _advance_past_countdown(game)
    catcher_rect = game._catcher_rect()
    near_x = catcher_rect.centerx + CATCH_NEAR_MISS_DISTANCE * 0.5
    # Just past the play area's bottom edge, as it would be the frame it's
    # first detected as missed (not 100px further down, which would put
    # it unrealistically far from the catcher for a "near miss" check).
    near_y = game.play_area.bottom + game._catcher_rect().height
    game._objects = [_FallingObject(x=near_x, y=near_y, kind="hazard")]
    score_before = game._score.score
    game.update(DT)
    assert game._score.score > score_before
    assert game._near_miss_banner_timer > 0


# --- Round-ending conditions -----------------------------------------------------

def test_round_ends_out_of_lives_when_lives_reach_zero():
    game = _game()
    _advance_past_countdown(game)
    game._lives = 1
    game._objects = [_FallingObject(x=game._catcher_x, y=game._catcher_rect().centery, kind="hazard")]
    game.update(DT)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "out_of_lives"


def test_round_ends_cleared_after_full_duration():
    game = _game()
    _advance_past_countdown(game)
    game._elapsed_playing = CATCH_ROUND_DURATION_SECONDS - DT / 2
    game._objects = []
    game.update(DT)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "cleared"


# --- get_results is safe at any time ------------------------------------------

def test_get_results_before_round_ends_reports_in_progress():
    game = _game()
    results = game.get_results()
    assert results["outcome"] == "in_progress"
    assert results["game_id"] == "catch"
    assert "score" in results and "best_streak" in results and "lives_remaining" in results


def test_reset_returns_to_a_clean_countdown_state():
    game = _game()
    _advance_past_countdown(game)
    game._score.add(100)
    game._lives = 0
    game.reset()
    assert game._phase is _Phase.COUNTDOWN
    assert game._score.score == 0
    assert game._lives == CATCH_START_LIVES
    assert game._objects == []


# --- Spawning / difficulty (deterministic via seeded rng) ----------------------

def test_objects_spawn_over_time_during_play():
    game = _game(seed=7)
    _advance_past_countdown(game)
    for _ in range(120):  # a couple of seconds
        game.update(DT)
    assert len(game._objects) > 0 or game._score.score > 0  # something happened


def test_spawned_objects_are_within_play_area_bounds():
    game = _game(seed=3)
    _advance_past_countdown(game)
    for _ in range(300):
        game.update(DT)
    for obj in game._objects:
        assert game.play_area.left <= obj.x <= game.play_area.right


def test_seeded_game_is_reproducible():
    game_a = _game(seed=99)
    game_b = _game(seed=99)
    _advance_past_countdown(game_a)
    _advance_past_countdown(game_b)
    for _ in range(180):
        game_a.update(DT)
        game_b.update(DT)
    assert game_a.get_results() == game_b.get_results()


# --- Drawing ---------------------------------------------------------------------

def test_draw_does_not_raise_in_every_phase(renderer):
    game = CatchGame(
        renderer.surface.get_width(),
        renderer.surface.get_height(),
        get_theme("dark"),
        Typography(),
        rng=random.Random(1),
    )
    game.draw(renderer.surface)  # COUNTDOWN

    _advance_past_countdown(game)
    game._objects = [
        _FallingObject(x=100, y=100, kind="good"),
        _FallingObject(x=200, y=150, kind="hazard"),
        _FallingObject(x=300, y=200, kind="bonus"),
    ]
    game.draw(renderer.surface)  # PLAYING

    game._lives = 0
    game.update(DT)
    game.draw(renderer.surface)  # GAME_OVER
    assert game.is_finished() is True
