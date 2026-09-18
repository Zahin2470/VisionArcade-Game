"""Reusable score and combo/streak tracking, shared across mini-games.

Kept generic (no game-specific point values here — those are each
game's own tunable constants) so every future game gets consistent,
already-tested combo-decay and multiplier behavior for free.
"""

from __future__ import annotations


class ScoreTracker:
    """A running score, accumulated via `add()`."""

    def __init__(self) -> None:
        self._score = 0

    @property
    def score(self) -> int:
        return self._score

    def add(self, base_points: int, multiplier: float = 1.0) -> int:
        """Add `base_points * multiplier` (rounded) to the score.
        Returns the amount actually gained, for feedback (e.g. a
        floating "+25" popup)."""
        gained = int(round(base_points * multiplier))
        self._score += gained
        return gained

    def reset(self) -> None:
        self._score = 0


class ComboTracker:
    """Tracks a consecutive-hit streak and the score multiplier it
    grants, with a timeout so an idle player's combo decays rather
    than lasting forever."""

    def __init__(
        self,
        max_multiplier: float = 4.0,
        multiplier_step: float = 0.5,
        combo_timeout_seconds: float = 2.0,
    ) -> None:
        self.max_multiplier = max_multiplier
        self.multiplier_step = multiplier_step
        self.combo_timeout_seconds = combo_timeout_seconds

        self._streak = 0
        self._best_streak = 0
        self._time_since_last_hit = 0.0

    @property
    def streak(self) -> int:
        return self._streak

    @property
    def best_streak(self) -> int:
        return self._best_streak

    @property
    def multiplier(self) -> float:
        return min(self.max_multiplier, 1.0 + self._streak * self.multiplier_step)

    def register_hit(self) -> float:
        """Extend the streak by one. Returns the new multiplier."""
        self._streak += 1
        self._best_streak = max(self._best_streak, self._streak)
        self._time_since_last_hit = 0.0
        return self.multiplier

    def register_miss(self) -> None:
        """Break the streak immediately (e.g. a hazard was caught, or
        a beneficial object was missed)."""
        self._streak = 0
        self._time_since_last_hit = 0.0

    def update(self, dt: float) -> None:
        """Advance the idle timer; breaks the streak once it exceeds
        `combo_timeout_seconds` with no new hit."""
        if self._streak <= 0:
            return
        self._time_since_last_hit += dt
        if self._time_since_last_hit >= self.combo_timeout_seconds:
            self.register_miss()

    def reset(self) -> None:
        self._streak = 0
        self._best_streak = 0
        self._time_since_last_hit = 0.0
