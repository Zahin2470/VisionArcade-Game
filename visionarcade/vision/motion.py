"""Velocity and swipe (directional trajectory) detection.

Operates on a short rolling history of positions, so a single fast-but-
noisy frame can't register as a swipe on its own — a swipe requires
sustained speed AND net displacement across a short detection window.
"""

from __future__ import annotations

import enum
import math
from collections import deque
from typing import Deque, Optional, Tuple

from visionarcade.constants import (
    SWIPE_COOLDOWN_SECONDS,
    SWIPE_DETECTION_WINDOW_SECONDS,
    SWIPE_MIN_DISPLACEMENT,
    SWIPE_MIN_SPEED,
)

Point = Tuple[float, float]


class SwipeDirection(enum.Enum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


class MotionTracker:
    """Tracks a short position history and derives velocity + swipes."""

    def __init__(
        self,
        window_seconds: float = SWIPE_DETECTION_WINDOW_SECONDS,
        min_speed: float = SWIPE_MIN_SPEED,
        min_displacement: float = SWIPE_MIN_DISPLACEMENT,
        cooldown_seconds: float = SWIPE_COOLDOWN_SECONDS,
    ) -> None:
        self.window_seconds = window_seconds
        self.min_speed = min_speed
        self.min_displacement = min_displacement
        self.cooldown_seconds = cooldown_seconds

        self._history: Deque[Tuple[float, Point]] = deque()  # (elapsed_time, position)
        self._elapsed = 0.0
        self._velocity: Point = (0.0, 0.0)
        self._cooldown_remaining = 0.0

    @property
    def velocity(self) -> Point:
        return self._velocity

    def reset(self) -> None:
        self._history.clear()
        self._elapsed = 0.0
        self._velocity = (0.0, 0.0)
        self._cooldown_remaining = 0.0

    def update(self, position: Point, dt: float) -> Point:
        """Feed one new position sample. Returns the current velocity."""
        if dt <= 0:
            return self._velocity

        previous = self._history[-1] if self._history else None
        self._elapsed += dt
        self._history.append((self._elapsed, position))

        cutoff = self._elapsed - self.window_seconds
        while len(self._history) > 1 and self._history[0][0] < cutoff:
            self._history.popleft()

        if previous is not None:
            _, prev_pos = previous
            self._velocity = (
                (position[0] - prev_pos[0]) / dt,
                (position[1] - prev_pos[1]) / dt,
            )

        if self._cooldown_remaining > 0:
            self._cooldown_remaining = max(0.0, self._cooldown_remaining - dt)

        return self._velocity

    def detect_swipe(self) -> Optional[SwipeDirection]:
        """Return a swipe direction if recent history qualifies, else None.

        Fires at most once per `cooldown_seconds`, and clears history on
        a successful detection, so one swipe motion can't be reported
        multiple times as it continues to be tracked frame by frame.
        """
        if self._cooldown_remaining > 0 or len(self._history) < 2:
            return None

        start_time, start_pos = self._history[0]
        end_time, end_pos = self._history[-1]
        elapsed = end_time - start_time
        if elapsed <= 0:
            return None

        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        distance = math.hypot(dx, dy)
        speed = distance / elapsed

        if distance < self.min_displacement or speed < self.min_speed:
            return None

        direction = SwipeDirection.RIGHT if dx > 0 else SwipeDirection.LEFT
        if abs(dy) > abs(dx):
            direction = SwipeDirection.DOWN if dy > 0 else SwipeDirection.UP

        self._cooldown_remaining = self.cooldown_seconds
        self._history.clear()
        self._elapsed = 0.0
        return direction
