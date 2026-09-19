"""Tests for `visionarcade.arcade.games.aim.AimGame`.

Deterministic via a seeded `random.Random` (target placement is the
only randomness). Hits/misses are driven directly through
`handle_intent()` with explicit pinch states, matching how the real
intent pipeline delivers `PinchState.START` edges.
"""

from __future__ import annotations

import random

import pytest

from visionarcade.arcade.games.aim import AimGame, _Phase
from visionarcade.constants import (
    AIM_BASE_POINTS,
    AIM_COUNTDOWN_SECONDS,
    AIM_MAX_MISSES,
    AIM_TARGET_COUNT,
)
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent, HandIntent, PinchState

WIDTH, HEIGHT = 1280, 720
DT = 1 / 60


def _game(seed: int = 1) -> AimGame:
    return AimGame(WIDTH, HEIGHT, get_theme("dark"), Typography(), rng=random.Random(seed))


def _intent(x: float, y: float, pinch: PinchState = PinchState.NONE) -> FrameIntent:
    right = HandIntent(handedness="Right", present=True, position=(x, y), index_tip=(x, y), pinch_state=pinch)
    return FrameIntent(left=HandIntent.absent("Left"), right=right)


def _no_hand() -> FrameIntent:
    return FrameIntent(left=HandIntent.absent("Left"), right=HandIntent.absent("Right"))


def _advance_past_countdown(game: AimGame) -> None:
    game.handle_intent(_no_hand())
    for _ in range(int(AIM_COUNTDOWN_SECONDS / DT) + 2):
        game.update(DT)
    assert game._phase is _Phase.PLAYING
    assert game._target_pos is not None


def _rel_position_of_target(game: AimGame):
    assert game._target_pos is not None
    x, y = game._target_pos
    return (
        (x - game.play_area.left) / game.play_area.width,
        (y - game.play_area.top) / game.play_area.height,
    )


def _hit_current_target(game: AimGame) -> None:
    rel_x, rel_y = _rel_position_of_target(game)
    game.handle_intent(_intent(rel_x, rel_y, pinch=PinchState.NONE))
    game.update(DT)  # hover, register _hovering
    game.handle_intent(_intent(rel_x, rel_y, pinch=PinchState.START))
    game.update(DT)  # pinch while hovering -> hit


def _miss_current_target(game: AimGame) -> None:
    game.handle_intent(_no_hand())
    limit = game._target_time_limit
    for _ in range(int(limit / DT) + 2):
        if game._phase is not _Phase.PLAYING:
            break
        game.update(DT)


# --- Metadata / interface -----------------------------------------------------

def test_game_metadata():
    game = _game()
    assert game.id == "aim"
    assert game.title == "Vision Aim"
    assert game.objective


def test_starts_in_countdown():
    game = _game()
    assert game._phase is _Phase.COUNTDOWN
    assert game.is_finished() is False


def test_first_target_spawns_after_countdown():
    game = _game()
    _advance_past_countdown(game)
    assert game._targets_presented == 1


# --- Hover feedback --------------------------------------------------------------

def test_hovering_over_target_sets_hovering_true():
    game = _game()
    _advance_past_countdown(game)
    rel_x, rel_y = _rel_position_of_target(game)
    game.handle_intent(_intent(rel_x, rel_y))
    game.update(DT)
    assert game._hovering is True


def test_hovering_away_from_target_sets_hovering_false():
    game = _game()
    _advance_past_countdown(game)
    game.handle_intent(_intent(0.001, 0.001))
    game.update(DT)
    assert game._hovering is False


# --- Hit mechanics -----------------------------------------------------------------

def test_pinch_while_hovering_hits_the_target():
    game = _game()
    _advance_past_countdown(game)
    _hit_current_target(game)
    assert game._targets_hit == 1
    assert game._score.score > 0


def test_pinch_while_not_hovering_does_not_hit():
    game = _game()
    _advance_past_countdown(game)
    game.handle_intent(_intent(0.001, 0.001, pinch=PinchState.START))
    game.update(DT)
    assert game._targets_hit == 0
    assert game._score.score == 0


def test_hitting_advances_to_the_next_target():
    game = _game()
    _advance_past_countdown(game)
    _hit_current_target(game)
    assert game._targets_presented == 2


def test_fast_hit_scores_more_than_a_slow_hit():
    game_fast = _game(seed=1)
    _advance_past_countdown(game_fast)
    rel_x, rel_y = _rel_position_of_target(game_fast)
    game_fast.handle_intent(_intent(rel_x, rel_y, pinch=PinchState.START))
    game_fast.update(DT)  # hit almost instantly
    fast_score = game_fast._score.score

    game_slow = _game(seed=1)
    _advance_past_countdown(game_slow)
    rel_x2, rel_y2 = _rel_position_of_target(game_slow)
    # Wait most of the time limit before hitting.
    wait_frames = int((game_slow._target_time_limit * 0.9) / DT)
    game_slow.handle_intent(_no_hand())
    for _ in range(wait_frames):
        game_slow.update(DT)
    game_slow.handle_intent(_intent(rel_x2, rel_y2, pinch=PinchState.NONE))
    game_slow.update(DT)
    game_slow.handle_intent(_intent(rel_x2, rel_y2, pinch=PinchState.START))
    game_slow.update(DT)
    slow_score = game_slow._score.score

    assert fast_score > slow_score


def test_reaction_time_is_recorded_on_hit():
    game = _game()
    _advance_past_countdown(game)
    _hit_current_target(game)
    assert len(game._reaction_times) == 1
    assert game._reaction_times[0] >= 0.0


# --- Miss mechanics ----------------------------------------------------------------

def test_target_timing_out_counts_as_a_miss():
    game = _game()
    _advance_past_countdown(game)
    _miss_current_target(game)
    assert game._targets_missed == 1


def test_miss_resets_streak():
    game = _game()
    _advance_past_countdown(game)
    _hit_current_target(game)
    _hit_current_target(game)
    assert game._streak.streak == 2
    _miss_current_target(game)
    assert game._streak.streak == 0


def test_consecutive_hits_increase_streak_and_multiplier():
    game = _game()
    _advance_past_countdown(game)
    _hit_current_target(game)
    score_after_one = game._score.score
    _hit_current_target(game)
    gained_second = game._score.score - score_after_one
    assert gained_second > AIM_BASE_POINTS  # multiplier > 1x by the second hit


# --- Round-ending conditions -----------------------------------------------------

def test_too_many_misses_ends_the_round():
    game = _game()
    _advance_past_countdown(game)
    for _ in range(AIM_MAX_MISSES):
        if game.is_finished():
            break
        _miss_current_target(game)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "too_many_misses"


def test_completing_the_full_sequence_clears_the_round():
    game = _game()
    _advance_past_countdown(game)
    for _ in range(AIM_TARGET_COUNT):
        if game.is_finished():
            break
        _hit_current_target(game)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "cleared"
    assert game.get_results()["accuracy"] == pytest.approx(1.0)


# --- get_results / reset --------------------------------------------------------

def test_get_results_before_round_ends_reports_in_progress():
    game = _game()
    results = game.get_results()
    assert results["outcome"] == "in_progress"
    assert results["game_id"] == "aim"
    assert results["accuracy"] == 0.0
    assert results["average_reaction_time"] is None


def test_get_results_accuracy_reflects_hits_and_misses():
    game = _game()
    _advance_past_countdown(game)
    _hit_current_target(game)
    _miss_current_target(game)
    results = game.get_results()
    # 1 initial target + 1 spawned after the hit + 1 spawned after the miss = 3.
    assert results["targets_presented"] == 3
    assert results["accuracy"] == pytest.approx(1 / 3, abs=0.001)
    assert results["missed_targets"] == 1


def test_reset_returns_to_clean_countdown_state():
    game = _game()
    _advance_past_countdown(game)
    _hit_current_target(game)
    game.reset()
    assert game._phase is _Phase.COUNTDOWN
    assert game._score.score == 0
    assert game._targets_presented == 0
    assert game._targets_hit == 0
    assert game._reaction_times == []


# --- Spawning / bounds (deterministic via seeded rng) ----------------------------

def test_spawned_targets_stay_within_play_area():
    game = _game(seed=13)
    _advance_past_countdown(game)
    for _ in range(5):
        assert game._target_pos is not None
        x, y = game._target_pos
        assert game.play_area.left <= x <= game.play_area.right
        assert game.play_area.top <= y <= game.play_area.bottom
        _hit_current_target(game)
        if game.is_finished():
            break


def test_seeded_game_is_reproducible():
    game_a = _game(seed=77)
    game_b = _game(seed=77)
    _advance_past_countdown(game_a)
    _advance_past_countdown(game_b)
    for _ in range(3):
        _hit_current_target(game_a)
        _hit_current_target(game_b)
    assert game_a.get_results() == game_b.get_results()
    assert game_a._target_pos == game_b._target_pos


# --- Drawing -----------------------------------------------------------------------

def test_draw_does_not_raise_in_every_phase(renderer):
    game = AimGame(
        renderer.surface.get_width(),
        renderer.surface.get_height(),
        get_theme("dark"),
        Typography(),
        rng=random.Random(1),
    )
    game.draw(renderer.surface)  # COUNTDOWN

    _advance_past_countdown(game)
    game.handle_intent(_intent(0.5, 0.5))
    game.update(DT)
    game.draw(renderer.surface)  # PLAYING, hovering

    _hit_current_target(game)
    game.draw(renderer.surface)  # PLAYING, just after a hit (flash active)

    for _ in range(AIM_MAX_MISSES):
        if game.is_finished():
            break
        _miss_current_target(game)
    game.draw(renderer.surface)  # GAME_OVER
    assert game.is_finished() is True
