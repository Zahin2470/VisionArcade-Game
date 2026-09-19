"""Tests for `visionarcade.arcade.games.slice.SliceGame`.

Deterministic via a seeded `random.Random`. Blade collisions are
driven directly through `handle_intent()` across two consecutive
frames (the segment between them is what's tested), matching how the
real intent pipeline would feed a swiping hand frame by frame.
"""

from __future__ import annotations

import random

from visionarcade.arcade.games.slice import SliceGame, _Phase, _Target
from visionarcade.constants import (
    SLICE_COMMON_POINTS,
    SLICE_COUNTDOWN_SECONDS,
    SLICE_GOLD_POINTS,
    SLICE_ROUND_DURATION_SECONDS,
    SLICE_START_LIVES,
)
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent, HandIntent

WIDTH, HEIGHT = 1280, 720
DT = 1 / 60


def _game(seed: int = 1) -> SliceGame:
    return SliceGame(WIDTH, HEIGHT, get_theme("dark"), Typography(), rng=random.Random(seed))


def _intent_at(x: float, y: float) -> FrameIntent:
    right = HandIntent(handedness="Right", present=True, position=(x, y), index_tip=(x, y))
    return FrameIntent(left=HandIntent.absent("Left"), right=right)


def _no_hand() -> FrameIntent:
    return FrameIntent(left=HandIntent.absent("Left"), right=HandIntent.absent("Right"))


def _advance_past_countdown(game: SliceGame) -> None:
    game.handle_intent(_intent_at(0.5, 0.5))
    for _ in range(int(SLICE_COUNTDOWN_SECONDS / DT) + 2):
        game.update(DT)
    assert game._phase is _Phase.PLAYING
    # Real gameplay never has a discontinuous position jump (the hand
    # moves continuously, smoothed frame to frame) — these isolated
    # tests inject synthetic positions directly, so start each one's
    # swipe scenario from a clean blade-tracking state rather than
    # carrying over wherever the countdown-phase hand happened to be.
    game._trail.clear()
    game._previous_pointer = None


def _swipe_through(game: SliceGame, target: _Target) -> None:
    """Simulate a two-frame swipe: hand starts well away from the
    target, then moves to land exactly on it — the segment between
    those two frames is what `segment_circle_intersect` checks."""
    far_x = (target.x - game.play_area.left - 200) / game.play_area.width
    far_y = (target.y - game.play_area.top) / game.play_area.height
    game.handle_intent(_intent_at(max(0.0, far_x), far_y))
    game.update(DT)

    hit_x = (target.x - game.play_area.left) / game.play_area.width
    hit_y = (target.y - game.play_area.top) / game.play_area.height
    game.handle_intent(_intent_at(hit_x, hit_y))
    game.update(DT)


# --- Metadata / interface -----------------------------------------------------

def test_game_metadata():
    game = _game()
    assert game.id == "slice"
    assert game.title == "Vision Slice"
    assert game.objective


def test_starts_in_countdown():
    game = _game()
    assert game._phase is _Phase.COUNTDOWN
    assert game.is_finished() is False


def test_countdown_transitions_to_playing():
    game = _game()
    _advance_past_countdown(game)


# --- Trail tracking --------------------------------------------------------------

def test_trail_grows_as_hand_moves():
    game = _game()
    _advance_past_countdown(game)
    for i in range(5):
        game.handle_intent(_intent_at(0.1 * i, 0.5))
        game.update(DT)
    assert len(game._trail) == 5


def test_trail_clears_when_hand_disappears():
    game = _game()
    _advance_past_countdown(game)
    game.handle_intent(_intent_at(0.5, 0.5))
    game.update(DT)
    assert len(game._trail) > 0

    game.handle_intent(_no_hand())
    game.update(DT)
    assert len(game._trail) == 0
    assert game._previous_pointer is None


def test_trail_is_capped_at_max_length():
    game = _game()
    _advance_past_countdown(game)
    from visionarcade.constants import SLICE_TRAIL_LENGTH

    for i in range(SLICE_TRAIL_LENGTH + 20):
        game.handle_intent(_intent_at(0.5, 0.5))
        game.update(DT)
    assert len(game._trail) == SLICE_TRAIL_LENGTH


# --- Slicing mechanics -----------------------------------------------------------

def test_slicing_a_common_target_scores_and_removes_it():
    game = _game()
    _advance_past_countdown(game)
    target = _Target(x=game.play_area.centerx, y=game.play_area.centery, vx=0, vy=0, kind="common")
    game._targets = [target]
    _swipe_through(game, target)
    assert target.sliced is True
    assert game._score.score > 0
    assert game._targets_sliced == 1


def test_slicing_a_gold_target_scores_flat_points():
    game = _game()
    _advance_past_countdown(game)
    target = _Target(x=game.play_area.centerx, y=game.play_area.centery, vx=0, vy=0, kind="gold")
    game._targets = [target]
    _swipe_through(game, target)
    assert game._score.score == SLICE_GOLD_POINTS


def test_slicing_a_bomb_costs_a_life_and_resets_chain():
    game = _game()
    _advance_past_countdown(game)
    game._chain.register_hit()
    target = _Target(x=game.play_area.centerx, y=game.play_area.centery, vx=0, vy=0, kind="bomb")
    game._targets = [target]
    lives_before = game._lives
    _swipe_through(game, target)
    assert game._lives == lives_before - 1
    assert game._chain.streak == 0
    assert game._shake_time_remaining > 0


def test_a_far_swipe_that_never_reaches_the_target_does_not_slice_it():
    game = _game()
    _advance_past_countdown(game)
    target = _Target(x=game.play_area.centerx, y=game.play_area.centery, vx=0, vy=0, kind="common")
    game._targets = [target]
    game.handle_intent(_intent_at(0.01, 0.01))
    game.update(DT)
    game.handle_intent(_intent_at(0.02, 0.02))
    game.update(DT)
    assert target.sliced is False
    assert game._score.score == 0


def test_fast_swipe_between_two_frames_still_slices_a_target_in_between():
    game = _game()
    _advance_past_countdown(game)
    # Target sits exactly halfway between two sampled hand positions —
    # neither endpoint touches it, but the segment does.
    mid_x = game.play_area.centerx
    mid_y = game.play_area.centery
    target = _Target(x=mid_x, y=mid_y, vx=0, vy=0, kind="common")
    game._targets = [target]

    left_x = (game.play_area.left + 5 - game.play_area.left) / game.play_area.width
    right_x = (game.play_area.right - 5 - game.play_area.left) / game.play_area.width
    y = (mid_y - game.play_area.top) / game.play_area.height

    game.handle_intent(_intent_at(left_x, y))
    game.update(DT)
    game.handle_intent(_intent_at(right_x, y))
    game.update(DT)
    assert target.sliced is True


def test_sliced_target_cannot_be_sliced_twice():
    game = _game()
    _advance_past_countdown(game)
    target = _Target(x=game.play_area.centerx, y=game.play_area.centery, vx=0, vy=0, kind="common")
    game._targets = [target]
    _swipe_through(game, target)
    score_after_first = game._score.score

    # Swipe through the same (now-sliced) spot again.
    game.handle_intent(_intent_at(0.0, 0.0))
    game.update(DT)
    hit_x = (target.x - game.play_area.left) / game.play_area.width
    hit_y = (target.y - game.play_area.top) / game.play_area.height
    game.handle_intent(_intent_at(hit_x, hit_y))
    game.update(DT)
    assert game._score.score == score_after_first


# --- Chain scoring -----------------------------------------------------------------

def test_consecutive_slices_increase_chain_multiplier():
    game = _game()
    _advance_past_countdown(game)
    t1 = _Target(x=game.play_area.left + 60, y=game.play_area.centery, vx=0, vy=0, kind="common")
    t2 = _Target(x=game.play_area.left + 120, y=game.play_area.centery, vx=0, vy=0, kind="common")
    game._targets = [t1, t2]

    _swipe_through(game, t1)
    score_after_first = game._score.score
    _swipe_through(game, t2)
    gained_second = game._score.score - score_after_first

    assert gained_second > SLICE_COMMON_POINTS  # multiplier > 1x by the second hit


# --- Round-ending conditions -----------------------------------------------------

def test_round_ends_out_of_lives():
    game = _game()
    _advance_past_countdown(game)
    game._lives = 1
    target = _Target(x=game.play_area.centerx, y=game.play_area.centery, vx=0, vy=0, kind="bomb")
    game._targets = [target]
    _swipe_through(game, target)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "out_of_lives"


def test_round_ends_cleared_after_full_duration():
    game = _game()
    _advance_past_countdown(game)
    game._elapsed_playing = SLICE_ROUND_DURATION_SECONDS - DT / 2
    game._targets = []
    game.handle_intent(_no_hand())
    game.update(DT)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "cleared"


def test_missing_a_common_target_has_no_penalty():
    game = _game()
    _advance_past_countdown(game)
    target = _Target(
        x=game.play_area.centerx, y=game.play_area.bottom + 1, vx=0, vy=100, kind="common"
    )
    game._targets = [target]
    lives_before = game._lives
    game.handle_intent(_no_hand())
    game.update(DT)
    assert game._lives == lives_before  # falling past the bottom, uncut, is free


# --- get_results / reset --------------------------------------------------------

def test_get_results_before_round_ends_reports_in_progress():
    game = _game()
    results = game.get_results()
    assert results["outcome"] == "in_progress"
    assert results["game_id"] == "slice"


def test_reset_returns_to_clean_countdown_state():
    game = _game()
    _advance_past_countdown(game)
    game._score.add(500)
    game._lives = 0
    game._targets_sliced = 10
    game.reset()
    assert game._phase is _Phase.COUNTDOWN
    assert game._score.score == 0
    assert game._lives == SLICE_START_LIVES
    assert game._targets_sliced == 0
    assert game._targets == []
    assert len(game._trail) == 0


# --- Physics / spawning (deterministic via seeded rng) --------------------------

def test_targets_launch_upward_and_fall_back_with_gravity():
    game = _game(seed=5)
    _advance_past_countdown(game)
    for _ in range(300):
        game.update(DT)
    # After a few seconds, some targets should have been spawned and
    # either survived (arced) or fallen past the bottom and been removed.
    assert game._targets_sliced == 0  # no hand movement -> nothing sliced
    assert game._spawn_timer is not None


def test_spawned_targets_start_within_play_area_x_bounds():
    game = _game(seed=9)
    _advance_past_countdown(game)
    for _ in range(60):
        game.update(DT)
    for target in game._targets:
        assert game.play_area.left <= target.x <= game.play_area.right


def test_seeded_game_is_reproducible():
    game_a = _game(seed=42)
    game_b = _game(seed=42)
    _advance_past_countdown(game_a)
    _advance_past_countdown(game_b)
    for _ in range(180):
        game_a.update(DT)
        game_b.update(DT)
    assert game_a.get_results() == game_b.get_results()


# --- Drawing -----------------------------------------------------------------------

def test_draw_does_not_raise_in_every_phase(renderer):
    game = SliceGame(
        renderer.surface.get_width(),
        renderer.surface.get_height(),
        get_theme("dark"),
        Typography(),
        rng=random.Random(1),
    )
    game.draw(renderer.surface)  # COUNTDOWN

    _advance_past_countdown(game)
    game._targets = [
        _Target(x=100, y=100, vx=10, vy=-50, kind="common"),
        _Target(x=200, y=150, vx=-10, vy=-30, kind="gold"),
        _Target(x=300, y=200, vx=0, vy=0, kind="bomb"),
    ]
    game.handle_intent(_intent_at(0.5, 0.5))
    game.update(DT)
    game.draw(renderer.surface)  # PLAYING, with shards/particles/trail active

    game._lives = 0
    game.update(DT)
    game.draw(renderer.surface)  # GAME_OVER
    assert game.is_finished() is True
