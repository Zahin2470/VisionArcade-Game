"""A reusable focus/selection primitive for menu screens.

Every menu screen (home, settings, calibration) needs the same three
things: a list of selectable items, a way to move focus between them
via keyboard OR a touchless pointer, and a way to "activate" whichever
item is focused. Implementing that once here means each screen only
supplies its own items and draws its own visuals — it doesn't
reimplement navigation, satisfying "Allow game selection through
keyboard for accessibility/testing" and touchless menu navigation with
one shared code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

Point = Tuple[float, float]


@dataclass
class SelectableItem:
    """One focusable/activatable menu entry."""

    item_id: str
    rect: pygame.Rect
    enabled: bool = True


class FocusGroup:
    """Manages focus across a linear list of `SelectableItem`s.

    Supports two independent ways of moving focus, either of which can
    drive the same menu: keyboard arrow keys + Enter/Space (the
    accessibility/testing fallback the spec calls for), and a
    touchless pointer position + a "confirm" pulse (e.g. a pinch
    START), which a screen feeds in from a `HandIntent`.
    """

    def __init__(self, items: Optional[List[SelectableItem]] = None) -> None:
        self._items: List[SelectableItem] = []
        self._focus_index: Optional[int] = None
        self.set_items(items or [])

    def set_items(self, items: List[SelectableItem]) -> None:
        self._items = items
        if not items:
            self._focus_index = None
            return
        if self._focus_index is None or self._focus_index >= len(items):
            self._focus_index = self._first_enabled_index()

    def _first_enabled_index(self) -> Optional[int]:
        for index, item in enumerate(self._items):
            if item.enabled:
                return index
        return None

    @property
    def items(self) -> List[SelectableItem]:
        return self._items

    @property
    def focus_index(self) -> Optional[int]:
        return self._focus_index

    @property
    def focused_id(self) -> Optional[str]:
        if self._focus_index is None:
            return None
        return self._items[self._focus_index].item_id

    def move_focus(self, step: int) -> None:
        """Move focus by `step` positions (e.g. -1 for left/up, +1 for
        right/down), skipping disabled items and wrapping around."""
        if not self._items:
            return
        if self._focus_index is None:
            self._focus_index = self._first_enabled_index()
            return

        count = len(self._items)
        index = self._focus_index
        for _ in range(count):
            index = (index + step) % count
            if self._items[index].enabled:
                self._focus_index = index
                return
        # No other enabled item found; keep the current focus.

    def handle_key(self, key: int) -> Optional[str]:
        """Feed one keydown event. Returns an activated item's id, or
        None if the key only moved focus (or did nothing)."""
        if key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
            self.move_focus(1)
        elif key in (pygame.K_LEFT, pygame.K_UP):
            self.move_focus(-1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            return self.activate_focused()
        return None

    def update_pointer(self, point: Optional[Point]) -> None:
        """Move focus to whichever item contains `point` (in the same
        pixel space as each item's `rect`), if any. `point` is
        typically a hand's index-fingertip position mapped to screen
        coordinates; passing None (no hand) leaves focus unchanged."""
        if point is None:
            return
        x, y = point
        for index, item in enumerate(self._items):
            if item.enabled and item.rect.collidepoint(x, y):
                self._focus_index = index
                return

    def activate_focused(self) -> Optional[str]:
        """Return the focused item's id if it's enabled, else None."""
        if self._focus_index is None:
            return None
        item = self._items[self._focus_index]
        return item.item_id if item.enabled else None
