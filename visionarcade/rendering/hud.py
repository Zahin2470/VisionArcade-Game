"""A reusable in-game heads-up display: score, lives, combo, and timer.

Shared across mini-games so every game gets a consistent HUD without
reimplementing text layout. Lives are drawn as simple filled/outline
dots rather than a text glyph (e.g. a unicode heart), which isn't
guaranteed to render on every platform's default font.
"""

from __future__ import annotations

from typing import Optional

import pygame

from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography

_LIFE_DOT_RADIUS = 8
_LIFE_DOT_GAP = 22


class HUD:
    """Draws score/lives/combo/timer at fixed corners of the window."""

    def __init__(self, width: int) -> None:
        self.width = width

    def draw(
        self,
        surface: pygame.Surface,
        typography: Typography,
        theme: Theme,
        *,
        score: int,
        lives: Optional[int] = None,
        max_lives: Optional[int] = None,
        combo: int = 0,
        time_remaining: Optional[float] = None,
    ) -> None:
        typography.render(
            surface, f"Score: {score}", "heading", theme.text_primary, topleft=(20, 16)
        )

        if lives is not None and max_lives is not None:
            self._draw_lives(surface, theme, lives, max_lives, topleft=(24, 60))

        if combo > 1:
            typography.render(
                surface, f"Combo x{combo}", "body", theme.accent, topleft=(20, 84)
            )

        if time_remaining is not None:
            label = f"{max(0.0, time_remaining):0.0f}s"
            typography.render(
                surface, label, "body", theme.text_secondary, topleft=(self.width - 70, 16)
            )

    @staticmethod
    def _draw_lives(surface, theme: Theme, lives: int, max_lives: int, topleft) -> None:
        x, y = topleft
        for i in range(max_lives):
            center = (x + i * _LIFE_DOT_GAP, y)
            if i < lives:
                pygame.draw.circle(surface, theme.danger, center, _LIFE_DOT_RADIUS)
            else:
                pygame.draw.circle(surface, theme.danger, center, _LIFE_DOT_RADIUS, width=2)
