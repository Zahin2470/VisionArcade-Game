"""The settings screen: theme, audio, camera, and accessibility.

Rows are navigated vertically (Up/Down, or pointer hover); Left/Right
fine-adjusts a focused slider/cycles a focused option from the
keyboard, while a touchless pinch ("confirm") steps the focused row
forward by one increment — coarser, but usable without a keyboard,
per "the game must remain usable when [interaction] is imperfect".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import pygame

from visionarcade.constants import THEMES
from visionarcade.persistence.settings import Settings
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.navigation import FocusGroup, SelectableItem

Point = Tuple[float, float]

_VOLUME_STEP = 0.1
_SENSITIVITY_STEP = 0.1
_SMOOTHING_STEP = 0.1


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _cycle_theme(settings: Settings, step: int) -> Settings:
    index = THEMES.index(settings.theme) if settings.theme in THEMES else 0
    new_theme = THEMES[(index + step) % len(THEMES)]
    return settings.with_overrides(theme=new_theme)


@dataclass
class SettingsRow:
    """One adjustable/toggleable/actionable row in the settings list."""

    row_id: str
    label: str
    rect: pygame.Rect
    render_value: Callable[[Settings], str]
    on_left: Optional[Callable[[Settings], Settings]] = None
    on_right: Optional[Callable[[Settings], Settings]] = None
    # `on_activate` handles Enter/Space and a touchless pinch alike —
    # for sliders/cycles it behaves the same as `on_right` (step
    # forward), so a pinch can still adjust them, just less precisely.
    on_activate: Optional[Callable[[Settings], Settings]] = None


class SettingsScreen:
    """Lets the player adjust and persist their `Settings`."""

    def __init__(self, width: int, height: int, settings: Settings) -> None:
        self.width = width
        self.height = height
        self.settings = settings
        self._focus = FocusGroup()
        self._layout()

    def load(self, settings: Settings) -> None:
        """Refresh the working copy shown, e.g. when re-entering the screen."""
        self.settings = settings

    def on_enter(self, settings: Settings) -> None:
        self.load(settings)

    def _layout(self) -> None:
        row_height = 48
        row_width = min(560, self.width - 80)
        top = 90
        gap = 8
        x = (self.width - row_width) // 2

        specs = [
            ("theme", "Theme", lambda s: s.theme.capitalize(), lambda s: _cycle_theme(s, -1), lambda s: _cycle_theme(s, 1)),
            (
                "master_volume",
                "Master Volume",
                lambda s: f"{int(s.master_volume * 100)}%",
                lambda s: s.with_overrides(master_volume=s.master_volume - _VOLUME_STEP),
                lambda s: s.with_overrides(master_volume=s.master_volume + _VOLUME_STEP),
            ),
            (
                "sfx_volume",
                "SFX Volume",
                lambda s: f"{int(s.sfx_volume * 100)}%",
                lambda s: s.with_overrides(sfx_volume=s.sfx_volume - _VOLUME_STEP),
                lambda s: s.with_overrides(sfx_volume=s.sfx_volume + _VOLUME_STEP),
            ),
            (
                "music_volume",
                "Music Volume",
                lambda s: f"{int(s.music_volume * 100)}%",
                lambda s: s.with_overrides(music_volume=s.music_volume - _VOLUME_STEP),
                lambda s: s.with_overrides(music_volume=s.music_volume + _VOLUME_STEP),
            ),
            (
                "muted",
                "Mute",
                lambda s: "On" if s.muted else "Off",
                None,
                None,
            ),
            (
                "camera_mirror",
                "Mirror Camera",
                lambda s: "On" if s.camera_mirror else "Off",
                None,
                None,
            ),
            (
                "sensitivity",
                "Gesture Sensitivity",
                lambda s: f"{s.sensitivity:.1f}x",
                lambda s: s.with_overrides(sensitivity=s.sensitivity - _SENSITIVITY_STEP),
                lambda s: s.with_overrides(sensitivity=s.sensitivity + _SENSITIVITY_STEP),
            ),
            (
                "smoothing_multiplier",
                "Smoothing",
                lambda s: f"{s.smoothing_multiplier:.1f}x",
                lambda s: s.with_overrides(smoothing_multiplier=s.smoothing_multiplier - _SMOOTHING_STEP),
                lambda s: s.with_overrides(smoothing_multiplier=s.smoothing_multiplier + _SMOOTHING_STEP),
            ),
            (
                "high_contrast",
                "High Contrast",
                lambda s: "On" if s.high_contrast else "Off",
                None,
                None,
            ),
            (
                "reduced_particles",
                "Reduced Particles",
                lambda s: "On" if s.reduced_particles else "Off",
                None,
                None,
            ),
        ]

        self._rows: List[SettingsRow] = []
        items: List[SelectableItem] = []
        for index, (row_id, label, render_value, on_left, on_right) in enumerate(specs):
            rect = pygame.Rect(x, top + index * (row_height + gap), row_width, row_height)
            is_toggle = on_left is None and on_right is None
            on_activate = _make_toggle(row_id) if is_toggle else on_right
            row = SettingsRow(
                row_id=row_id,
                label=label,
                rect=rect,
                render_value=render_value,
                on_left=on_left,
                on_right=on_right,
                on_activate=on_activate,
            )
            self._rows.append(row)
            items.append(SelectableItem(item_id=row_id, rect=rect))

        reset_rect = pygame.Rect(x, top + len(specs) * (row_height + gap) + 12, 220, row_height)
        back_rect = pygame.Rect(x + row_width - 140, reset_rect.y, 140, row_height)
        items.append(SelectableItem(item_id="reset_scores", rect=reset_rect))
        items.append(SelectableItem(item_id="back", rect=back_rect))
        self._reset_rect = reset_rect
        self._back_rect = back_rect

        self._focus.set_items(items)

    def _row(self, row_id: str) -> Optional[SettingsRow]:
        for row in self._rows:
            if row.row_id == row_id:
                return row
        return None

    def update(
        self,
        dt: float,
        pointer: Optional[Point],
        confirm: bool,
        key_events: List[int],
    ) -> Optional[str]:
        """Advance one frame. Returns "back" once the player leaves the
        screen, "reset_scores" once requested (the caller performs the
        actual reset), else None."""
        self._focus.update_pointer(pointer)
        focused_id = self._focus.focused_id

        result: Optional[str] = None
        for key in key_events:
            if key in (pygame.K_UP,):
                self._focus.move_focus(-1)
            elif key in (pygame.K_DOWN, pygame.K_TAB):
                self._focus.move_focus(1)
            elif key == pygame.K_LEFT:
                self._apply(focused_id, "left")
            elif key == pygame.K_RIGHT:
                self._apply(focused_id, "right")
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                result = self._activate(focused_id) or result
            elif key == pygame.K_ESCAPE:
                result = "back"

        if confirm:
            result = self._activate(focused_id) or result

        return result

    def _apply(self, row_id: Optional[str], direction: str) -> None:
        row = self._row(row_id) if row_id else None
        if row is None:
            return
        fn = row.on_left if direction == "left" else row.on_right
        if fn is not None:
            self.settings = fn(self.settings).clamped()

    def _activate(self, row_id: Optional[str]) -> Optional[str]:
        if row_id is None:
            return None
        if row_id == "back":
            return "back"
        if row_id == "reset_scores":
            return "reset_scores"
        row = self._row(row_id)
        if row is not None and row.on_activate is not None:
            self.settings = row.on_activate(self.settings).clamped()
        return None

    def draw(self, surface: pygame.Surface, typography: Typography, theme: Theme) -> None:
        surface.fill(theme.background)
        typography.render(
            surface, "Settings", "title", theme.text_primary, center=(self.width // 2, 48)
        )

        for row in self._rows:
            focused = row.row_id == self._focus.focused_id
            self._draw_row(surface, typography, theme, row, focused)

        self._draw_action_button(surface, typography, theme, "reset_scores", "Reset Scores", self._reset_rect)
        self._draw_action_button(surface, typography, theme, "back", "Back", self._back_rect)

    def _draw_row(self, surface, typography, theme, row: SettingsRow, focused: bool) -> None:
        color = theme.surface_focused if focused else theme.surface
        pygame.draw.rect(surface, color, row.rect, border_radius=10)
        if focused:
            pygame.draw.rect(surface, theme.accent, row.rect, width=2, border_radius=10)

        typography.render(
            surface,
            row.label,
            "body",
            theme.text_primary,
            topleft=(row.rect.x + 16, row.rect.y + row.rect.height // 2 - 10),
        )
        typography.render(
            surface,
            row.render_value(self.settings),
            "body",
            theme.accent,
            topleft=(row.rect.right - 100, row.rect.y + row.rect.height // 2 - 10),
        )

    def _draw_action_button(self, surface, typography, theme, item_id, label, rect) -> None:
        focused = item_id == self._focus.focused_id
        color = theme.surface_focused if focused else theme.surface
        pygame.draw.rect(surface, color, rect, border_radius=10)
        if focused:
            pygame.draw.rect(surface, theme.accent, rect, width=2, border_radius=10)
        typography.render(surface, label, "body", theme.text_primary, center=rect.center)


def _make_toggle(row_id: str) -> Callable[[Settings], Settings]:
    def _toggle(settings: Settings) -> Settings:
        current = getattr(settings, row_id)
        return settings.with_overrides(**{row_id: not current})

    return _toggle
