"""Vision Catch: move a hand-controlled catcher to collect falling
objects and avoid hazards.

A round runs COUNTDOWN -> PLAYING -> GAME_OVER. Fall speed and spawn
rate ramp up over the round via `DifficultyCurve`. Catching a
beneficial object scores points scaled by a combo multiplier that
decays if the player goes too long without a catch; catching a hazard
costs a life and briefly shakes the screen; letting a beneficial
object fall past the catcher also costs a life; a hazard that falls
past very close to the catcher (a "near miss") grants a small
consolation bonus instead of a penalty.
"""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pygame

from visionarcade.arcade.collision import circle_rect_overlap, distance_to_rect
from visionarcade.arcade.difficulty import DifficultyCurve
from visionarcade.arcade.game import ArcadeGame
from visionarcade.arcade.input import GameInput, build_game_input
from visionarcade.arcade.scoring import ComboTracker, ScoreTracker
from visionarcade.constants import (
    CATCH_BONUS_POINTS,
    CATCH_BONUS_WEIGHT,
    CATCH_CATCHER_HEIGHT,
    CATCH_CATCHER_WIDTH,
    CATCH_COMBO_MAX_MULTIPLIER,
    CATCH_COMBO_MULTIPLIER_STEP,
    CATCH_COMBO_TIMEOUT_SECONDS,
    CATCH_COUNTDOWN_SECONDS,
    CATCH_DIFFICULTY_RAMP_SECONDS,
    CATCH_FALL_SPEED_END,
    CATCH_FALL_SPEED_START,
    CATCH_GOOD_POINTS,
    CATCH_GOOD_WEIGHT,
    CATCH_HAZARD_WEIGHT,
    CATCH_NEAR_MISS_BONUS_POINTS,
    CATCH_NEAR_MISS_DISTANCE,
    CATCH_OBJECT_RADIUS,
    CATCH_ROUND_DURATION_SECONDS,
    CATCH_SCREEN_SHAKE_DURATION,
    CATCH_SCREEN_SHAKE_MAGNITUDE,
    CATCH_SPAWN_INTERVAL_END,
    CATCH_SPAWN_INTERVAL_START,
    CATCH_START_LIVES,
)
from visionarcade.rendering.hud import HUD
from visionarcade.rendering.particles import ParticleSystem
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent

#: Visual-only jitter (screen shake) uses the module-level RNG, kept
#: separate from the game's own seedable `rng` so gameplay logic
#: (spawn timing/kind/position) stays deterministic in tests
#: regardless of how many times `draw()` happens to be called.
_shake_rng = random.Random()


class _Phase(enum.Enum):
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    GAME_OVER = "game_over"


@dataclass
class _FallingObject:
    x: float
    y: float
    kind: str  # "good" | "hazard" | "bonus"


class CatchGame(ArcadeGame):
    """The first fully playable mini-game."""

    id = "catch"
    title = "Vision Catch"
    objective = "Move your hand to catch falling objects and avoid hazards."

    def __init__(
        self,
        width: int,
        height: int,
        theme: Theme,
        typography: Typography,
        rng: Optional[random.Random] = None,
        reduced_particles: bool = False,
    ) -> None:
        self.width = width
        self.height = height
        self._theme = theme
        self._typography = typography
        self._rng = rng if rng is not None else random.Random()

        self.play_area = pygame.Rect(40, 120, width - 80, height - 160)
        self.particles = ParticleSystem(rng=self._rng, reduced=reduced_particles)
        self.hud = HUD(width)

        self.reset()

    # --- ArcadeGame interface -------------------------------------------

    def reset(self) -> None:
        self._phase = _Phase.COUNTDOWN
        self._countdown_remaining = CATCH_COUNTDOWN_SECONDS
        self._elapsed_playing = 0.0
        self._lives = CATCH_START_LIVES
        self._outcome: Optional[str] = None

        self._score = ScoreTracker()
        self._combo = ComboTracker(
            max_multiplier=CATCH_COMBO_MAX_MULTIPLIER,
            multiplier_step=CATCH_COMBO_MULTIPLIER_STEP,
            combo_timeout_seconds=CATCH_COMBO_TIMEOUT_SECONDS,
        )
        self._speed_curve = DifficultyCurve(
            CATCH_FALL_SPEED_START, CATCH_FALL_SPEED_END, CATCH_DIFFICULTY_RAMP_SECONDS
        )
        self._spawn_curve = DifficultyCurve(
            CATCH_SPAWN_INTERVAL_START, CATCH_SPAWN_INTERVAL_END, CATCH_DIFFICULTY_RAMP_SECONDS
        )

        self._spawn_timer = 0.0
        self._objects: List[_FallingObject] = []
        self._catcher_x: float = float(self.play_area.centerx)
        self._input: Optional[GameInput] = None
        self._shake_time_remaining = 0.0
        self._near_miss_banner_timer = 0.0

        self.particles.clear()

    def handle_intent(self, intent: FrameIntent) -> None:
        self._input = build_game_input(intent, self.play_area)

    def update(self, dt: float) -> None:
        self.particles.update(dt)
        self._shake_time_remaining = max(0.0, self._shake_time_remaining - dt)
        self._near_miss_banner_timer = max(0.0, self._near_miss_banner_timer - dt)

        if self._phase is _Phase.COUNTDOWN:
            self._update_countdown(dt)
        elif self._phase is _Phase.PLAYING:
            self._update_playing(dt)

    def is_finished(self) -> bool:
        return self._phase is _Phase.GAME_OVER

    def get_results(self) -> Dict[str, Any]:
        """The current score/stats snapshot — valid whether the round
        truly finished or is being abandoned early (e.g. "Quit to
        Hub" from the pause menu), so callers never need two methods."""
        return {
            "game_id": self.id,
            "score": self._score.score,
            "outcome": self._outcome or "in_progress",
            "lives_remaining": self._lives,
            "best_streak": self._combo.best_streak,
            "elapsed_seconds": round(self._elapsed_playing, 1),
        }

    # --- Internal update helpers -----------------------------------------

    def _update_countdown(self, dt: float) -> None:
        self._update_catcher_position()
        self._countdown_remaining -= dt
        if self._countdown_remaining <= 0:
            self._phase = _Phase.PLAYING

    def _update_catcher_position(self) -> None:
        if self._input is not None and self._input.pointer is not None:
            half_width = CATCH_CATCHER_WIDTH / 2
            min_x = self.play_area.left + half_width
            max_x = self.play_area.right - half_width
            self._catcher_x = max(min_x, min(max_x, self._input.pointer[0]))

    def _catcher_rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self._catcher_x - CATCH_CATCHER_WIDTH / 2),
            self.play_area.bottom - CATCH_CATCHER_HEIGHT - 8,
            CATCH_CATCHER_WIDTH,
            CATCH_CATCHER_HEIGHT,
        )

    def _update_playing(self, dt: float) -> None:
        self._update_catcher_position()
        self._elapsed_playing += dt
        self._combo.update(dt)

        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_object()
            jitter = self._rng.uniform(0.85, 1.15)
            self._spawn_timer = self._spawn_curve.value_at(self._elapsed_playing) * jitter

        fall_speed = self._speed_curve.value_at(self._elapsed_playing)
        catcher_rect = self._catcher_rect()
        surviving: List[_FallingObject] = []
        for obj in self._objects:
            obj.y += fall_speed * dt
            if circle_rect_overlap(obj.x, obj.y, CATCH_OBJECT_RADIUS, catcher_rect):
                self._handle_catch(obj)
                continue
            if obj.y - CATCH_OBJECT_RADIUS > self.play_area.bottom:
                self._handle_miss(obj, catcher_rect)
                continue
            surviving.append(obj)
        self._objects = surviving

        if self._lives <= 0:
            self._end_round("out_of_lives")
        elif self._elapsed_playing >= CATCH_ROUND_DURATION_SECONDS:
            self._end_round("cleared")

    def _spawn_object(self) -> None:
        kind = self._rng.choices(
            ("good", "hazard", "bonus"),
            weights=(CATCH_GOOD_WEIGHT, CATCH_HAZARD_WEIGHT, CATCH_BONUS_WEIGHT),
        )[0]
        min_x = self.play_area.left + CATCH_OBJECT_RADIUS
        max_x = self.play_area.right - CATCH_OBJECT_RADIUS
        x = self._rng.uniform(min_x, max_x)
        self._objects.append(_FallingObject(x=x, y=self.play_area.top - CATCH_OBJECT_RADIUS, kind=kind))

    def _handle_catch(self, obj: _FallingObject) -> None:
        if obj.kind == "good":
            multiplier = self._combo.register_hit()
            self._score.add(CATCH_GOOD_POINTS, multiplier)
            self.particles.burst(obj.x, obj.y, self._theme.success)
        elif obj.kind == "bonus":
            self._combo.register_hit()
            self._score.add(CATCH_BONUS_POINTS, 1.0)
            self.particles.burst(obj.x, obj.y, self._theme.accent, count=28)
        elif obj.kind == "hazard":
            self._lives -= 1
            self._combo.register_miss()
            self._shake_time_remaining = CATCH_SCREEN_SHAKE_DURATION
            self.particles.burst(obj.x, obj.y, self._theme.danger)

    def _handle_miss(self, obj: _FallingObject, catcher_rect: pygame.Rect) -> None:
        if obj.kind == "good":
            self._lives -= 1
            self._combo.register_miss()
        elif obj.kind == "hazard":
            if distance_to_rect(obj.x, obj.y, catcher_rect) <= CATCH_NEAR_MISS_DISTANCE:
                self._score.add(CATCH_NEAR_MISS_BONUS_POINTS, 1.0)
                self._near_miss_banner_timer = 1.0
        # "bonus" objects: missing one carries no penalty.

    def _end_round(self, outcome: str) -> None:
        self._phase = _Phase.GAME_OVER
        self._outcome = outcome

    # --- Drawing -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        offset = self._current_shake_offset()
        surface.fill(self._theme.background)
        self._draw_play_area(surface, offset)
        for obj in self._objects:
            self._draw_object(surface, obj, offset)
        self._draw_catcher(surface, offset)
        self.particles.draw(surface)

        time_remaining = (
            CATCH_ROUND_DURATION_SECONDS - self._elapsed_playing
            if self._phase is _Phase.PLAYING
            else None
        )
        self.hud.draw(
            surface,
            self._typography,
            self._theme,
            score=self._score.score,
            lives=self._lives,
            max_lives=CATCH_START_LIVES,
            combo=self._combo.streak,
            time_remaining=time_remaining,
        )

        if self._phase is _Phase.COUNTDOWN:
            self._draw_countdown(surface)
        if self._near_miss_banner_timer > 0:
            self._typography.render(
                surface,
                "Near miss!",
                "body",
                self._theme.accent,
                center=(self.width // 2, self.play_area.top - 20),
            )

    def _current_shake_offset(self) -> tuple[int, int]:
        if self._shake_time_remaining <= 0:
            return (0, 0)
        magnitude = CATCH_SCREEN_SHAKE_MAGNITUDE
        return (
            int(_shake_rng.uniform(-magnitude, magnitude)),
            int(_shake_rng.uniform(-magnitude, magnitude)),
        )

    def _draw_play_area(self, surface, offset) -> None:
        rect = self.play_area.move(*offset)
        pygame.draw.rect(surface, self._theme.surface, rect, border_radius=8)
        pygame.draw.rect(surface, self._theme.border, rect, width=2, border_radius=8)

    def _draw_object(self, surface, obj: _FallingObject, offset) -> None:
        color = {
            "good": self._theme.success,
            "hazard": self._theme.danger,
            "bonus": self._theme.accent,
        }[obj.kind]
        radius = CATCH_OBJECT_RADIUS * (1.3 if obj.kind == "bonus" else 1.0)
        center = (int(obj.x) + offset[0], int(obj.y) + offset[1])
        pygame.draw.circle(surface, color, center, int(radius))
        if obj.kind == "bonus":
            pygame.draw.circle(surface, self._theme.text_primary, center, int(radius), width=2)

    def _draw_catcher(self, surface, offset) -> None:
        rect = self._catcher_rect().move(*offset)
        pygame.draw.rect(surface, self._theme.accent, rect, border_radius=10)
        pygame.draw.rect(surface, self._theme.text_primary, rect, width=2, border_radius=10)

    def _draw_countdown(self, surface) -> None:
        remaining = max(0, int(self._countdown_remaining) + 1)
        label = str(remaining) if self._countdown_remaining > 0 else "Go!"
        self._typography.render(
            surface, label, "title", self._theme.text_primary, center=self.play_area.center
        )
