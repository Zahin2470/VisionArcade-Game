"""A generic pause overlay: Resume / Restart / Quit to Hub.

Pausing is a shell-level concern (freezing whatever game is active),
not something each mini-game reimplements — this screen is reusable
across every one of them.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.navigation import FocusGroup, SelectableItem

Point = Tuple[float, float]

_BUTTON_WIDTH = 240
_BUTTON_HEIGHT = 56
_BUTTON_GAP = 20
_LABELS = (("resume", "Resume"), ("restart", "Restart"), ("quit_to_hub", "Quit to Hub"))


class PauseScreen:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._focus = FocusGroup()
        self._layout()

    def _layout(self) -> None:
        total_height = len(_LABELS) * _BUTTON_HEIGHT + (len(_LABELS) - 1) * _BUTTON_GAP
        top = (self.height - total_height) // 2
        left = (self.width - _BUTTON_WIDTH) // 2

        items: List[SelectableItem] = []
        for index, (item_id, _label) in enumerate(_LABELS):
            rect = pygame.Rect(left, top + index * (_BUTTON_HEIGHT + _BUTTON_GAP), _BUTTON_WIDTH, _BUTTON_HEIGHT)
            items.append(SelectableItem(item_id=item_id, rect=rect))
        self._top = top
        self._focus.set_items(items)

    def on_enter(self) -> None:
        self._focus.set_items(self._focus.items)
        # Always resume-focused on entry, regardless of prior state.
        for index, item in enumerate(self._focus.items):
            if item.item_id == "resume":
                self._focus._focus_index = index  # noqa: SLF001 - same module family
                break

    def update(
        self, dt: float, pointer: Optional[Point], confirm: bool, key_events: List[int]
    ) -> Optional[str]:
        self._focus.update_pointer(pointer)
        result: Optional[str] = None
        for key in key_events:
            if key == pygame.K_ESCAPE:
                result = "resume"
            else:
                activated = self._focus.handle_key(key)
                if activated is not None:
                    result = activated
        if confirm:
            activated = self._focus.activate_focused()
            if activated is not None:
                result = activated
        return result

    def draw(self, surface: pygame.Surface, typography: Typography, theme: Theme) -> None:
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        typography.render(
            surface, "Paused", "title", theme.text_primary, center=(self.width // 2, self._top - 60)
        )

        for item in self._focus.items:
            focused = item.item_id == self._focus.focused_id
            color = theme.surface_focused if focused else theme.surface
            pygame.draw.rect(surface, color, item.rect, border_radius=12)
            if focused:
                pygame.draw.rect(surface, theme.accent, item.rect, width=2, border_radius=12)
            label = dict(_LABELS)[item.item_id]
            typography.render(surface, label, "body", theme.text_primary, center=item.rect.center)
