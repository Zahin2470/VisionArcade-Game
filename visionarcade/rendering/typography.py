"""Cached, sized text rendering.

Every screen asks for text by a named size ("title", "heading", "body",
"small") instead of picking a raw pixel size, so the whole app's type
scale stays consistent and changes in one place.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pygame

Color = Tuple[int, int, int]

#: Named type scale, in pixels. A later phase can swap `pygame.font.SysFont`
#: for a bundled custom font file without changing any call site.
_SIZES: Dict[str, int] = {
    "title": 48,
    "heading": 32,
    "body": 22,
    "small": 16,
}


class Typography:
    """Loads and caches one `pygame.font.Font` per named size."""

    def __init__(self) -> None:
        self._fonts: Dict[str, pygame.font.Font] = {}

    def _font(self, size_name: str) -> pygame.font.Font:
        if size_name not in self._fonts:
            if not pygame.font.get_init():
                pygame.font.init()
            pixel_size = _SIZES.get(size_name, _SIZES["body"])
            self._fonts[size_name] = pygame.font.SysFont(None, pixel_size)
        return self._fonts[size_name]

    def render(
        self,
        surface: pygame.Surface,
        text: str,
        size_name: str,
        color: Color,
        center: Optional[Tuple[int, int]] = None,
        topleft: Optional[Tuple[int, int]] = None,
    ) -> pygame.Rect:
        """Render `text` onto `surface`, positioned by `center` or
        `topleft` (defaults to the surface's center). Returns the
        drawn rect, so callers can lay out further content relative
        to it."""
        font = self._font(size_name)
        rendered = font.render(text, True, color)
        if topleft is not None:
            rect = rendered.get_rect(topleft=topleft)
        else:
            target_center = center if center is not None else surface.get_rect().center
            rect = rendered.get_rect(center=target_center)
        surface.blit(rendered, rect)
        return rect

    def measure(self, text: str, size_name: str) -> Tuple[int, int]:
        """The (width, height) `text` would occupy at `size_name`,
        without drawing it — useful for layout."""
        return self._font(size_name).size(text)

    def render_wrapped(
        self,
        surface: pygame.Surface,
        text: str,
        size_name: str,
        color: Color,
        rect: "pygame.Rect",
        top: int,
        line_height: int = 20,
    ) -> None:
        """Word-wrap `text` to fit within `rect`'s width (minus a small
        margin) and render it centered horizontally, starting at `top`.
        Shared by any screen that needs to fit a description into a
        fixed-width card rather than reimplementing wrapping."""
        max_width = rect.width - 24
        words = text.split(" ")
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if self.measure(candidate, size_name)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        y = top
        for line in lines:
            self.render(surface, line, size_name, color, center=(rect.centerx, y))
            y += line_height

    def clear_cache(self) -> None:
        self._fonts.clear()
