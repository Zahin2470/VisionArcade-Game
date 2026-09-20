"""A generic results screen: final score/stats plus Play Again / Back
to Hub — reusable across every mini-game's `get_results()` output.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pygame

from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.navigation import FocusGroup, SelectableItem

Point = Tuple[float, float]

_BUTTON_WIDTH = 200
_BUTTON_HEIGHT = 56
_BUTTON_GAP = 20
_LABELS = (("play_again", "Play Again"), ("save_share_card", "Save Share Card"), ("back_to_hub", "Back to Hub"))
_MESSAGE_SECONDS = 2.5

_OUTCOME_HEADLINES = {
    "cleared": "Round Complete!",
    "out_of_lives": "Game Over",
    "player_win": "You Win!",
    "player_loss": "You Lose",
    "left_win": "Left Player Wins!",
    "right_win": "Right Player Wins!",
    "too_many_misses": "Sequence Failed",
}


class ResultsScreen:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._focus = FocusGroup()
        self.results: Dict[str, Any] = {}
        self.is_new_best = False
        self._message = ""
        self._message_timer = 0.0
        self._layout()

    def _layout(self) -> None:
        total_width = len(_LABELS) * _BUTTON_WIDTH + (len(_LABELS) - 1) * _BUTTON_GAP
        left = (self.width - total_width) // 2
        top = self.height - 140

        items: List[SelectableItem] = []
        for index, (item_id, _label) in enumerate(_LABELS):
            rect = pygame.Rect(left + index * (_BUTTON_WIDTH + _BUTTON_GAP), top, _BUTTON_WIDTH, _BUTTON_HEIGHT)
            items.append(SelectableItem(item_id=item_id, rect=rect))
        self._focus.set_items(items)

    def on_enter(self, results: Dict[str, Any], is_new_best: bool) -> None:
        self.results = results
        self.is_new_best = is_new_best
        self._message = ""
        self._message_timer = 0.0
        self._focus._focus_index = 0  # noqa: SLF001 - same module family

    def show_message(self, text: str) -> None:
        """Briefly display a status line (e.g. "Share card saved") —
        used after an action that doesn't change screens, like saving
        a share card, so the player still gets confirmation."""
        self._message = text
        self._message_timer = _MESSAGE_SECONDS

    def update(
        self, dt: float, pointer: Optional[Point], confirm: bool, key_events: List[int]
    ) -> Optional[str]:
        self._message_timer = max(0.0, self._message_timer - dt)
        self._focus.update_pointer(pointer)
        result: Optional[str] = None
        for key in key_events:
            if key == pygame.K_ESCAPE:
                result = "back_to_hub"
            else:
                activated = self._focus.handle_key(key)
                if activated is not None:
                    result = activated
        if confirm:
            activated = self._focus.activate_focused()
            if activated is not None:
                result = activated
        return result

    def draw(self, surface: pygame.Surface, typography: Typography, theme: Theme, game_title: str = "") -> None:
        surface.fill(theme.background)

        outcome = self.results.get("outcome", "")
        headline = _OUTCOME_HEADLINES.get(outcome, "Results")
        typography.render(surface, headline, "title", theme.text_primary, center=(self.width // 2, 100))
        if game_title:
            typography.render(
                surface, game_title, "body", theme.text_secondary, center=(self.width // 2, 148)
            )

        typography.render(
            surface,
            f"Score: {self.results.get('score', 0)}",
            "heading",
            theme.accent,
            center=(self.width // 2, 220),
        )

        y = 262
        if self.is_new_best:
            typography.render(surface, "New Best Score!", "body", theme.success, center=(self.width // 2, y))
            y += 32

        best_streak = self.results.get("best_streak")
        if best_streak is not None:
            typography.render(
                surface,
                f"Best Streak: {best_streak}",
                "body",
                theme.text_secondary,
                center=(self.width // 2, y),
            )

        for item in self._focus.items:
            focused = item.item_id == self._focus.focused_id
            color = theme.surface_focused if focused else theme.surface
            pygame.draw.rect(surface, color, item.rect, border_radius=12)
            if focused:
                pygame.draw.rect(surface, theme.accent, item.rect, width=2, border_radius=12)
            label = dict(_LABELS)[item.item_id]
            typography.render(surface, label, "body", theme.text_primary, center=item.rect.center)

        if self._message_timer > 0 and self._message:
            button_top = self._focus.items[0].rect.top if self._focus.items else self.height - 140
            typography.render(
                surface, self._message, "small", theme.success, center=(self.width // 2, button_top - 24)
            )
