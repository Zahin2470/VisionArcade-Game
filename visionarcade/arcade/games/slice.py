"""Vision Slice: your hand's swipe trajectory is a blade — cut through
targets, avoid bombs.

Targets launch from the bottom of the play area in a parabolic arc
(gravity pulls them back down) rather than falling straight like
Catch's objects, giving Slice a distinct feel. Each frame's motion
segment (previous hand position -> current hand position) is tested
against every target with `segment_circle_intersect`, so a fast swipe
that would sail past a target's center between two sampled frames
still registers as a hit — a plain point check on each frame's
endpoint alone would miss those. A short fading trail follows the
hand for both visual feedback and player readability.
"""

from __future__ import annotations

import enum
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

import pygame

from visionarcade.arcade.collision import segment_circle_intersect
from visionarcade.arcade.difficulty import DifficultyCurve
from visionarcade.arcade.game import ArcadeGame
from visionarcade.arcade.input import GameInput, build_game_input
from visionarcade.arcade.scoring import ComboTracker, ScoreTracker
from visionarcade.constants import (
    SLICE_BOMB_WEIGHT,
    SLICE_CHAIN_MAX_MULTIPLIER,
    SLICE_CHAIN_MULTIPLIER_STEP,
    SLICE_CHAIN_TIMEOUT_SECONDS,
    SLICE_COMMON_POINTS,
    SLICE_COMMON_WEIGHT,
    SLICE_COUNTDOWN_SECONDS,
    SLICE_DIFFICULTY_RAMP_SECONDS,
    SLICE_GOLD_POINTS,
    SLICE_GOLD_WEIGHT,
    SLICE_GRAVITY,
    SLICE_LAUNCH_SPEED_END,
    SLICE_LAUNCH_SPEED_START,
    SLICE_ROUND_DURATION_SECONDS,
    SLICE_SCREEN_SHAKE_DURATION,
    SLICE_SCREEN_SHAKE_MAGNITUDE,
    SLICE_SPAWN_INTERVAL_END,
    SLICE_SPAWN_INTERVAL_START,
    SLICE_START_LIVES,
    SLICE_TARGET_RADIUS,
    SLICE_TRAIL_LENGTH,
)
from visionarcade.rendering.particles import ParticleSystem
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent

Point = Tuple[float, float]

#: Visual-only jitter (screen shake), kept separate from the game's own
#: seedable `rng` so gameplay logic stays deterministic in tests
#: regardless of how many times `draw()` happens to be called.
_shake_rng = random.Random()


class _Phase(enum.Enum):
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    GAME_OVER = "game_over"


@dataclass
class _Target:
    x: float
    y: float
    vx: float
    vy: float
    kind: str  # "common" | "gold" | "bomb"
    sliced: bool = False


@dataclass
class _Shard:
    """A small rotating fragment flung apart on a successful slice —
    the "satisfying slice animation" the design calls for, kept as a
    lightweight, game-specific effect rather than folded into the
    generic `ParticleSystem` (which only draws circles)."""

    x: float
    y: float
    vx: float
    vy: float
    rotation: float
    rotation_speed: float
    life: float
    max_life: float
    color: Tuple[int, int, int]
    size: float


class SliceGame(ArcadeGame):
    """Slice through arcing targets with your hand's swipe trajectory."""

    id = "slice"
    title = "Vision Slice"
    objective = "Swipe through targets to slice them — avoid the bombs."

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
        self._trail_surface = pygame.Surface((width, height), pygame.SRCALPHA)

        self.reset()

    # --- ArcadeGame interface -------------------------------------------

    def reset(self) -> None:
        self._phase = _Phase.COUNTDOWN
        self._countdown_remaining = SLICE_COUNTDOWN_SECONDS
        self._elapsed_playing = 0.0
        self._lives = SLICE_START_LIVES
        self._outcome: Optional[str] = None
        self._targets_sliced = 0

        self._score = ScoreTracker()
        self._chain = ComboTracker(
            max_multiplier=SLICE_CHAIN_MAX_MULTIPLIER,
            multiplier_step=SLICE_CHAIN_MULTIPLIER_STEP,
            combo_timeout_seconds=SLICE_CHAIN_TIMEOUT_SECONDS,
        )
        self._speed_curve = DifficultyCurve(
            SLICE_LAUNCH_SPEED_START, SLICE_LAUNCH_SPEED_END, SLICE_DIFFICULTY_RAMP_SECONDS
        )
        self._spawn_curve = DifficultyCurve(
            SLICE_SPAWN_INTERVAL_START, SLICE_SPAWN_INTERVAL_END, SLICE_DIFFICULTY_RAMP_SECONDS
        )

        self._spawn_timer = 0.0
        self._targets: List[_Target] = []
        self._shards: List[_Shard] = []
        self._trail: Deque[Point] = deque(maxlen=SLICE_TRAIL_LENGTH)
        self._previous_pointer: Optional[Point] = None
        self._input: Optional[GameInput] = None
        self._shake_time_remaining = 0.0

        self.particles.clear()

    def handle_intent(self, intent: FrameIntent) -> None:
        self._input = build_game_input(intent, self.play_area)

    def update(self, dt: float) -> None:
        self.particles.update(dt)
        self._update_shards(dt)
        self._chain.update(dt)
        self._shake_time_remaining = max(0.0, self._shake_time_remaining - dt)

        if self._phase is _Phase.COUNTDOWN:
            self._update_trail()
            self._countdown_remaining -= dt
            if self._countdown_remaining <= 0:
                self._phase = _Phase.PLAYING
        elif self._phase is _Phase.PLAYING:
            self._update_playing(dt)

    def is_finished(self) -> bool:
        return self._phase is _Phase.GAME_OVER

    def get_results(self) -> Dict[str, Any]:
        return {
            "game_id": self.id,
            "score": self._score.score,
            "outcome": self._outcome or "in_progress",
            "lives_remaining": self._lives,
            "best_streak": self._chain.best_streak,
            "targets_sliced": self._targets_sliced,
            "elapsed_seconds": round(self._elapsed_playing, 1),
        }

    # --- Trail / blade tracking ------------------------------------------

    def _update_trail(self) -> None:
        pointer = self._input.pointer if self._input is not None else None
        if pointer is None:
            self._trail.clear()
            self._previous_pointer = None
            return
        self._trail.append(pointer)

    # --- Playing -----------------------------------------------------------

    def _update_playing(self, dt: float) -> None:
        self._elapsed_playing += dt
        self._update_trail()
        self._check_blade_collisions()

        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_target()
            jitter = self._rng.uniform(0.85, 1.15)
            self._spawn_timer = self._spawn_curve.value_at(self._elapsed_playing) * jitter

        surviving: List[_Target] = []
        for target in self._targets:
            target.vy += SLICE_GRAVITY * dt
            target.x += target.vx * dt
            target.y += target.vy * dt
            if not target.sliced and target.y - SLICE_TARGET_RADIUS <= self.play_area.bottom:
                surviving.append(target)
        self._targets = surviving

        if self._lives <= 0:
            self._end_round("out_of_lives")
        elif self._elapsed_playing >= SLICE_ROUND_DURATION_SECONDS:
            self._end_round("cleared")

    def _check_blade_collisions(self) -> None:
        pointer = self._input.pointer if self._input is not None else None
        if pointer is None or self._previous_pointer is None:
            self._previous_pointer = pointer
            return

        for target in self._targets:
            if target.sliced:
                continue
            radius = self._target_radius(target)
            if segment_circle_intersect(self._previous_pointer, pointer, target.x, target.y, radius):
                self._slice_target(target)

        self._previous_pointer = pointer

    @staticmethod
    def _target_radius(target: _Target) -> float:
        return SLICE_TARGET_RADIUS * (1.25 if target.kind == "gold" else 1.0)

    def _spawn_target(self) -> None:
        kind = self._rng.choices(
            ("common", "gold", "bomb"),
            weights=(SLICE_COMMON_WEIGHT, SLICE_GOLD_WEIGHT, SLICE_BOMB_WEIGHT),
        )[0]
        x = self._rng.uniform(self.play_area.left + SLICE_TARGET_RADIUS, self.play_area.right - SLICE_TARGET_RADIUS)
        y = self.play_area.bottom - SLICE_TARGET_RADIUS

        launch_speed = self._speed_curve.value_at(self._elapsed_playing)
        # Mostly-upward launch with a bit of lateral drift, so arcs land
        # somewhere else in the field rather than straight back down.
        vx = self._rng.uniform(-0.35, 0.35) * launch_speed
        vy = -self._rng.uniform(0.85, 1.0) * launch_speed

        self._targets.append(_Target(x=x, y=y, vx=vx, vy=vy, kind=kind))

    def _slice_target(self, target: _Target) -> None:
        target.sliced = True
        self._targets_sliced += 1

        if target.kind == "common":
            multiplier = self._chain.register_hit()
            self._score.add(SLICE_COMMON_POINTS, multiplier)
            self._spawn_slice_effect(target, self._theme.success)
        elif target.kind == "gold":
            self._chain.register_hit()
            self._score.add(SLICE_GOLD_POINTS, 1.0)
            self._spawn_slice_effect(target, self._theme.accent, shard_count=4)
        elif target.kind == "bomb":
            self._lives -= 1
            self._chain.register_miss()
            self._shake_time_remaining = SLICE_SCREEN_SHAKE_DURATION
            self._spawn_slice_effect(target, self._theme.danger)

    def _spawn_slice_effect(self, target: _Target, color: Tuple[int, int, int], shard_count: int = 2) -> None:
        self.particles.burst(target.x, target.y, color, count=14)
        self._spawn_shards(target.x, target.y, color, shard_count)

    def _spawn_shards(self, x: float, y: float, color: Tuple[int, int, int], count: int) -> None:
        for _ in range(count):
            angle = self._rng.uniform(0.0, 6.283185307)
            speed = self._rng.uniform(120.0, 260.0)
            vx = speed * self._rng.uniform(0.6, 1.0)  # cos-ish spread, kept simple
            vy = speed * self._rng.uniform(-1.0, -0.3)
            if self._rng.random() < 0.5:
                vx = -vx
            self._shards.append(
                _Shard(
                    x=x,
                    y=y,
                    vx=vx,
                    vy=vy,
                    rotation=angle,
                    rotation_speed=self._rng.uniform(-6.0, 6.0),
                    life=0.45,
                    max_life=0.45,
                    color=color,
                    size=self._rng.uniform(6.0, 11.0),
                )
            )

    def _update_shards(self, dt: float) -> None:
        alive: List[_Shard] = []
        for shard in self._shards:
            shard.life -= dt
            if shard.life <= 0:
                continue
            shard.x += shard.vx * dt
            shard.y += shard.vy * dt
            shard.vy += SLICE_GRAVITY * 0.5 * dt
            shard.rotation += shard.rotation_speed * dt
            alive.append(shard)
        self._shards = alive

    def _end_round(self, outcome: str) -> None:
        self._phase = _Phase.GAME_OVER
        self._outcome = outcome

    # --- Drawing -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        offset = self._current_shake_offset()
        surface.fill(self._theme.background)
        self._draw_play_area(surface, offset)
        for target in self._targets:
            self._draw_target(surface, target, offset)
        self._draw_shards(surface, offset)
        self.particles.draw(surface)
        self._draw_trail(surface)
        self._draw_hud(surface)

        if self._phase is _Phase.COUNTDOWN:
            self._draw_countdown(surface)

    def _current_shake_offset(self) -> Tuple[int, int]:
        if self._shake_time_remaining <= 0:
            return (0, 0)
        magnitude = SLICE_SCREEN_SHAKE_MAGNITUDE
        return (
            int(_shake_rng.uniform(-magnitude, magnitude)),
            int(_shake_rng.uniform(-magnitude, magnitude)),
        )

    def _draw_play_area(self, surface, offset) -> None:
        rect = self.play_area.move(*offset)
        pygame.draw.rect(surface, self._theme.surface, rect, border_radius=8)
        pygame.draw.rect(surface, self._theme.border, rect, width=2, border_radius=8)

    def _draw_target(self, surface, target: _Target, offset) -> None:
        color = {
            "common": self._theme.success,
            "gold": self._theme.accent,
            "bomb": self._theme.danger,
        }[target.kind]
        radius = self._target_radius(target)
        center = (int(target.x) + offset[0], int(target.y) + offset[1])
        pygame.draw.circle(surface, color, center, int(radius))
        if target.kind == "bomb":
            # A small cross marker so a bomb reads as "avoid" at a glance.
            arm = int(radius * 0.5)
            pygame.draw.line(surface, self._theme.text_primary, (center[0] - arm, center[1] - arm), (center[0] + arm, center[1] + arm), 3)
            pygame.draw.line(surface, self._theme.text_primary, (center[0] - arm, center[1] + arm), (center[0] + arm, center[1] - arm), 3)
        elif target.kind == "gold":
            pygame.draw.circle(surface, self._theme.text_primary, center, int(radius), width=2)

    def _draw_shards(self, surface, offset) -> None:
        for shard in self._shards:
            fraction = max(0.0, shard.life / shard.max_life)
            size = shard.size * fraction
            cx, cy = shard.x + offset[0], shard.y + offset[1]
            points = _rotated_square_points(cx, cy, size, shard.rotation)
            pygame.draw.polygon(surface, shard.color, points)

    def _draw_trail(self, surface) -> None:
        self._trail_surface.fill((0, 0, 0, 0))
        points = list(self._trail)
        count = len(points)
        for i in range(count - 1):
            fraction = (i + 1) / count
            alpha = int(220 * fraction)
            width = max(2, int(7 * fraction))
            color = (*self._theme.accent, alpha)
            pygame.draw.line(self._trail_surface, color, points[i], points[i + 1], width)
        surface.blit(self._trail_surface, (0, 0))

    def _draw_hud(self, surface) -> None:
        self._typography.render(
            surface, f"Score: {self._score.score}", "heading", self._theme.text_primary, topleft=(20, 16)
        )
        for i in range(SLICE_START_LIVES):
            center = (24 + i * 22, 60)
            if i < self._lives:
                pygame.draw.circle(surface, self._theme.danger, center, 8)
            else:
                pygame.draw.circle(surface, self._theme.danger, center, 8, width=2)
        if self._chain.streak > 1:
            self._typography.render(
                surface, f"Chain x{self._chain.streak}", "body", self._theme.accent, topleft=(20, 84)
            )
        if self._phase is _Phase.PLAYING:
            remaining = max(0.0, SLICE_ROUND_DURATION_SECONDS - self._elapsed_playing)
            self._typography.render(
                surface, f"{remaining:0.0f}s", "body", self._theme.text_secondary, topleft=(self.width - 70, 16)
            )

    def _draw_countdown(self, surface) -> None:
        remaining = max(0, int(self._countdown_remaining) + 1)
        label = str(remaining) if self._countdown_remaining > 0 else "Go!"
        self._typography.render(
            surface, label, "title", self._theme.text_primary, center=self.play_area.center
        )


def _rotated_square_points(cx: float, cy: float, size: float, angle: float) -> List[Point]:
    half = size / 2
    corners = ((-half, -half), (half, -half), (half, half), (-half, half))
    cos_a, sin_a = _cos_sin(angle)
    return [(cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a) for x, y in corners]


def _cos_sin(angle: float) -> Tuple[float, float]:
    return math.cos(angle), math.sin(angle)
