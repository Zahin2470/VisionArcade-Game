"""Vision Aim: a reticle follows your index fingertip; pinch activates
a target.

A sequence of `AIM_TARGET_COUNT` targets appear one at a time, each
with a shrinking time limit (the limit itself gets tighter as the
sequence progresses, via `DifficultyCurve` — but ramped over the
*target index*, not wall-clock time, since Aim's pacing is inherently
target-by-target rather than continuous). Missing too many
(`AIM_MAX_MISSES`) ends the round early; completing the whole sequence
within budget clears it. Score rewards both accuracy (you have to
actually hit it) and reaction time (a speed bonus that tapers to zero
near the time limit), plus a streak multiplier for consecutive hits.
"""

from __future__ import annotations

import enum
import random
from typing import Any, Dict, List, Optional, Tuple

import pygame

from visionarcade.arcade.difficulty import DifficultyCurve
from visionarcade.arcade.game import ArcadeGame
from visionarcade.arcade.input import GameInput, build_game_input
from visionarcade.arcade.scoring import ComboTracker, ScoreTracker
from visionarcade.constants import (
    AIM_BASE_POINTS,
    AIM_COUNTDOWN_SECONDS,
    AIM_DIFFICULTY_RAMP_TARGETS,
    AIM_MAX_MISSES,
    AIM_SPEED_BONUS_MAX,
    AIM_STREAK_MAX_MULTIPLIER,
    AIM_STREAK_MULTIPLIER_STEP,
    AIM_TARGET_COUNT,
    AIM_TARGET_RADIUS,
    AIM_TIME_LIMIT_END,
    AIM_TIME_LIMIT_START,
)
from visionarcade.rendering.particles import ParticleSystem
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.gestures import FrameIntent

Point = Tuple[float, float]


class _Phase(enum.Enum):
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    GAME_OVER = "game_over"


class AimGame(ArcadeGame):
    """A reaction-time and accuracy target sequence."""

    id = "aim"
    title = "Vision Aim"
    objective = "Point at each target and pinch to hit it before time runs out."

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

        self.play_area = pygame.Rect(40, 120, width - 80, height - 200)
        self.particles = ParticleSystem(rng=self._rng)

        self._time_limit_curve = DifficultyCurve(
            AIM_TIME_LIMIT_START, AIM_TIME_LIMIT_END, AIM_DIFFICULTY_RAMP_TARGETS
        )

        self.reset()

    # --- ArcadeGame interface -------------------------------------------

    def reset(self) -> None:
        self._phase = _Phase.COUNTDOWN
        self._countdown_remaining = AIM_COUNTDOWN_SECONDS
        self._outcome: Optional[str] = None

        self._score = ScoreTracker()
        self._streak = ComboTracker(
            max_multiplier=AIM_STREAK_MAX_MULTIPLIER,
            multiplier_step=AIM_STREAK_MULTIPLIER_STEP,
        )

        self._targets_presented = 0
        self._targets_hit = 0
        self._targets_missed = 0
        self._reaction_times: List[float] = []

        self._target_pos: Optional[Point] = None
        self._target_time_limit = AIM_TIME_LIMIT_START
        self._target_time_remaining = 0.0
        self._target_spawned_at = 0.0
        self._hovering = False

        self._elapsed_playing = 0.0
        self._input: Optional[GameInput] = None
        self._hit_flash_timer = 0.0
        self._hit_flash_pos: Optional[Point] = None
        self._hit_flash_text = ""
        self._miss_flash_timer = 0.0
        self._miss_flash_pos: Optional[Point] = None

        self.particles.clear()

    def handle_intent(self, intent: FrameIntent) -> None:
        self._input = build_game_input(intent, self.play_area)

    def update(self, dt: float) -> None:
        self.particles.update(dt)
        self._hit_flash_timer = max(0.0, self._hit_flash_timer - dt)
        self._miss_flash_timer = max(0.0, self._miss_flash_timer - dt)

        if self._phase is _Phase.COUNTDOWN:
            self._countdown_remaining -= dt
            if self._countdown_remaining <= 0:
                self._phase = _Phase.PLAYING
                self._spawn_target()
        elif self._phase is _Phase.PLAYING:
            self._update_playing(dt)

    def is_finished(self) -> bool:
        return self._phase is _Phase.GAME_OVER

    def get_results(self) -> Dict[str, Any]:
        accuracy = self._targets_hit / self._targets_presented if self._targets_presented else 0.0
        average_reaction_time = (
            sum(self._reaction_times) / len(self._reaction_times) if self._reaction_times else None
        )
        return {
            "game_id": self.id,
            "score": self._score.score,
            "outcome": self._outcome or "in_progress",
            "accuracy": round(accuracy, 3),
            "average_reaction_time": round(average_reaction_time, 3) if average_reaction_time else None,
            "missed_targets": self._targets_missed,
            "best_streak": self._streak.best_streak,
            "targets_presented": self._targets_presented,
            "elapsed_seconds": round(self._elapsed_playing, 1),
        }

    # --- Playing -----------------------------------------------------------

    def _update_playing(self, dt: float) -> None:
        self._elapsed_playing += dt

        pointer = self._input.pointer if self._input is not None else None
        self._hovering = (
            pointer is not None
            and self._target_pos is not None
            and _distance(pointer, self._target_pos) <= AIM_TARGET_RADIUS
        )

        if self._input is not None and self._input.pinch_just_started and self._hovering:
            self._register_hit()
            return  # a hit already advances to the next target (or ends the round)

        self._target_time_remaining -= dt
        if self._target_time_remaining <= 0:
            self._register_miss()

    def _spawn_target(self) -> None:
        self._targets_presented += 1
        margin = AIM_TARGET_RADIUS + 10
        x = self._rng.uniform(self.play_area.left + margin, self.play_area.right - margin)
        y = self._rng.uniform(self.play_area.top + margin, self.play_area.bottom - margin)
        self._target_pos = (x, y)

        self._target_time_limit = self._time_limit_curve.value_at(self._targets_presented - 1)
        self._target_time_remaining = self._target_time_limit
        self._target_spawned_at = self._elapsed_playing

    def _register_hit(self) -> None:
        reaction_time = self._elapsed_playing - self._target_spawned_at
        self._reaction_times.append(reaction_time)
        self._targets_hit += 1

        speed_fraction = max(0.0, 1.0 - (reaction_time / self._target_time_limit))
        speed_bonus = int(round(AIM_SPEED_BONUS_MAX * speed_fraction))
        multiplier = self._streak.register_hit()
        gained = self._score.add(AIM_BASE_POINTS + speed_bonus, multiplier)

        if self._target_pos is not None:
            self.particles.burst(self._target_pos[0], self._target_pos[1], self._theme.success, count=16)
        self._hit_flash_timer = 0.5
        self._hit_flash_pos = self._target_pos
        self._hit_flash_text = f"+{gained}"

        self._advance_or_end()

    def _register_miss(self) -> None:
        self._targets_missed += 1
        self._streak.register_miss()
        self._miss_flash_timer = 0.4
        self._miss_flash_pos = self._target_pos
        self._advance_or_end()

    def _advance_or_end(self) -> None:
        if self._targets_missed >= AIM_MAX_MISSES:
            self._end_round("too_many_misses")
        elif self._targets_presented >= AIM_TARGET_COUNT:
            self._end_round("cleared")
        else:
            self._spawn_target()

    def _end_round(self, outcome: str) -> None:
        self._phase = _Phase.GAME_OVER
        self._outcome = outcome
        self._target_pos = None

    # --- Drawing -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(self._theme.background)
        self._draw_play_area(surface)

        if self._target_pos is not None:
            self._draw_target(surface)
        self.particles.draw(surface)
        self._draw_reticle(surface)
        self._draw_hud(surface)

        if self._phase is _Phase.COUNTDOWN:
            self._draw_countdown(surface)
        if self._hit_flash_timer > 0 and self._hit_flash_pos is not None:
            self._typography.render(
                surface,
                self._hit_flash_text,
                "body",
                self._theme.success,
                center=(int(self._hit_flash_pos[0]), int(self._hit_flash_pos[1] - 40)),
            )
        if self._miss_flash_timer > 0 and self._miss_flash_pos is not None:
            pygame.draw.circle(
                surface, self._theme.danger, (int(self._miss_flash_pos[0]), int(self._miss_flash_pos[1])),
                int(AIM_TARGET_RADIUS + 6), width=3,
            )

    def _draw_play_area(self, surface) -> None:
        pygame.draw.rect(surface, self._theme.surface, self.play_area, border_radius=8)
        pygame.draw.rect(surface, self._theme.border, self.play_area, width=2, border_radius=8)

    def _draw_target(self, surface) -> None:
        assert self._target_pos is not None
        x, y = int(self._target_pos[0]), int(self._target_pos[1])
        color = self._theme.accent if self._hovering else self._theme.success
        pygame.draw.circle(surface, self._theme.surface, (x, y), int(AIM_TARGET_RADIUS))
        pygame.draw.circle(surface, color, (x, y), int(AIM_TARGET_RADIUS), width=4)
        pygame.draw.circle(surface, color, (x, y), int(AIM_TARGET_RADIUS * 0.35))

        # A depleting arc showing how much time is left on this target.
        fraction = max(0.0, min(1.0, self._target_time_remaining / self._target_time_limit))
        if fraction > 0:
            rect = pygame.Rect(0, 0, int(AIM_TARGET_RADIUS * 2.6), int(AIM_TARGET_RADIUS * 2.6))
            rect.center = (x, y)
            start_angle = -1.5707963267948966  # -90 degrees: start at the top
            end_angle = start_angle + fraction * 6.283185307179586
            pygame.draw.arc(surface, color, rect, start_angle, end_angle, width=3)

    def _draw_reticle(self, surface) -> None:
        pointer = self._input.pointer if self._input is not None else None
        if pointer is None:
            return
        x, y = int(pointer[0]), int(pointer[1])
        color = self._theme.accent
        radius = 14
        pygame.draw.circle(surface, color, (x, y), radius, width=2)
        pygame.draw.line(surface, color, (x - radius - 6, y), (x - radius + 4, y), 2)
        pygame.draw.line(surface, color, (x + radius - 4, y), (x + radius + 6, y), 2)
        pygame.draw.line(surface, color, (x, y - radius - 6), (x, y - radius + 4), 2)
        pygame.draw.line(surface, color, (x, y + radius - 4), (x, y + radius + 6), 2)

    def _draw_hud(self, surface) -> None:
        self._typography.render(
            surface, f"Score: {self._score.score}", "heading", self._theme.text_primary, topleft=(20, 16)
        )
        self._typography.render(
            surface,
            f"Target {min(self._targets_presented, AIM_TARGET_COUNT)}/{AIM_TARGET_COUNT}",
            "small",
            self._theme.text_secondary,
            topleft=(20, 56),
        )
        self._typography.render(
            surface,
            f"Misses: {self._targets_missed}/{AIM_MAX_MISSES}",
            "small",
            self._theme.danger,
            topleft=(20, 78),
        )
        if self._streak.streak > 1:
            self._typography.render(
                surface, f"Streak x{self._streak.streak}", "body", self._theme.accent, topleft=(20, 100)
            )

    def _draw_countdown(self, surface) -> None:
        remaining = max(0, int(self._countdown_remaining) + 1)
        label = str(remaining) if self._countdown_remaining > 0 else "Go!"
        self._typography.render(
            surface, label, "title", self._theme.text_primary, center=self.play_area.center
        )


def _distance(a: Point, b: Point) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
