"""A simple fade transition between screens.

Applied once, at the shell level (`ArcadeManager`), whenever its state
changes — individual screens don't need to know transitions exist. The
overlay surface is allocated once at construction and reused every
frame (refilled, not reallocated), per the project's performance
requirements against repeated large allocations.
"""

from __future__ import annotations

import pygame

_DEFAULT_HALF_DURATION = 0.15  # seconds to fade to black; fading back in mirrors it


class FadeTransition:
    """A brief fade-to-black-and-back, triggered by `start()`."""

    def __init__(self, width: int, height: int, half_duration: float = _DEFAULT_HALF_DURATION) -> None:
        self.half_duration = half_duration
        self._elapsed = 0.0
        self._active = False
        self._overlay = pygame.Surface((width, height), pygame.SRCALPHA)

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self) -> None:
        self._elapsed = 0.0
        self._active = True

    def update(self, dt: float) -> None:
        if not self._active:
            return
        self._elapsed += dt
        if self._elapsed >= self.half_duration * 2:
            self._active = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self._active:
            return
        if self._elapsed < self.half_duration:
            fraction = self._elapsed / self.half_duration  # 0 -> 1: fading to black
        else:
            fraction = 1.0 - (self._elapsed - self.half_duration) / self.half_duration  # 1 -> 0

        alpha = int(255 * max(0.0, min(1.0, fraction)))
        if alpha <= 0:
            return
        self._overlay.fill((0, 0, 0, alpha))
        surface.blit(self._overlay, (0, 0))
