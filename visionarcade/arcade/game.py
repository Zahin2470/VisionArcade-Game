"""The common interface every mini-game implements.

Locking this contract now (Phase 3) — before any concrete game exists
(Phase 4 onward) — is what lets `arcade/manager.py` treat every future
game identically: it never needs game-specific code to run one, per
Engineering Rule #3 ("never duplicate hand-tracking code inside
individual games") and the architecture goal of adding games without
rewriting camera, tracking, gesture, rendering, persistence, or audio
systems.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

import pygame

from visionarcade.vision.gestures import FrameIntent


class ArcadeGame(ABC):
    """Base class for every mini-game.

    Subclasses supply `id`, `title`, and `objective` as class
    attributes, and implement the lifecycle methods below. A game
    never touches the camera, tracker, or a global event loop directly
    — it only ever receives a `FrameIntent` (already stabilized) and a
    delta time.
    """

    id: str = ""
    title: str = ""
    objective: str = ""

    @abstractmethod
    def reset(self) -> None:
        """Return the game to its initial countdown/start state."""

    @abstractmethod
    def handle_intent(self, intent: FrameIntent) -> None:
        """Apply this frame's stabilized hand intent to game state."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance game simulation by `dt` seconds."""

    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the current game state onto `surface`."""

    @abstractmethod
    def is_finished(self) -> bool:
        """Whether the round has ended (win, loss, or time/score limit)."""

    @abstractmethod
    def get_results(self) -> Dict[str, Any]:
        """A summary of the finished round (at least `score`), for the
        results screen and score persistence."""
