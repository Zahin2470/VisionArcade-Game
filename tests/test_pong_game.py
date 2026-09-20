"""Tests for `visionarcade.arcade.games.pong.PongGame`.

Deterministic throughout via a seeded `random.Random` — serve angle,
direction, and AI aim error never depend on real randomness.
"""

from __future__ import annotations

import random

import pytest

from visionarcade.arcade.games.pong import PongGame, PongMode, _Phase
from visionarcade.constants import PONG_COUNTDOWN_SECONDS, PONG_SERVE_DELAY_SECONDS
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent, HandIntent, PinchState

WIDTH, HEIGHT = 1280, 720
DT = 1 / 60


def _game(seed: int = 1, points_to_win: int = 3) -> PongGame:
    return PongGame(
        WIDTH, HEIGHT, get_theme("dark"), Typography(), rng=random.Random(seed), points_to_win=points_to_win
    )


def _hand(present: bool, x: float = 0.5, y: float = 0.5, pinch: PinchState = PinchState.NONE) -> HandIntent:
    if not present:
        return HandIntent.absent("Right")
    return HandIntent(handedness="Right", present=True, position=(x, y), index_tip=(x, y), pinch_state=pinch)


def _intent(left=None, right=None) -> FrameIntent:
    return FrameIntent(
        left=left if left is not None else HandIntent.absent("Left"),
        right=right if right is not None else HandIntent.absent("Right"),
    )


def _select_single_player(game: PongGame) -> None:
    single_item = next(i for i in game._mode_focus.items if i.item_id == "single")
    # Position the (right) hand's normalized position so it maps onto the button's pixel center.
    rel_x = (single_item.rect.centerx - game.play_area.x) / game.play_area.width
    rel_y = (single_item.rect.centery - game.play_area.y) / game.play_area.height
    right = HandIntent(handedness="Right", present=True, position=(rel_x, rel_y), pinch_state=PinchState.NONE)
    game.handle_intent(_intent(right=right))
    game.update(DT)  # hover
    right_confirm = HandIntent(
        handedness="Right", present=True, position=(rel_x, rel_y), pinch_state=PinchState.START
    )
    game.handle_intent(_intent(right=right_confirm))
    game.update(DT)  # confirm
    assert game._phase is _Phase.COUNTDOWN
    assert game._mode is PongMode.SINGLE_PLAYER


def _select_two_player(game: PongGame) -> None:
    item = next(i for i in game._mode_focus.items if i.item_id == "two_player")
    rel_x = (item.rect.centerx - game.play_area.x) / game.play_area.width
    rel_y = (item.rect.centery - game.play_area.y) / game.play_area.height
    right = HandIntent(handedness="Right", present=True, position=(rel_x, rel_y), pinch_state=PinchState.NONE)
    game.handle_intent(_intent(right=right))
    game.update(DT)
    right_confirm = HandIntent(
        handedness="Right", present=True, position=(rel_x, rel_y), pinch_state=PinchState.START
    )
    game.handle_intent(_intent(right=right_confirm))
    game.update(DT)
    assert game._mode is PongMode.TWO_PLAYER


def _finish_countdown(game: PongGame) -> None:
    for _ in range(int(PONG_COUNTDOWN_SECONDS / DT) + 2):
        game.update(DT)
    assert game._phase is _Phase.PLAYING


def _finish_serve_delay(game: PongGame) -> None:
    for _ in range(int(PONG_SERVE_DELAY_SECONDS / DT) + 2):
        game.update(DT)


# --- Metadata / interface -----------------------------------------------------

def test_game_metadata():
    game = _game()
    assert game.id == "pong"
    assert game.title == "Vision Pong"
    assert game.objective


def test_starts_in_mode_select():
    game = _game()
    assert game._phase is _Phase.MODE_SELECT
    assert game.is_finished() is False


# --- Mode select ---------------------------------------------------------------

def test_selecting_single_player_advances_to_countdown():
    game = _game()
    _select_single_player(game)


def test_selecting_two_player_advances_to_countdown():
    game = _game()
    _select_two_player(game)


def test_no_intent_yet_does_not_crash_mode_select():
    game = _game()
    game.update(DT)  # handle_intent never called
    assert game._phase is _Phase.MODE_SELECT


def test_left_hand_can_select_two_player_even_when_right_hand_is_also_present():
    """Regression test: mode-select must check both hands
    independently. A user pointing at the menu with their LEFT hand
    (natural for a two-hand game) must not be ignored just because
    their right hand also happens to be visible in frame — the old
    implementation used `intent.primary()`, which always prefers the
    right hand and would silently drop the left hand's pinch entirely."""
    game = _game()
    item = next(i for i in game._mode_focus.items if i.item_id == "two_player")
    rel_x = (item.rect.centerx - game.play_area.x) / game.play_area.width
    rel_y = (item.rect.centery - game.play_area.y) / game.play_area.height

    # Right hand present but stationary elsewhere, not pinching.
    right = HandIntent(handedness="Right", present=True, position=(0.05, 0.05), pinch_state=PinchState.NONE)
    # Left hand hovering the two_player button and pinching.
    left = HandIntent(handedness="Left", present=True, position=(rel_x, rel_y), pinch_state=PinchState.START)
    game.handle_intent(FrameIntent(left=left, right=right))
    game.update(DT)

    assert game._mode is PongMode.TWO_PLAYER


def test_pinch_hold_over_a_button_activates_it_even_without_a_fresh_start_frame():
    """Regression test: the old code only checked `pinch_just_started`
    (the single exact transition frame). If a pinch was already being
    held by the time the pointer arrived over a button — e.g. the
    pointer drifted there mid-pinch, which is normal for a real
    gesture — the old code would never activate it. HOLD must also work."""
    game = _game()
    item = next(i for i in game._mode_focus.items if i.item_id == "two_player")
    rel_x = (item.rect.centerx - game.play_area.x) / game.play_area.width
    rel_y = (item.rect.centery - game.play_area.y) / game.play_area.height
    game.handle_intent(_intent(right=_hand(True, x=rel_x, y=rel_y, pinch=PinchState.HOLD)))
    game.update(DT)
    assert game._mode is PongMode.TWO_PLAYER


# --- Countdown / paddle tracking -----------------------------------------------

def test_countdown_transitions_to_playing_and_serves():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    assert game._ball_speed > 0


def test_right_paddle_tracks_hand_during_countdown():
    game = _game()
    _select_single_player(game)
    game.handle_intent(_intent(right=_hand(True, x=0.5, y=0.9)))
    game.update(DT)
    assert game._right_paddle_y > game.play_area.centery


def test_left_paddle_is_ai_controlled_in_single_player_and_ignores_left_hand():
    game = _game()
    _select_single_player(game)
    # Even if a left hand is present, single-player mode must not let it drive the AI paddle.
    game.handle_intent(_intent(left=_hand(True, x=0.5, y=0.05), right=_hand(True, x=0.5, y=0.5)))
    y_before = game._left_paddle_y
    game.update(DT)
    # AI paddle only moves toward the ball (idle at center pre-serve), not toward the hand's y=0.05.
    assert abs(game._left_paddle_y - y_before) < 5  # negligible drift before serving


def test_two_player_mode_maps_each_hand_to_its_own_paddle():
    game = _game()
    _select_two_player(game)
    game.handle_intent(_intent(left=_hand(True, x=0.5, y=0.1), right=_hand(True, x=0.5, y=0.9)))
    game.update(DT)
    assert game._left_paddle_y < game.play_area.centery
    assert game._right_paddle_y > game.play_area.centery


def test_paddle_position_is_clamped_within_play_area():
    game = _game()
    _select_two_player(game)
    game.handle_intent(_intent(left=_hand(True, y=0.0), right=_hand(True, y=1.0)))
    game.update(DT)
    from visionarcade.constants import PONG_PADDLE_HEIGHT

    half = PONG_PADDLE_HEIGHT / 2
    assert game._left_paddle_y >= game.play_area.top + half - 1e-6
    assert game._right_paddle_y <= game.play_area.bottom - half + 1e-6


# --- Ball physics ----------------------------------------------------------------

def test_ball_starts_at_center_on_serve():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    assert game._ball_x == pytest.approx(game.play_area.centerx)
    assert game._ball_y == pytest.approx(game.play_area.centery)


def test_ball_does_not_move_during_serve_delay():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    x_before, y_before = game._ball_x, game._ball_y
    game.update(DT)
    assert (game._ball_x, game._ball_y) == (x_before, y_before)


def test_ball_moves_after_serve_delay_elapses():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    _finish_serve_delay(game)
    x_before, y_before = game._ball_x, game._ball_y
    game.update(DT)
    assert (game._ball_x, game._ball_y) != (x_before, y_before)


def test_ball_bounces_off_top_wall():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_y = game.play_area.top + 1
    game._ball_vy = -100.0
    game.update(DT)
    assert game._ball_vy > 0


def test_ball_bounces_off_bottom_wall():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_y = game.play_area.bottom - 1
    game._ball_vy = 100.0
    game.update(DT)
    assert game._ball_vy < 0


def test_ball_bounces_off_right_paddle_and_reverses_direction():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    right_rect = game._right_paddle_rect()
    game._ball_x = right_rect.left - 1
    game._ball_y = right_rect.centery
    game._ball_vx = 200.0
    game.update(DT)
    assert game._ball_vx < 0  # reversed back toward the left
    assert game._rally_hits == 1


def test_bounce_speed_increases_up_to_a_cap():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    right_rect = game._right_paddle_rect()
    speed_before = game._ball_speed
    game._ball_x = right_rect.left - 1
    game._ball_y = right_rect.centery
    game._ball_vx = 200.0
    game.update(DT)
    assert game._ball_speed > speed_before

    from visionarcade.constants import PONG_BALL_MAX_SPEED

    for _ in range(200):  # many hits in a row should still respect the cap
        game._ball_x = right_rect.left - 1
        game._ball_y = right_rect.centery
        game._ball_vx = 200.0
        game.update(DT)
    assert game._ball_speed <= PONG_BALL_MAX_SPEED + 1e-6


def test_hitting_off_center_adds_vertical_english():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    right_rect = game._right_paddle_rect()
    game._ball_x = right_rect.left - 1
    game._ball_y = right_rect.top + 2  # near the paddle's top edge
    game._ball_vx = 200.0
    game.update(DT)
    assert game._ball_vy < 0  # deflected upward


# --- Scoring / round end ---------------------------------------------------------

def test_ball_passing_left_edge_scores_right_player():
    game = _game(points_to_win=5)
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_x = game.play_area.left - 100
    game.update(DT)
    assert game._right_score == 1
    assert game._left_score == 0


def test_ball_passing_right_edge_scores_left_player():
    game = _game(points_to_win=5)
    _select_two_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_x = game.play_area.right + 100
    game.update(DT)
    assert game._left_score == 1


def test_scoring_a_point_resets_for_a_new_serve_when_match_continues():
    game = _game(points_to_win=5)
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_x = game.play_area.left - 100
    game.update(DT)
    assert game._serve_timer > 0  # a fresh serve delay has begun
    assert game.is_finished() is False


def test_reaching_points_to_win_ends_the_match_single_player_win():
    game = _game(points_to_win=1)
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_x = game.play_area.left - 100  # right (human) scores
    game.update(DT)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "player_win"


def test_reaching_points_to_win_ends_the_match_single_player_loss():
    game = _game(points_to_win=1)
    _select_single_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_x = game.play_area.right + 100  # AI (left) scores
    game.update(DT)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "player_loss"


def test_reaching_points_to_win_two_player_left_wins():
    game = _game(points_to_win=1)
    _select_two_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_x = game.play_area.right + 100
    game.update(DT)
    assert game.get_results()["outcome"] == "left_win"


def test_reaching_points_to_win_two_player_right_wins():
    game = _game(points_to_win=1)
    _select_two_player(game)
    _finish_countdown(game)
    game._serve_timer = 0.0
    game._ball_x = game.play_area.left - 100
    game.update(DT)
    assert game.get_results()["outcome"] == "right_win"


# --- get_results / reset --------------------------------------------------------

def test_get_results_in_progress_before_match_ends():
    game = _game()
    results = game.get_results()
    assert results["outcome"] == "in_progress"
    assert results["mode"] is None
    assert results["game_id"] == "pong"


def test_get_results_reports_mode_once_selected():
    game = _game()
    _select_two_player(game)
    assert game.get_results()["mode"] == "two_player"


def test_reset_returns_to_mode_select():
    game = _game(points_to_win=1)
    _select_single_player(game)
    _finish_countdown(game)
    _finish_serve_delay(game)
    game._ball_x = game.play_area.left - 100
    game.update(DT)
    assert game.is_finished() is True

    game.reset()
    assert game._phase is _Phase.MODE_SELECT
    assert game._mode is None
    assert game._left_score == 0 and game._right_score == 0


# --- AI behavior -----------------------------------------------------------------

def test_ai_paddle_moves_toward_the_ball_when_ball_heads_left():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    _finish_serve_delay(game)
    game._ball_x = game.play_area.centerx
    game._ball_y = game.play_area.top + 5
    game._ball_vx = -50.0
    y_before = game._left_paddle_y
    for _ in range(30):
        game.update(DT)
    assert game._left_paddle_y < y_before  # moved up, toward the ball


def test_ai_speed_is_capped_and_does_not_teleport():
    game = _game()
    _select_single_player(game)
    _finish_countdown(game)
    _finish_serve_delay(game)
    game._ball_x = game.play_area.centerx
    game._ball_y = game.play_area.bottom - 5
    game._ball_vx = -50.0
    y_before = game._left_paddle_y
    game.update(DT)
    # A single frame can't move the paddle the entire play area height.
    assert abs(game._left_paddle_y - y_before) < game.play_area.height


# --- Determinism -------------------------------------------------------------------

def test_seeded_match_is_reproducible():
    game_a = _game(seed=123, points_to_win=2)
    game_b = _game(seed=123, points_to_win=2)
    for game in (game_a, game_b):
        _select_single_player(game)
        _finish_countdown(game)
    for _ in range(600):
        game_a.update(DT)
        game_b.update(DT)
    assert game_a.get_results() == game_b.get_results()


# --- Drawing -----------------------------------------------------------------------

def test_draw_does_not_raise_in_every_phase(renderer):
    game = PongGame(
        renderer.surface.get_width(),
        renderer.surface.get_height(),
        get_theme("dark"),
        Typography(),
        rng=random.Random(1),
        points_to_win=1,
    )
    game.draw(renderer.surface)  # MODE_SELECT

    _select_single_player(game)
    game.draw(renderer.surface)  # COUNTDOWN

    _finish_countdown(game)
    game.draw(renderer.surface)  # PLAYING (serve delay)

    _finish_serve_delay(game)
    game.draw(renderer.surface)  # PLAYING (ball moving)

    game._ball_x = game.play_area.left - 100
    game.update(DT)
    game.draw(renderer.surface)  # GAME_OVER
    assert game.is_finished() is True


def test_draw_two_player_labels_does_not_raise(renderer):
    game = PongGame(
        renderer.surface.get_width(), renderer.surface.get_height(), get_theme("neon"), Typography(),
        rng=random.Random(2),
    )
    _select_two_player(game)
    game.draw(renderer.surface)
