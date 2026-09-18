"""A simple, deterministic difficulty ramp shared across mini-games.

Every game that speeds up or spawns more frequently over time (Catch's
fall speed, a future game's ball speed, etc.) can reuse one
`DifficultyCurve` instead of hand-rolling its own ramp math.
"""

from __future__ import annotations


class DifficultyCurve:
    """A linear ramp from `start` to `end` over `ramp_seconds`, clamped
    to `end` afterward. `start` may be greater than `end` (e.g. a spawn
    interval that shrinks over time) — the ramp direction doesn't matter."""

    def __init__(self, start: float, end: float, ramp_seconds: float) -> None:
        if ramp_seconds <= 0:
            raise ValueError("ramp_seconds must be positive")
        self.start = start
        self.end = end
        self.ramp_seconds = ramp_seconds

    def value_at(self, elapsed_seconds: float) -> float:
        """The ramped value at `elapsed_seconds` into the round."""
        t = max(0.0, min(1.0, elapsed_seconds / self.ramp_seconds))
        return self.start + (self.end - self.start) * t
