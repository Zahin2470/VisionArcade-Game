"""Temporal smoothing utilities.

Raw per-frame landmark positions are jittery even when a hand is
perfectly still — these classes turn that jitter into stable signals
without introducing perceptible lag, per Engineering Rule #4 ("never
let raw landmark jitter directly control critical game events").
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from visionarcade.constants import SMOOTHING_TIME_CONSTANT_SECONDS

Point = Tuple[float, float]


class ExponentialSmoother:
    """A frame-rate-independent exponential moving average (EMA).

    The blend factor is derived from elapsed time rather than fixed
    per-frame, so the effective amount of smoothing stays consistent
    whether the app runs at 30fps or 144fps:

        alpha = 1 - exp(-dt / time_constant)
    """

    def __init__(
        self,
        time_constant: float = SMOOTHING_TIME_CONSTANT_SECONDS,
        initial: Optional[float] = None,
    ) -> None:
        if time_constant <= 0:
            raise ValueError("time_constant must be positive")
        self.time_constant = time_constant
        self._value: Optional[float] = initial

    @property
    def value(self) -> Optional[float]:
        return self._value

    def reset(self, value: Optional[float] = None) -> None:
        self._value = value

    def update(self, raw_value: float, dt: float) -> float:
        """Feed one new raw sample and return the smoothed value.

        The first call (or a call after `reset(None)`) snaps directly
        to `raw_value` rather than smoothing from zero, so a freshly
        detected hand doesn't visibly "fly in" from the origin.
        """
        if self._value is None or dt <= 0:
            self._value = raw_value
            return self._value

        alpha = 1.0 - math.exp(-dt / self.time_constant)
        self._value = self._value + alpha * (raw_value - self._value)
        return self._value


class PointSmoother:
    """Smooths a 2D point by smoothing each axis independently."""

    def __init__(self, time_constant: float = SMOOTHING_TIME_CONSTANT_SECONDS) -> None:
        self._x = ExponentialSmoother(time_constant)
        self._y = ExponentialSmoother(time_constant)

    @property
    def value(self) -> Optional[Point]:
        if self._x.value is None or self._y.value is None:
            return None
        return (self._x.value, self._y.value)

    def reset(self, point: Optional[Point] = None) -> None:
        if point is None:
            self._x.reset(None)
            self._y.reset(None)
        else:
            self._x.reset(point[0])
            self._y.reset(point[1])

    def update(self, point: Point, dt: float) -> Point:
        return (self._x.update(point[0], dt), self._y.update(point[1], dt))

    def set_time_constant(self, time_constant: float) -> None:
        """Change how much smoothing is applied going forward, without
        resetting the smoother's current value (no visible jump) —
        used to apply the player's "smoothing" accessibility setting."""
        self._x.time_constant = time_constant
        self._y.time_constant = time_constant


class HysteresisGate:
    """Requires N consecutive confirmations before flipping a boolean state.

    `enter_frames` and `exit_frames` can differ — e.g. a hand can be
    confirmed *present* within a couple of frames, but only confirmed
    *absent* after a longer grace period, so one dropped detection
    frame doesn't make the hand seem to vanish.
    """

    def __init__(self, enter_frames: int = 1, exit_frames: int = 1, initial: bool = False) -> None:
        self.enter_frames = max(1, enter_frames)
        self.exit_frames = max(1, exit_frames)
        self._state = initial
        self._counter = 0

    @property
    def state(self) -> bool:
        return self._state

    def update(self, raw_value: bool) -> bool:
        if raw_value == self._state:
            self._counter = 0
            return self._state

        self._counter += 1
        threshold = self.exit_frames if self._state else self.enter_frames
        if self._counter >= threshold:
            self._state = raw_value
            self._counter = 0
        return self._state

    def reset(self, state: bool = False) -> None:
        self._state = state
        self._counter = 0
