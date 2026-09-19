"""Vision Puzzle: pinch to grab a piece, drag it, release it on its
matching slot.

Rotation-by-wrist-orientation — one of the spec's suggested "advanced"
options — is deliberately not implemented: the vision layer's
stabilized `HandIntent` doesn't expose a hand-orientation signal, and
adding one would mean extending the whole vision pipeline (features ->
gestures -> every consumer) for a single feature the design brief
itself marks "if robust". Shape+color matching alone is a complete,
robust spatial-manipulation puzzle without it.

Two-hand play works automatically rather than needing a separate mode:
each hand's grab/drag/release is tracked independently, so placing two
pieces at once (one per hand) is simply something a player can choose
to do.

Difficulty progresses across `PUZZLE_STAGE_COUNT` stages — each with
more pieces AND less time than the last.
"""

from __future__ import annotations

import enum
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pygame

from visionarcade.arcade.difficulty import DifficultyCurve
from visionarcade.arcade.game import ArcadeGame
from visionarcade.arcade.input import map_point_to_rect
from visionarcade.arcade.scoring import ComboTracker, ScoreTracker
from visionarcade.constants import (
    PUZZLE_BASE_PIECE_COUNT,
    PUZZLE_BASE_POINTS_PER_PIECE,
    PUZZLE_COUNTDOWN_SECONDS,
    PUZZLE_GRAB_RADIUS,
    PUZZLE_PIECE_COLORS,
    PUZZLE_PIECE_KINDS,
    PUZZLE_PIECE_RADIUS,
    PUZZLE_SLOT_RADIUS,
    PUZZLE_STAGE_BONUS_STEP,
    PUZZLE_STAGE_COUNT,
    PUZZLE_STAGE_TIME_END,
    PUZZLE_STAGE_TIME_START,
    PUZZLE_STAGE_TRANSITION_SECONDS,
    PUZZLE_STREAK_MAX_MULTIPLIER,
    PUZZLE_STREAK_MULTIPLIER_STEP,
)
from visionarcade.rendering.particles import ParticleSystem
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent, PinchState

Point = Tuple[float, float]
_HAND_NAMES: Tuple[str, str] = ("Left", "Right")


class _Phase(enum.Enum):
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    STAGE_CLEAR = "stage_clear"
    GAME_OVER = "game_over"


@dataclass
class _Piece:
    kind_index: int
    x: float
    y: float
    home_x: float
    home_y: float
    placed: bool = False


@dataclass
class _Slot:
    kind_index: int
    x: float
    y: float
    filled: bool = False


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _regular_polygon_points(cx: float, cy: float, radius: float, sides: int, rotation: float = 0.0) -> List[Point]:
    return [
        (cx + radius * math.cos(rotation + 2 * math.pi * i / sides), cy + radius * math.sin(rotation + 2 * math.pi * i / sides))
        for i in range(sides)
    ]


#: (polygon side count, drawing rotation) per kind name; 0 sides means "draw a circle".
_SHAPE_GEOMETRY: Dict[str, Tuple[int, float]] = {
    "circle": (0, 0.0),
    "triangle": (3, -math.pi / 2),
    "square": (4, 0.0),
    "diamond": (4, math.pi / 4),
    "pentagon": (5, -math.pi / 2),
}


class PuzzleGame(ArcadeGame):
    """A multi-stage shape-matching spatial puzzle."""

    id = "puzzle"
    title = "Vision Puzzle"
    objective = "Pinch to grab a piece and release it on the matching slot."

    def __init__(
        self,
        width: int,
        height: int,
        theme: Theme,
        typography: Typography,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.width = width
        self.height = height
        self._theme = theme
        self._typography = typography
        self._rng = rng if rng is not None else random.Random()

        self.play_area = pygame.Rect(40, 120, width - 80, height - 160)
        self.particles = ParticleSystem(rng=self._rng)
        self._time_curve = DifficultyCurve(
            PUZZLE_STAGE_TIME_START, PUZZLE_STAGE_TIME_END, max(1, PUZZLE_STAGE_COUNT - 1)
        )

        self.reset()

    # --- ArcadeGame interface -------------------------------------------

    def reset(self) -> None:
        self._phase = _Phase.COUNTDOWN
        self._countdown_remaining = PUZZLE_COUNTDOWN_SECONDS
        self._stage_index = 0
        self._stage_transition_remaining = 0.0
        self._outcome: Optional[str] = None
        self._elapsed_playing = 0.0

        self._score = ScoreTracker()
        self._streak = ComboTracker(
            max_multiplier=PUZZLE_STREAK_MAX_MULTIPLIER, multiplier_step=PUZZLE_STREAK_MULTIPLIER_STEP
        )
        self._pieces_placed_total = 0
        self._wrong_placements = 0
        self._intent: Optional[FrameIntent] = None

        self.particles.clear()
        self._start_stage()

    def handle_intent(self, intent: FrameIntent) -> None:
        self._intent = intent

    def update(self, dt: float) -> None:
        self.particles.update(dt)
        if self._phase is _Phase.COUNTDOWN:
            self._countdown_remaining -= dt
            if self._countdown_remaining <= 0:
                self._phase = _Phase.PLAYING
        elif self._phase is _Phase.PLAYING:
            self._update_playing(dt)
        elif self._phase is _Phase.STAGE_CLEAR:
            self._update_stage_clear(dt)

    def is_finished(self) -> bool:
        return self._phase is _Phase.GAME_OVER

    def get_results(self) -> Dict[str, Any]:
        stage_reached = PUZZLE_STAGE_COUNT if self._outcome == "cleared" else self._stage_index + 1
        return {
            "game_id": self.id,
            "score": self._score.score,
            "outcome": self._outcome or "in_progress",
            "stage_reached": stage_reached,
            "pieces_placed": self._pieces_placed_total,
            "wrong_placements": self._wrong_placements,
            "best_streak": self._streak.best_streak,
            "elapsed_seconds": round(self._elapsed_playing, 1),
        }

    # --- Stage setup ---------------------------------------------------------

    def _start_stage(self) -> None:
        piece_count = PUZZLE_BASE_PIECE_COUNT + self._stage_index
        kind_indices = [i % len(PUZZLE_PIECE_KINDS) for i in range(piece_count)]
        self._rng.shuffle(kind_indices)

        staging_top = self.play_area.top + 20
        staging_bottom = self.play_area.top + int(self.play_area.height * 0.38)
        self._pieces: List[_Piece] = []
        for i, kind in enumerate(kind_indices):
            x = self._lane_x(i, piece_count)
            y = self._rng.uniform(staging_top + PUZZLE_PIECE_RADIUS, staging_bottom - PUZZLE_PIECE_RADIUS)
            self._pieces.append(_Piece(kind_index=kind, x=x, y=y, home_x=x, home_y=y))

        slot_kinds = list(kind_indices)
        self._rng.shuffle(slot_kinds)  # a different left-to-right order than the pieces
        board_y = self.play_area.top + int(self.play_area.height * 0.72)
        self._slots: List[_Slot] = [
            _Slot(kind_index=kind, x=self._lane_x(i, piece_count), y=board_y)
            for i, kind in enumerate(slot_kinds)
        ]

        self._stage_time_limit = self._time_curve.value_at(self._stage_index)
        self._stage_time_remaining = self._stage_time_limit
        self._held_by: Dict[str, Optional[int]] = {name: None for name in _HAND_NAMES}

    def _lane_x(self, index: int, count: int) -> float:
        margin = PUZZLE_PIECE_RADIUS + 30
        if count <= 1:
            return float(self.play_area.centerx)
        span = self.play_area.width - 2 * margin
        return self.play_area.left + margin + span * (index / (count - 1))

    # --- Playing -----------------------------------------------------------

    def _update_playing(self, dt: float) -> None:
        self._elapsed_playing += dt
        self._stage_time_remaining -= dt

        for hand_name in _HAND_NAMES:
            self._update_hand(hand_name)

        if self._stage_time_remaining <= 0:
            self._end_round("out_of_time")
            return

        if all(piece.placed for piece in self._pieces):
            self._phase = _Phase.STAGE_CLEAR
            self._stage_transition_remaining = PUZZLE_STAGE_TRANSITION_SECONDS

    def _update_hand(self, hand_name: str) -> None:
        if self._intent is None:
            return
        hand = self._intent.left if hand_name == "Left" else self._intent.right
        held_index = self._held_by[hand_name]

        if not hand.present or hand.position is None:
            if held_index is not None:
                self._release_piece(hand_name, held_index)
            return

        pointer = map_point_to_rect(hand.position, self.play_area)
        assert pointer is not None

        if held_index is not None:
            piece = self._pieces[held_index]
            piece.x, piece.y = pointer
            if hand.pinch_state == PinchState.RELEASE:
                self._release_piece(hand_name, held_index)
            return

        if hand.pinch_state == PinchState.START:
            self._try_grab(hand_name, pointer)

    def _try_grab(self, hand_name: str, pointer: Point) -> None:
        held_indices = set(v for v in self._held_by.values() if v is not None)
        for index, piece in enumerate(self._pieces):
            if piece.placed or index in held_indices:
                continue
            if _distance(pointer, (piece.x, piece.y)) <= PUZZLE_GRAB_RADIUS:
                self._held_by[hand_name] = index
                return

    def _release_piece(self, hand_name: str, index: int) -> None:
        self._held_by[hand_name] = None
        piece = self._pieces[index]
        for slot in self._slots:
            if slot.filled:
                continue
            if _distance((piece.x, piece.y), (slot.x, slot.y)) <= PUZZLE_SLOT_RADIUS:
                if slot.kind_index == piece.kind_index:
                    self._place_piece(piece, slot)
                else:
                    self._wrong_placements += 1
                    self._streak.register_miss()
                    piece.x, piece.y = piece.home_x, piece.home_y
                return
        # Not released over any open slot: it just stays wherever dropped.

    def _place_piece(self, piece: _Piece, slot: _Slot) -> None:
        piece.placed = True
        piece.x, piece.y = slot.x, slot.y
        slot.filled = True
        self._pieces_placed_total += 1

        multiplier = self._streak.register_hit()
        points = PUZZLE_BASE_POINTS_PER_PIECE * (1.0 + self._stage_index * PUZZLE_STAGE_BONUS_STEP)
        self._score.add(int(round(points)), multiplier)
        self.particles.burst(piece.x, piece.y, PUZZLE_PIECE_COLORS[piece.kind_index], count=18)

    def _update_stage_clear(self, dt: float) -> None:
        self._stage_transition_remaining -= dt
        if self._stage_transition_remaining > 0:
            return
        if self._stage_index + 1 >= PUZZLE_STAGE_COUNT:
            self._end_round("cleared")
        else:
            self._stage_index += 1
            self._start_stage()
            self._phase = _Phase.PLAYING

    def _end_round(self, outcome: str) -> None:
        self._phase = _Phase.GAME_OVER
        self._outcome = outcome

    # --- Drawing -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(self._theme.background)
        self._draw_play_area(surface)
        self._draw_slots(surface)
        for index, piece in enumerate(self._pieces):
            self._draw_piece(surface, index, piece)
        self.particles.draw(surface)
        self._draw_hud(surface)

        if self._phase is _Phase.COUNTDOWN:
            self._draw_countdown(surface)
        elif self._phase is _Phase.STAGE_CLEAR:
            self._typography.render(
                surface, "Stage Clear!", "title", self._theme.success, center=self.play_area.center
            )

    def _draw_play_area(self, surface) -> None:
        pygame.draw.rect(surface, self._theme.surface, self.play_area, border_radius=8)
        pygame.draw.rect(surface, self._theme.border, self.play_area, width=2, border_radius=8)

    def _draw_shape(self, surface, kind_index: int, center: Tuple[int, int], radius: float, color, width: int = 0) -> None:
        name = PUZZLE_PIECE_KINDS[kind_index]
        sides, rotation = _SHAPE_GEOMETRY[name]
        if sides == 0:
            pygame.draw.circle(surface, color, center, int(radius), width=width)
        else:
            points = _regular_polygon_points(center[0], center[1], radius, sides, rotation)
            pygame.draw.polygon(surface, color, points, width=width)

    def _draw_slots(self, surface) -> None:
        for slot in self._slots:
            color = self._theme.success if slot.filled else self._theme.border
            self._draw_shape(surface, slot.kind_index, (int(slot.x), int(slot.y)), PUZZLE_SLOT_RADIUS, color, width=3)

    def _draw_piece(self, surface, index: int, piece: _Piece) -> None:
        color = PUZZLE_PIECE_COLORS[piece.kind_index]
        center = (int(piece.x), int(piece.y))
        self._draw_shape(surface, piece.kind_index, center, PUZZLE_PIECE_RADIUS, color)
        if index in self._held_by.values():
            self._draw_shape(
                surface, piece.kind_index, center, PUZZLE_PIECE_RADIUS + 5, self._theme.text_primary, width=2
            )

    def _draw_hud(self, surface) -> None:
        self._typography.render(
            surface, f"Score: {self._score.score}", "heading", self._theme.text_primary, topleft=(20, 16)
        )
        self._typography.render(
            surface,
            f"Stage {self._stage_index + 1}/{PUZZLE_STAGE_COUNT}",
            "small",
            self._theme.text_secondary,
            topleft=(20, 56),
        )
        if self._phase is _Phase.PLAYING:
            remaining = max(0.0, self._stage_time_remaining)
            self._typography.render(
                surface, f"{remaining:0.0f}s", "body", self._theme.text_secondary, topleft=(self.width - 70, 16)
            )
        if self._streak.streak > 1:
            self._typography.render(
                surface, f"Streak x{self._streak.streak}", "body", self._theme.accent, topleft=(20, 78)
            )

    def _draw_countdown(self, surface) -> None:
        remaining = max(0, int(self._countdown_remaining) + 1)
        label = str(remaining) if self._countdown_remaining > 0 else "Go!"
        self._typography.render(
            surface, label, "title", self._theme.text_primary, center=self.play_area.center
        )
