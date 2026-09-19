"""Tests for `visionarcade.arcade.games.puzzle.PuzzleGame`.

Deterministic via a seeded `random.Random`. Grab/drag/release is
driven directly through `handle_intent()` with explicit per-hand
pinch states, matching how the real intent pipeline delivers
`PinchState.START`/`RELEASE` edges independently per hand.
"""

from __future__ import annotations

import random

from visionarcade.arcade.games.puzzle import PuzzleGame, _Phase
from visionarcade.constants import (
    PUZZLE_BASE_PIECE_COUNT,
    PUZZLE_COUNTDOWN_SECONDS,
    PUZZLE_STAGE_COUNT,
    PUZZLE_STAGE_TRANSITION_SECONDS,
)
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent, HandIntent, PinchState

WIDTH, HEIGHT = 1280, 720
DT = 1 / 60


def _game(seed: int = 1) -> PuzzleGame:
    return PuzzleGame(WIDTH, HEIGHT, get_theme("dark"), Typography(), rng=random.Random(seed))


def _hand_at(x: float, y: float, pinch: PinchState = PinchState.NONE, handedness: str = "Right") -> HandIntent:
    return HandIntent(handedness=handedness, present=True, position=(x, y), pinch_state=pinch)


def _absent(name: str) -> HandIntent:
    return HandIntent.absent(name)


def _rel(game: PuzzleGame, point) -> tuple:
    x, y = point
    return ((x - game.play_area.left) / game.play_area.width, (y - game.play_area.top) / game.play_area.height)


def _advance_past_countdown(game: PuzzleGame) -> None:
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_absent("Right")))
    for _ in range(int(PUZZLE_COUNTDOWN_SECONDS / DT) + 2):
        game.update(DT)
    assert game._phase is _Phase.PLAYING


def _grab_and_release_with_right_hand(game: PuzzleGame, piece_index: int, target_point) -> None:
    """Grab `piece_index` with the right hand, drag it to `target_point`
    (a pixel position), and release."""
    piece = game._pieces[piece_index]
    rel_x, rel_y = _rel(game, (piece.x, piece.y))
    right = _hand_at(rel_x, rel_y, pinch=PinchState.START)
    game.handle_intent(FrameIntent(left=_absent("Left"), right=right))
    game.update(DT)  # grab

    tx, ty = _rel(game, target_point)
    right = _hand_at(tx, ty, pinch=PinchState.NONE)
    game.handle_intent(FrameIntent(left=_absent("Left"), right=right))
    game.update(DT)  # drag

    right = _hand_at(tx, ty, pinch=PinchState.RELEASE)
    game.handle_intent(FrameIntent(left=_absent("Left"), right=right))
    game.update(DT)  # release


def _matching_slot_for(game: PuzzleGame, piece_index: int):
    piece = game._pieces[piece_index]
    return next(s for s in game._slots if s.kind_index == piece.kind_index and not s.filled)


# --- Metadata / interface -----------------------------------------------------

def test_game_metadata():
    game = _game()
    assert game.id == "puzzle"
    assert game.title == "Vision Puzzle"
    assert game.objective


def test_starts_in_countdown_with_stage_one_pieces():
    game = _game()
    assert game._phase is _Phase.COUNTDOWN
    assert len(game._pieces) == PUZZLE_BASE_PIECE_COUNT
    assert len(game._slots) == PUZZLE_BASE_PIECE_COUNT
    assert game.is_finished() is False


# --- Grab / drag / release -----------------------------------------------------

def test_pinch_start_near_a_piece_grabs_it():
    game = _game()
    _advance_past_countdown(game)
    piece = game._pieces[0]
    rel_x, rel_y = _rel(game, (piece.x, piece.y))
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_hand_at(rel_x, rel_y, pinch=PinchState.START)))
    game.update(DT)
    assert game._held_by["Right"] == 0


def test_pinch_start_far_from_any_piece_grabs_nothing():
    game = _game()
    _advance_past_countdown(game)
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_hand_at(0.001, 0.001, pinch=PinchState.START)))
    game.update(DT)
    assert game._held_by["Right"] is None


def test_held_piece_follows_the_hand():
    game = _game()
    _advance_past_countdown(game)
    piece = game._pieces[0]
    rel_x, rel_y = _rel(game, (piece.x, piece.y))
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_hand_at(rel_x, rel_y, pinch=PinchState.START)))
    game.update(DT)

    new_x = game.play_area.centerx
    new_y = game.play_area.centery
    nrel_x, nrel_y = _rel(game, (new_x, new_y))
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_hand_at(nrel_x, nrel_y)))
    game.update(DT)
    assert abs(piece.x - new_x) < 1.0
    assert abs(piece.y - new_y) < 1.0


def test_releasing_over_the_matching_slot_places_the_piece():
    game = _game()
    _advance_past_countdown(game)
    slot = _matching_slot_for(game, 0)
    _grab_and_release_with_right_hand(game, 0, (slot.x, slot.y))
    assert game._pieces[0].placed is True
    assert slot.filled is True
    assert game._score.score > 0
    assert game._held_by["Right"] is None


def test_releasing_over_a_wrong_slot_snaps_back_home():
    game = _game()
    _advance_past_countdown(game)
    piece = game._pieces[0]
    wrong_slot = next(s for s in game._slots if s.kind_index != piece.kind_index)
    home_x, home_y = piece.home_x, piece.home_y
    _grab_and_release_with_right_hand(game, 0, (wrong_slot.x, wrong_slot.y))
    assert piece.placed is False
    assert piece.x == home_x and piece.y == home_y
    assert game._wrong_placements == 1
    assert wrong_slot.filled is False


def test_releasing_over_empty_space_leaves_piece_where_dropped():
    game = _game()
    _advance_past_countdown(game)
    piece = game._pieces[0]
    drop_point = (game.play_area.left + 15, game.play_area.top + 15)
    _grab_and_release_with_right_hand(game, 0, drop_point)
    assert piece.placed is False
    rel_drop = _rel(game, drop_point)
    expected = (game.play_area.left + rel_drop[0] * game.play_area.width, game.play_area.top + rel_drop[1] * game.play_area.height)
    assert abs(piece.x - expected[0]) < 1.0


def test_cannot_grab_an_already_placed_piece():
    game = _game()
    _advance_past_countdown(game)
    slot = _matching_slot_for(game, 0)
    _grab_and_release_with_right_hand(game, 0, (slot.x, slot.y))
    assert game._pieces[0].placed is True

    rel_x, rel_y = _rel(game, (slot.x, slot.y))
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_hand_at(rel_x, rel_y, pinch=PinchState.START)))
    game.update(DT)
    assert game._held_by["Right"] is None


def test_hand_disappearing_mid_hold_releases_the_piece():
    game = _game()
    _advance_past_countdown(game)
    piece = game._pieces[0]
    rel_x, rel_y = _rel(game, (piece.x, piece.y))
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_hand_at(rel_x, rel_y, pinch=PinchState.START)))
    game.update(DT)
    assert game._held_by["Right"] == 0

    game.handle_intent(FrameIntent(left=_absent("Left"), right=_absent("Right")))
    game.update(DT)
    assert game._held_by["Right"] is None


# --- Two-hand play -----------------------------------------------------------------

def test_both_hands_can_grab_different_pieces_simultaneously():
    game = _game()
    game._pieces = game._pieces[:2] if len(game._pieces) >= 2 else game._pieces
    _advance_past_countdown(game)
    assert len(game._pieces) >= 2
    p0, p1 = game._pieces[0], game._pieces[1]
    left = _hand_at(*_rel(game, (p0.x, p0.y)), pinch=PinchState.START, handedness="Left")
    right = _hand_at(*_rel(game, (p1.x, p1.y)), pinch=PinchState.START)
    game.handle_intent(FrameIntent(left=left, right=right))
    game.update(DT)
    assert game._held_by["Left"] == 0
    assert game._held_by["Right"] == 1


def test_second_hand_cannot_grab_a_piece_already_held_by_the_first():
    game = _game()
    _advance_past_countdown(game)
    piece = game._pieces[0]
    rel_x, rel_y = _rel(game, (piece.x, piece.y))
    right = _hand_at(rel_x, rel_y, pinch=PinchState.START)
    game.handle_intent(FrameIntent(left=_absent("Left"), right=right))
    game.update(DT)
    assert game._held_by["Right"] == 0

    left = _hand_at(rel_x, rel_y, pinch=PinchState.START, handedness="Left")
    game.handle_intent(FrameIntent(left=left, right=right))
    game.update(DT)
    assert game._held_by["Left"] is None


# --- Streak --------------------------------------------------------------------------

def test_correct_placements_build_a_streak_and_bonus_score():
    game = _game()
    _advance_past_countdown(game)
    assert len(game._pieces) >= 2
    slot0 = _matching_slot_for(game, 0)
    _grab_and_release_with_right_hand(game, 0, (slot0.x, slot0.y))
    score_after_first = game._score.score

    slot1 = _matching_slot_for(game, 1)
    _grab_and_release_with_right_hand(game, 1, (slot1.x, slot1.y))
    gained_second = game._score.score - score_after_first
    assert game._streak.streak == 2
    assert gained_second > (score_after_first)  # rough sanity: multiplier grew


def test_wrong_placement_resets_streak():
    game = _game()
    _advance_past_countdown(game)
    slot0 = _matching_slot_for(game, 0)
    _grab_and_release_with_right_hand(game, 0, (slot0.x, slot0.y))
    assert game._streak.streak == 1

    piece1 = game._pieces[1]
    wrong_slot = next(s for s in game._slots if s.kind_index != piece1.kind_index and not s.filled)
    _grab_and_release_with_right_hand(game, 1, (wrong_slot.x, wrong_slot.y))
    assert game._streak.streak == 0


# --- Stage progression / round end -----------------------------------------------

def test_placing_all_pieces_enters_stage_clear():
    game = _game()
    _advance_past_countdown(game)
    for index in range(len(game._pieces)):
        slot = _matching_slot_for(game, index)
        _grab_and_release_with_right_hand(game, index, (slot.x, slot.y))
    assert game._phase is _Phase.STAGE_CLEAR


def test_stage_clear_advances_to_a_bigger_next_stage():
    game = _game()
    _advance_past_countdown(game)
    first_stage_piece_count = len(game._pieces)
    for index in range(len(game._pieces)):
        slot = _matching_slot_for(game, index)
        _grab_and_release_with_right_hand(game, index, (slot.x, slot.y))
    for _ in range(int(PUZZLE_STAGE_TRANSITION_SECONDS / DT) + 2):
        game.update(DT)
    assert game._phase is _Phase.PLAYING
    assert game._stage_index == 1
    assert len(game._pieces) == first_stage_piece_count + 1


def test_completing_every_stage_clears_the_round():
    game = _game(seed=5)
    _advance_past_countdown(game)
    for _ in range(PUZZLE_STAGE_COUNT):
        for index in range(len(game._pieces)):
            slot = _matching_slot_for(game, index)
            _grab_and_release_with_right_hand(game, index, (slot.x, slot.y))
        for _ in range(int(PUZZLE_STAGE_TRANSITION_SECONDS / DT) + 2):
            game.update(DT)
            if game.is_finished():
                break
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "cleared"
    assert game.get_results()["stage_reached"] == PUZZLE_STAGE_COUNT


def test_running_out_of_time_ends_the_round():
    game = _game()
    _advance_past_countdown(game)
    game._stage_time_remaining = -1.0
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_absent("Right")))
    game.update(DT)
    assert game.is_finished() is True
    assert game.get_results()["outcome"] == "out_of_time"
    assert game.get_results()["stage_reached"] == 1


# --- get_results / reset --------------------------------------------------------

def test_get_results_before_round_ends_reports_in_progress():
    game = _game()
    results = game.get_results()
    assert results["outcome"] == "in_progress"
    assert results["game_id"] == "puzzle"


def test_reset_returns_to_clean_countdown_state():
    game = _game()
    _advance_past_countdown(game)
    slot = _matching_slot_for(game, 0)
    _grab_and_release_with_right_hand(game, 0, (slot.x, slot.y))
    game.reset()
    assert game._phase is _Phase.COUNTDOWN
    assert game._stage_index == 0
    assert game._score.score == 0
    assert game._pieces_placed_total == 0
    assert len(game._pieces) == PUZZLE_BASE_PIECE_COUNT


# --- Determinism -------------------------------------------------------------------

def test_seeded_stage_layout_is_reproducible():
    game_a = _game(seed=42)
    game_b = _game(seed=42)
    kinds_a = [(p.kind_index, round(p.x, 3), round(p.y, 3)) for p in game_a._pieces]
    kinds_b = [(p.kind_index, round(p.x, 3), round(p.y, 3)) for p in game_b._pieces]
    assert kinds_a == kinds_b


# --- Drawing -----------------------------------------------------------------------

def test_draw_does_not_raise_in_every_phase(renderer):
    game = PuzzleGame(
        renderer.surface.get_width(), renderer.surface.get_height(), get_theme("dark"), Typography(),
        rng=random.Random(1),
    )
    game.draw(renderer.surface)  # COUNTDOWN

    _advance_past_countdown(game)
    piece = game._pieces[0]
    rel_x, rel_y = _rel(game, (piece.x, piece.y))
    game.handle_intent(FrameIntent(left=_absent("Left"), right=_hand_at(rel_x, rel_y, pinch=PinchState.START)))
    game.update(DT)
    game.draw(renderer.surface)  # PLAYING, holding a piece

    for index in range(len(game._pieces)):
        slot = _matching_slot_for(game, index)
        _grab_and_release_with_right_hand(game, index, (slot.x, slot.y))
    game.draw(renderer.surface)  # STAGE_CLEAR

    game._stage_time_remaining = -1.0
    game.update(DT)
    game.draw(renderer.surface)  # could be PLAYING or GAME_OVER depending on stage transition timing
