"""The gesture tutorial screen: a visible explanation of every core
gesture, reachable from the hub before a player's first game.

Purely informational — the five gesture cards aren't interactive, only
the Back button is, keeping this screen as simple as what it actually
needs to do (per Engineering Rule #1: prefer the simplest robust
approach) rather than building a menu out of things that aren't choices.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pygame

from visionarcade.constants import GAME_CARD_GAP, GAME_CARD_HEIGHT, GAME_CARD_WIDTH
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.navigation import FocusGroup, SelectableItem

Point = Tuple[float, float]

_BACK_BUTTON_WIDTH = 180
_BACK_BUTTON_HEIGHT = 56

#: (display name, icon kind, one-line description) for each core gesture.
_GESTURES: Tuple[Tuple[str, str, str], ...] = (
    ("Move / Point", "point", "Move your hand to control the pointer or reticle."),
    ("Pinch", "pinch", "Touch thumb and index finger together to select, grab, or activate."),
    ("Open Palm", "open_palm", "Spread your fingers wide — used during calibration and some games."),
    ("Fist", "fist", "Close your hand — used during calibration and some games."),
    ("Swipe", "swipe", "Move your hand quickly left or right — slices targets and can navigate."),
)


class TutorialScreen:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._focus = FocusGroup()
        self._card_top = 150
        self._layout()

    def _layout(self) -> None:
        total_width = len(_GESTURES) * GAME_CARD_WIDTH + (len(_GESTURES) - 1) * GAME_CARD_GAP
        self._cards_left = max(20, (self.width - total_width) // 2)

        back_rect = pygame.Rect(
            (self.width - _BACK_BUTTON_WIDTH) // 2,
            self._card_top + GAME_CARD_HEIGHT + 40,
            _BACK_BUTTON_WIDTH,
            _BACK_BUTTON_HEIGHT,
        )
        self._focus.set_items([SelectableItem(item_id="back", rect=back_rect)])
        self._back_rect = back_rect

    def on_enter(self) -> None:
        pass  # nothing stateful to reset

    def update(
        self, dt: float, pointer: Optional[Point], confirm: bool, key_events: List[int]
    ) -> Optional[str]:
        self._focus.update_pointer(pointer)
        result: Optional[str] = None
        for key in key_events:
            if key == pygame.K_ESCAPE:
                result = "back"
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
        surface.fill(theme.background)
        typography.render(surface, "Gestures", "title", theme.text_primary, center=(self.width // 2, 50))
        typography.render(
            surface,
            "The core gestures used throughout VisionArcade",
            "small",
            theme.text_secondary,
            center=(self.width // 2, 88),
        )

        for index, (name, icon, description) in enumerate(_GESTURES):
            x = self._cards_left + index * (GAME_CARD_WIDTH + GAME_CARD_GAP)
            rect = pygame.Rect(x, self._card_top, GAME_CARD_WIDTH, GAME_CARD_HEIGHT)
            self._draw_gesture_card(surface, typography, theme, rect, name, icon, description)

        focused = self._focus.focused_id == "back"
        color = theme.surface_focused if focused else theme.surface
        pygame.draw.rect(surface, color, self._back_rect, border_radius=10)
        if focused:
            pygame.draw.rect(surface, theme.accent, self._back_rect, width=2, border_radius=10)
        typography.render(surface, "Back", "body", theme.text_primary, center=self._back_rect.center)

    def _draw_gesture_card(self, surface, typography, theme, rect, name, icon, description) -> None:
        pygame.draw.rect(surface, theme.surface, rect, border_radius=14)
        pygame.draw.rect(surface, theme.border, rect, width=2, border_radius=14)
        icon_center = (rect.centerx, rect.y + 60)
        _draw_gesture_icon(surface, icon, icon_center, theme)
        typography.render(surface, name, "body", theme.text_primary, center=(rect.centerx, rect.y + 110))
        typography.render_wrapped(
            surface, description, "small", theme.text_secondary, rect, top=rect.y + 140
        )


def _draw_gesture_icon(surface: pygame.Surface, kind: str, center: Tuple[int, int], theme: Theme) -> None:
    cx, cy = center
    color = theme.accent

    if kind == "point":
        pygame.draw.circle(surface, color, center, 22, width=3)
        pygame.draw.circle(surface, color, center, 5)
    elif kind == "pinch":
        left, right = (cx - 10, cy - 8), (cx + 10, cy - 8)
        pygame.draw.line(surface, color, left, right, 2)
        pygame.draw.circle(surface, color, left, 8)
        pygame.draw.circle(surface, color, right, 8)
        pygame.draw.circle(surface, theme.text_primary, center, 3)
    elif kind == "open_palm":
        pygame.draw.circle(surface, color, center, 14)
        for angle_deg in (-60, -30, 0, 30, 60):
            angle = math.radians(angle_deg - 90)
            end = (cx + 30 * math.cos(angle), cy + 30 * math.sin(angle))
            pygame.draw.line(surface, color, center, end, 4)
    elif kind == "fist":
        pygame.draw.circle(surface, color, center, 20)
    elif kind == "swipe":
        pygame.draw.line(surface, color, (cx - 28, cy), (cx + 18, cy), 4)
        pygame.draw.polygon(surface, color, [(cx + 18, cy - 10), (cx + 18, cy + 10), (cx + 32, cy)])
        for i, dx in enumerate((-40, -50, -60)):
            radius = max(1, 3 - i)
            pygame.draw.circle(surface, theme.text_secondary, (cx + dx, cy), radius)
