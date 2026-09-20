"""The first-run calibration screen.

Presents `vision.calibration.CalibrationSession`'s steps visually: a
guide box showing the player's own live camera feed, instruction text,
and a skip affordance — the session logic itself is fully covered by
Phase 2's tests, so this module is purely presentation plus simple
input routing (Escape or the Skip button/pinch).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pygame

from visionarcade.rendering.camera_view import CameraView
from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography
from visionarcade.vision.calibration import CalibrationSession, CalibrationStep
from visionarcade.vision.landmarks import HandResult

Point = Tuple[float, float]

_STEP_PROGRESS = {
    CalibrationStep.PLACE_HAND: 1,
    CalibrationStep.MOVE_RANGE: 2,
    CalibrationStep.PINCH: 3,
    CalibrationStep.OPEN_PALM: 4,
    CalibrationStep.SWIPE: 5,
    CalibrationStep.DONE: 6,
}
_TOTAL_STEPS = 6


class CalibrationScreen:
    """Walks the player through calibration and reports when to leave."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.session = CalibrationSession()
        self._skip_rect = pygame.Rect(width - 170, height - 76, 140, 48)
        guide_size = int(min(width, height) * 0.5)
        self._guide_rect = pygame.Rect(
            width // 2 - guide_size // 2, height // 2 - guide_size // 2, guide_size, guide_size
        )
        self.camera_view = CameraView(self._guide_rect)

    def on_enter(self) -> None:
        """Start a fresh calibration session each time this screen is entered."""
        self.session = CalibrationSession()

    def update(
        self,
        dt: float,
        primary_hand: Optional[HandResult],
        pointer: Optional[Point],
        confirm: bool,
        key_events: List[int],
    ) -> Optional[str]:
        """Advance one frame. Returns "home" once calibration finishes
        or is skipped, else None."""
        for key in key_events:
            if key == pygame.K_ESCAPE:
                self.session.skip()
                return "home"

        if pointer is not None and confirm and self._skip_rect.collidepoint(pointer):
            self.session.skip()
            return "home"

        self.session.update(primary_hand, dt)
        return "home" if self.session.is_done else None

    def draw(
        self,
        surface: pygame.Surface,
        typography: Typography,
        theme: Theme,
        camera_frame: Optional[np.ndarray] = None,
        camera_available: bool = False,
    ) -> None:
        surface.fill(theme.background)

        step_number = _STEP_PROGRESS.get(self.session.step, 1)
        typography.render(
            surface,
            f"Calibration — step {step_number} of {_TOTAL_STEPS}",
            "heading",
            theme.text_primary,
            center=(self.width // 2, 56),
        )
        typography.render(
            surface, self.session.instruction, "body", theme.text_secondary, center=(self.width // 2, 96)
        )

        self.camera_view.draw(
            surface, camera_frame, camera_available=camera_available, theme=theme, typography=typography
        )
        pygame.draw.rect(surface, theme.accent, self._guide_rect, width=3, border_radius=16)

        pygame.draw.rect(surface, theme.surface, self._skip_rect, border_radius=10)
        typography.render(surface, "Skip", "body", theme.text_primary, center=self._skip_rect.center)
