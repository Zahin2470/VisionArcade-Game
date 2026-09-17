"""Base pygame window/surface lifecycle.

This module owns the *only* `pygame.display` window in the application.
No game-specific module should create its own window or call
`pygame.init()`/`pygame.quit()` directly — everything draws onto the
surface this class exposes. HUD, themes, particles, and transitions
(later phases) draw on top of this base surface rather than replacing
it.
"""

from __future__ import annotations

import logging
from typing import Optional

import pygame

from visionarcade.constants import (
    APP_NAME,
    BACKGROUND_COLOR,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    PLACEHOLDER_TEXT_COLOR,
)

logger = logging.getLogger(__name__)


class RendererError(Exception):
    """Raised for programmer-error cases (e.g. drawing before opening)."""


class Renderer:
    """Owns the pygame window and exposes a simple draw/present cycle."""

    def __init__(
        self,
        width: int = DEFAULT_WINDOW_WIDTH,
        height: int = DEFAULT_WINDOW_HEIGHT,
        title: str = APP_NAME,
    ) -> None:
        self.width = width
        self.height = height
        self.title = title

        self._surface: Optional[pygame.Surface] = None
        self._font: Optional[pygame.font.Font] = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def surface(self) -> pygame.Surface:
        if self._surface is None:
            raise RendererError("Renderer.open() must be called before accessing `surface`.")
        return self._surface

    def open(self) -> None:
        """Initialize pygame and create the application window.

        Safe to call more than once; subsequent calls are no-ops.
        """
        if self._is_open:
            return

        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        self._surface = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        self._font = pygame.font.SysFont(None, 32)
        self._is_open = True
        logger.info("Renderer opened at %dx%d.", self.width, self.height)

    def pump_events(self) -> bool:
        """Process the OS event queue.

        Returns False if the player requested to quit (window close or
        Escape key), True otherwise. Callers should stop their main loop
        promptly when this returns False.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
        return True

    def clear(self, color: tuple[int, int, int] = BACKGROUND_COLOR) -> None:
        """Fill the whole surface with a solid color."""
        self.surface.fill(color)

    def draw_placeholder_text(
        self,
        text: str,
        color: tuple[int, int, int] = PLACEHOLDER_TEXT_COLOR,
        center: Optional[tuple[int, int]] = None,
    ) -> None:
        """Draw simple centered text. A stand-in until `typography.py`
        (a later phase) provides themed, styled text rendering.

        `center` defaults to the middle of the window; pass an explicit
        point to stack multiple lines without overlapping.
        """
        if self._font is None:
            return
        rendered = self._font.render(text, True, color)
        target_center = center if center is not None else (self.width // 2, self.height // 2)
        rect = rendered.get_rect(center=target_center)
        self.surface.blit(rendered, rect)

    def present(self) -> None:
        """Flip the back buffer to the screen."""
        pygame.display.flip()

    def close(self) -> None:
        """Tear down the window. Safe to call multiple times."""
        if self._is_open:
            pygame.display.quit()
        self._surface = None
        self._font = None
        self._is_open = False

    def __enter__(self) -> "Renderer":
        self.open()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
