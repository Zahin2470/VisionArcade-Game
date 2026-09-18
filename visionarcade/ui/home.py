"""The arcade hub / home screen.

Shows a game card per known mini-game (best score, difficulty, a
one-line description) plus Settings/Calibrate/Quit — navigable by
keyboard (accessibility/testing fallback) or by pointing with a
fingertip and pinching, via the shared `FocusGroup`/`SelectableItem`
primitives.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from visionarcade.config import KNOWN_GAMES
from visionarcade.constants import FOCUS_BORDER_WIDTH, GAME_CARD_GAP, GAME_CARD_HEIGHT, GAME_CARD_WIDTH, GAME_METADATA
from visionarcade.persistence.profiles import PlayerProfile
from visionarcade.persistence.scores import ScoresStore
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.navigation import FocusGroup, SelectableItem

Point = Tuple[float, float]

_ACTION_LABELS = {"settings": "Settings", "calibration": "Calibrate", "quit": "Quit"}


class HomeScreen:
    """The console-style home hub: game cards plus hub-level actions."""

    def __init__(self, width: int, height: int, scores: ScoresStore, profile: PlayerProfile) -> None:
        self.width = width
        self.height = height
        self.scores = scores
        self.profile = profile
        self._focus = FocusGroup()
        self._game_ids: List[str] = list(KNOWN_GAMES)
        self._card_top = 170
        self._button_height = 56
        self._layout()

    def refresh(self, scores: ScoresStore, profile: PlayerProfile) -> None:
        """Update the data shown (e.g. after a score is recorded or a
        settings change), without disturbing current focus."""
        self.scores = scores
        self.profile = profile

    def on_enter(self) -> None:
        pass  # nothing stateful needs resetting when returning to the hub

    def _layout(self) -> None:
        items: List[SelectableItem] = []

        total_cards_width = len(self._game_ids) * GAME_CARD_WIDTH + (
            len(self._game_ids) - 1
        ) * GAME_CARD_GAP
        start_x = max(20, (self.width - total_cards_width) // 2)
        for index, game_id in enumerate(self._game_ids):
            x = start_x + index * (GAME_CARD_WIDTH + GAME_CARD_GAP)
            rect = pygame.Rect(x, self._card_top, GAME_CARD_WIDTH, GAME_CARD_HEIGHT)
            items.append(SelectableItem(item_id=f"play:{game_id}", rect=rect))

        button_width, button_gap = 180, 24
        button_ids = ("settings", "calibration", "quit")
        total_buttons_width = len(button_ids) * button_width + (len(button_ids) - 1) * button_gap
        button_start_x = max(20, (self.width - total_buttons_width) // 2)
        self._button_top = self._card_top + GAME_CARD_HEIGHT + 50
        for index, action_id in enumerate(button_ids):
            x = button_start_x + index * (button_width + button_gap)
            rect = pygame.Rect(x, self._button_top, button_width, self._button_height)
            items.append(SelectableItem(item_id=action_id, rect=rect))

        self._focus.set_items(items)

    def update(
        self,
        dt: float,
        pointer: Optional[Point],
        confirm: bool,
        key_events: List[int],
    ) -> Optional[str]:
        """Advance one frame. Returns an action id ("quit", "settings",
        "calibration", or "play:<game_id>") once something is
        activated, else None."""
        self._focus.update_pointer(pointer)

        activated: Optional[str] = None
        for key in key_events:
            result = self._focus.handle_key(key)
            if result is not None:
                activated = result
        if confirm:
            result = self._focus.activate_focused()
            if result is not None:
                activated = result

        return activated

    def draw(self, surface: pygame.Surface, typography: Typography, theme: Theme) -> None:
        surface.fill(theme.background)
        typography.render(
            surface, "VisionArcade", "title", theme.text_primary, center=(self.width // 2, 56)
        )
        typography.render(
            surface,
            f"Welcome, {self.profile.display_name}",
            "body",
            theme.text_secondary,
            center=(self.width // 2, 100),
        )

        for item in self._focus.items:
            focused = item.item_id == self._focus.focused_id
            self._draw_item(surface, typography, theme, item, focused)

    def _draw_item(self, surface, typography, theme, item: SelectableItem, focused: bool) -> None:
        color = theme.surface_focused if focused else theme.surface
        pygame.draw.rect(surface, color, item.rect, border_radius=14)
        if focused:
            pygame.draw.rect(
                surface, theme.accent, item.rect, width=FOCUS_BORDER_WIDTH, border_radius=14
            )

        if item.item_id.startswith("play:"):
            self._draw_game_card(surface, typography, theme, item)
        else:
            label = _ACTION_LABELS.get(item.item_id, item.item_id)
            typography.render(surface, label, "body", theme.text_primary, center=item.rect.center)

    def _draw_game_card(self, surface, typography, theme, item: SelectableItem) -> None:
        game_id = item.item_id.split(":", 1)[1]
        meta = GAME_METADATA.get(game_id, {})
        title = meta.get("title", game_id)
        description = meta.get("description", "")
        difficulty = meta.get("difficulty", "-")
        best = self.scores.best_score(game_id)
        best_text = f"Best: {best}" if best is not None else "Best: -"

        typography.render(
            surface, title, "heading", theme.text_primary, center=(item.rect.centerx, item.rect.y + 36)
        )
        self._draw_wrapped_text(
            surface, typography, description, theme.text_secondary, item.rect, top=item.rect.y + 76
        )
        typography.render(
            surface,
            f"Difficulty: {difficulty}",
            "small",
            theme.text_secondary,
            center=(item.rect.centerx, item.rect.bottom - 46),
        )
        typography.render(
            surface, best_text, "small", theme.accent, center=(item.rect.centerx, item.rect.bottom - 22)
        )

    @staticmethod
    def _draw_wrapped_text(surface, typography, text, color, rect, top, line_height=20):
        max_width = rect.width - 24
        words = text.split(" ")
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if typography.measure(candidate, "small")[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        y = top
        for line in lines:
            typography.render(surface, line, "small", color, center=(rect.centerx, y))
            y += line_height
