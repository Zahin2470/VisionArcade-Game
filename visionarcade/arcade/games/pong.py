"""Vision Pong: move your hand to control a paddle and rally the ball.

A round runs MODE_SELECT -> COUNTDOWN -> PLAYING -> GAME_OVER.
MODE_SELECT is itself touchless (point and pinch to choose 1-player vs
AI, or 2-player using both hands), consistent with "gameplay controls
should remain touchless" — there's no reason a game's own sub-menu
needs the keyboard just because the shell's menus support it.

Ball speed ramps over the whole match via `DifficultyCurve`, then gets
an extra multiplicative boost on every paddle hit within a rally
(capped), so a long rally visibly escalates. The AI opponent chases
the ball with a capped speed and a small persistent aiming error, so
it's beatable rather than a perfect wall, and it also gets faster as
the match goes on.
"""

from __future__ import annotations

import enum
import math
import random
from typing import Any, Dict, Optional

import pygame

from visionarcade.arcade.collision import circle_rect_overlap
from visionarcade.arcade.difficulty import DifficultyCurve
from visionarcade.arcade.game import ArcadeGame
from visionarcade.arcade.input import build_game_input, map_point_to_rect
from visionarcade.arcade.scoring import ComboTracker
from visionarcade.constants import (
    PONG_AI_REACTION_ERROR,
    PONG_AI_SPEED_END,
    PONG_AI_SPEED_START,
    PONG_BALL_HIT_SPEEDUP,
    PONG_BALL_MAX_SPEED,
    PONG_BALL_RADIUS,
    PONG_BALL_SPEED_END,
    PONG_BALL_SPEED_START,
    PONG_BOUNCE_MAX_ANGLE_SPEED,
    PONG_COUNTDOWN_SECONDS,
    PONG_DIFFICULTY_RAMP_SECONDS,
    PONG_PADDLE_HEIGHT,
    PONG_PADDLE_MARGIN,
    PONG_PADDLE_WIDTH,
    PONG_POINTS_TO_WIN,
    PONG_SERVE_DELAY_SECONDS,
)
from visionarcade.rendering.particles import ParticleSystem
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.navigation import FocusGroup, SelectableItem
from visionarcade.vision.gestures import FrameIntent

_MODE_BUTTON_WIDTH = 260
_MODE_BUTTON_HEIGHT = 140
_MODE_BUTTON_GAP = 40
_RALLY_BANNER_EVERY = 3  # show "Rally xN!" every N consecutive hits
_RALLY_BANNER_SECONDS = 1.2


class PongMode(enum.Enum):
    SINGLE_PLAYER = "single_player"
    TWO_PLAYER = "two_player"


class _Phase(enum.Enum):
    MODE_SELECT = "mode_select"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    GAME_OVER = "game_over"


class PongGame(ArcadeGame):
    """Single- or two-player Pong, chosen via a touchless sub-menu."""

    id = "pong"
    title = "Vision Pong"
    objective = f"Move your hand to control your paddle — first to {PONG_POINTS_TO_WIN} points wins."

    def __init__(
        self,
        width: int,
        height: int,
        theme: Theme,
        typography: Typography,
        rng: Optional[random.Random] = None,
        points_to_win: int = PONG_POINTS_TO_WIN,
    ) -> None:
        self.width = width
        self.height = height
        self._theme = theme
        self._typography = typography
        self._rng = rng if rng is not None else random.Random()
        self._points_to_win = points_to_win

        self.play_area = pygame.Rect(40, 110, width - 80, height - 170)
        self.particles = ParticleSystem(rng=self._rng)

        self._mode_focus = FocusGroup()
        self._layout_mode_select()

        self.reset()

    # --- ArcadeGame interface -------------------------------------------

    def reset(self) -> None:
        self._phase = _Phase.MODE_SELECT
        self._mode: Optional[PongMode] = None
        self._outcome: Optional[str] = None
        self._intent: Optional[FrameIntent] = None

        self._countdown_remaining = PONG_COUNTDOWN_SECONDS
        self._elapsed_playing = 0.0

        self._left_score = 0
        self._right_score = 0
        self._left_paddle_y = float(self.play_area.centery)
        self._right_paddle_y = float(self.play_area.centery)

        self._speed_curve = DifficultyCurve(
            PONG_BALL_SPEED_START, PONG_BALL_SPEED_END, PONG_DIFFICULTY_RAMP_SECONDS
        )
        self._ai_speed_curve = DifficultyCurve(
            PONG_AI_SPEED_START, PONG_AI_SPEED_END, PONG_DIFFICULTY_RAMP_SECONDS
        )
        self._ai_target_error = 0.0
        self._ai_prev_heading_left = False

        self._ball_x = float(self.play_area.centerx)
        self._ball_y = float(self.play_area.centery)
        self._ball_vx = 0.0
        self._ball_vy = 0.0
        self._ball_speed = PONG_BALL_SPEED_START
        self._serve_timer = 0.0

        self._rally_hits = 0
        self._rally = ComboTracker()  # used purely as a hit counter; .update() is never called
        self._rally_banner_timer = 0.0
        self._rally_banner_text = ""

        self.particles.clear()

    def handle_intent(self, intent: FrameIntent) -> None:
        self._intent = intent

    def update(self, dt: float) -> None:
        self.particles.update(dt)
        self._rally_banner_timer = max(0.0, self._rally_banner_timer - dt)

        if self._phase is _Phase.MODE_SELECT:
            self._update_mode_select()
        elif self._phase is _Phase.COUNTDOWN:
            self._update_paddles()
            self._countdown_remaining -= dt
            if self._countdown_remaining <= 0:
                self._phase = _Phase.PLAYING
                self._elapsed_playing = 0.0
                self._serve()
        elif self._phase is _Phase.PLAYING:
            self._elapsed_playing += dt
            self._update_paddles()
            if self._mode is PongMode.SINGLE_PLAYER:
                self._update_ai(dt)
            if self._serve_timer > 0:
                self._serve_timer -= dt
            else:
                self._update_ball(dt)

    def is_finished(self) -> bool:
        return self._phase is _Phase.GAME_OVER

    def get_results(self) -> Dict[str, Any]:
        """The current match snapshot — valid mid-match too (e.g. an
        early "Quit to Hub"). `score` is the right paddle's points,
        which is always the human player in both modes."""
        return {
            "game_id": self.id,
            "score": self._right_score,
            "outcome": self._outcome or "in_progress",
            "left_score": self._left_score,
            "right_score": self._right_score,
            "best_streak": self._rally.best_streak,
            "mode": self._mode.value if self._mode else None,
            "elapsed_seconds": round(self._elapsed_playing, 1),
        }

    # --- Mode select -------------------------------------------------------

    def _layout_mode_select(self) -> None:
        total_width = 2 * _MODE_BUTTON_WIDTH + _MODE_BUTTON_GAP
        left = self.play_area.centerx - total_width // 2
        top = self.play_area.centery - _MODE_BUTTON_HEIGHT // 2
        items = [
            SelectableItem(
                item_id="single",
                rect=pygame.Rect(left, top, _MODE_BUTTON_WIDTH, _MODE_BUTTON_HEIGHT),
            ),
            SelectableItem(
                item_id="two_player",
                rect=pygame.Rect(
                    left + _MODE_BUTTON_WIDTH + _MODE_BUTTON_GAP,
                    top,
                    _MODE_BUTTON_WIDTH,
                    _MODE_BUTTON_HEIGHT,
                ),
            ),
        ]
        self._mode_focus.set_items(items)

    def _update_mode_select(self) -> None:
        if self._intent is None:
            return
        game_input = build_game_input(self._intent, self.play_area)
        self._mode_focus.update_pointer(game_input.pointer)
        if game_input.pinch_just_started:
            activated = self._mode_focus.activate_focused()
            if activated is not None:
                self._start_mode(activated)

    def _start_mode(self, mode_id: str) -> None:
        self._mode = PongMode.SINGLE_PLAYER if mode_id == "single" else PongMode.TWO_PLAYER
        self._phase = _Phase.COUNTDOWN
        self._countdown_remaining = PONG_COUNTDOWN_SECONDS

    # --- Paddles -------------------------------------------------------------

    def _clamp_paddle_y(self, y: float) -> float:
        half = PONG_PADDLE_HEIGHT / 2
        return max(self.play_area.top + half, min(self.play_area.bottom - half, y))

    def _update_paddles(self) -> None:
        if self._intent is None:
            return

        if self._mode is PongMode.TWO_PLAYER:
            left_pos = (
                map_point_to_rect(self._intent.left.position, self.play_area)
                if self._intent.left.present
                else None
            )
            if left_pos is not None:
                self._left_paddle_y = self._clamp_paddle_y(left_pos[1])

        right_pos = (
            map_point_to_rect(self._intent.right.position, self.play_area)
            if self._intent.right.present
            else None
        )
        if right_pos is not None:
            self._right_paddle_y = self._clamp_paddle_y(right_pos[1])

    def _update_ai(self, dt: float) -> None:
        heading_left = self._ball_vx < 0
        if heading_left and not self._ai_prev_heading_left:
            # Re-roll the AI's aim error only once per approach, so it
            # reads as a consistent (beatable) imprecision rather than
            # twitchy per-frame noise.
            self._ai_target_error = self._rng.uniform(-PONG_AI_REACTION_ERROR, PONG_AI_REACTION_ERROR)
        self._ai_prev_heading_left = heading_left

        target_y = self._ball_y + self._ai_target_error
        max_speed = self._ai_speed_curve.value_at(self._elapsed_playing)
        delta = target_y - self._left_paddle_y
        step = max(-max_speed * dt, min(max_speed * dt, delta))
        self._left_paddle_y = self._clamp_paddle_y(self._left_paddle_y + step)

    def _left_paddle_rect(self) -> pygame.Rect:
        x = self.play_area.left + PONG_PADDLE_MARGIN
        return pygame.Rect(
            x, int(self._left_paddle_y - PONG_PADDLE_HEIGHT / 2), PONG_PADDLE_WIDTH, PONG_PADDLE_HEIGHT
        )

    def _right_paddle_rect(self) -> pygame.Rect:
        x = self.play_area.right - PONG_PADDLE_MARGIN - PONG_PADDLE_WIDTH
        return pygame.Rect(
            x, int(self._right_paddle_y - PONG_PADDLE_HEIGHT / 2), PONG_PADDLE_WIDTH, PONG_PADDLE_HEIGHT
        )

    # --- Ball ------------------------------------------------------------------

    def _serve(self) -> None:
        self._ball_x = float(self.play_area.centerx)
        self._ball_y = float(self.play_area.centery)
        base_speed = self._speed_curve.value_at(self._elapsed_playing)
        self._ball_speed = base_speed

        angle = self._rng.uniform(-math.pi / 4, math.pi / 4)  # +/- 45 degrees from horizontal
        direction = self._rng.choice((-1, 1))
        self._ball_vx = math.cos(angle) * base_speed * direction
        self._ball_vy = math.sin(angle) * base_speed

        self._serve_timer = PONG_SERVE_DELAY_SECONDS
        self._rally_hits = 0
        self._rally.reset()

    def _update_ball(self, dt: float) -> None:
        self._ball_x += self._ball_vx * dt
        self._ball_y += self._ball_vy * dt

        if self._ball_y - PONG_BALL_RADIUS <= self.play_area.top and self._ball_vy < 0:
            self._ball_y = self.play_area.top + PONG_BALL_RADIUS
            self._ball_vy *= -1
        elif self._ball_y + PONG_BALL_RADIUS >= self.play_area.bottom and self._ball_vy > 0:
            self._ball_y = self.play_area.bottom - PONG_BALL_RADIUS
            self._ball_vy *= -1

        left_rect = self._left_paddle_rect()
        right_rect = self._right_paddle_rect()
        if self._ball_vx < 0 and circle_rect_overlap(self._ball_x, self._ball_y, PONG_BALL_RADIUS, left_rect):
            self._bounce_off_paddle(left_rect)
        elif self._ball_vx > 0 and circle_rect_overlap(
            self._ball_x, self._ball_y, PONG_BALL_RADIUS, right_rect
        ):
            self._bounce_off_paddle(right_rect)

        if self._ball_x < self.play_area.left:
            self._award_point("right")
        elif self._ball_x > self.play_area.right:
            self._award_point("left")

    def _bounce_off_paddle(self, paddle_rect: pygame.Rect) -> None:
        relative = (self._ball_y - paddle_rect.centery) / (paddle_rect.height / 2)
        relative = max(-1.0, min(1.0, relative))

        new_speed = min(PONG_BALL_MAX_SPEED, self._ball_speed * PONG_BALL_HIT_SPEEDUP)
        vy = relative * PONG_BOUNCE_MAX_ANGLE_SPEED
        vx_magnitude = math.sqrt(max(new_speed**2 - vy**2, (new_speed * 0.5) ** 2))
        direction_x = 1 if self._ball_vx < 0 else -1  # reverse horizontal direction

        self._ball_vx = direction_x * vx_magnitude
        self._ball_vy = vy
        self._ball_speed = new_speed

        # Nudge the ball just outside the paddle so it can't re-collide next frame.
        if direction_x > 0:
            self._ball_x = paddle_rect.right + PONG_BALL_RADIUS + 1
        else:
            self._ball_x = paddle_rect.left - PONG_BALL_RADIUS - 1

        self._rally_hits += 1
        self._rally.register_hit()
        self.particles.burst(self._ball_x, self._ball_y, self._theme.accent, count=10)
        if self._rally_hits % _RALLY_BANNER_EVERY == 0:
            self._rally_banner_text = f"Rally x{self._rally_hits}!"
            self._rally_banner_timer = _RALLY_BANNER_SECONDS

    def _award_point(self, scorer: str) -> None:
        if scorer == "left":
            self._left_score += 1
        else:
            self._right_score += 1
        self._rally.register_miss()

        if self._left_score >= self._points_to_win or self._right_score >= self._points_to_win:
            self._end_round(scorer)
        else:
            self._serve()

    def _end_round(self, scorer: str) -> None:
        self._phase = _Phase.GAME_OVER
        if self._mode is PongMode.SINGLE_PLAYER:
            self._outcome = "player_win" if scorer == "right" else "player_loss"
        else:
            self._outcome = f"{scorer}_win"

    # --- Drawing ---------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(self._theme.background)
        self._draw_play_area(surface)

        if self._phase is _Phase.MODE_SELECT:
            self._draw_mode_select(surface)
            return

        self._draw_center_line(surface)
        self._draw_paddles(surface)
        self._draw_ball(surface)
        self.particles.draw(surface)
        self._draw_scoreboard(surface)

        if self._phase is _Phase.COUNTDOWN:
            self._draw_countdown(surface)
        if self._rally_banner_timer > 0:
            self._typography.render(
                surface,
                self._rally_banner_text,
                "body",
                self._theme.accent,
                center=(self.width // 2, self.play_area.top - 16),
            )

    def _draw_play_area(self, surface) -> None:
        pygame.draw.rect(surface, self._theme.surface, self.play_area, border_radius=8)
        pygame.draw.rect(surface, self._theme.border, self.play_area, width=2, border_radius=8)

    def _draw_center_line(self, surface) -> None:
        x = self.play_area.centerx
        dash_height, gap = 14, 10
        y = self.play_area.top
        while y < self.play_area.bottom:
            pygame.draw.line(surface, self._theme.border, (x, y), (x, min(y + dash_height, self.play_area.bottom)), 2)
            y += dash_height + gap

    def _draw_paddles(self, surface) -> None:
        pygame.draw.rect(surface, self._theme.accent, self._left_paddle_rect(), border_radius=6)
        pygame.draw.rect(surface, self._theme.accent, self._right_paddle_rect(), border_radius=6)

    def _draw_ball(self, surface) -> None:
        pygame.draw.circle(
            surface, self._theme.text_primary, (int(self._ball_x), int(self._ball_y)), int(PONG_BALL_RADIUS)
        )

    def _draw_scoreboard(self, surface) -> None:
        self._typography.render(
            surface,
            f"{self._left_score}   -   {self._right_score}",
            "title",
            self._theme.text_primary,
            center=(self.width // 2, 56),
        )
        if self._mode is PongMode.SINGLE_PLAYER:
            self._typography.render(
                surface, "AI", "small", self._theme.text_secondary, center=(self.play_area.left + 40, 30)
            )
            self._typography.render(
                surface, "You", "small", self._theme.text_secondary, center=(self.play_area.right - 40, 30)
            )
        else:
            self._typography.render(
                surface, "Left Hand", "small", self._theme.text_secondary, center=(self.play_area.left + 60, 30)
            )
            self._typography.render(
                surface, "Right Hand", "small", self._theme.text_secondary, center=(self.play_area.right - 60, 30)
            )

    def _draw_mode_select(self, surface) -> None:
        self._typography.render(
            surface,
            "Choose a mode",
            "heading",
            self._theme.text_primary,
            center=(self.play_area.centerx, self.play_area.top + 50),
        )
        self._typography.render(
            surface,
            "Point and pinch to select",
            "small",
            self._theme.text_secondary,
            center=(self.play_area.centerx, self.play_area.top + 80),
        )

        labels = {"single": ["1 Player", "(vs AI)"], "two_player": ["2 Player", "(Left vs Right hand)"]}
        for item in self._mode_focus.items:
            focused = item.item_id == self._mode_focus.focused_id
            color = self._theme.surface_focused if focused else self._theme.surface
            pygame.draw.rect(surface, color, item.rect, border_radius=14)
            if focused:
                pygame.draw.rect(surface, self._theme.accent, item.rect, width=3, border_radius=14)

            lines = labels[item.item_id]
            y = item.rect.centery - (len(lines) - 1) * 14
            for line in lines:
                self._typography.render(
                    surface, line, "body", self._theme.text_primary, center=(item.rect.centerx, y)
                )
                y += 28

    def _draw_countdown(self, surface) -> None:
        remaining = max(0, int(self._countdown_remaining) + 1)
        label = str(remaining) if self._countdown_remaining > 0 else "Go!"
        self._typography.render(
            surface, label, "title", self._theme.text_primary, center=self.play_area.center
        )
