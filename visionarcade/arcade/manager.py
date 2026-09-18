"""The arcade shell controller.

Owns the current screen, `Settings`/`ScoresStore`/`PlayerProfile`, the
audio manager, and calibration data, and dispatches each frame's
`FrameIntent` (plus raw hand results, for calibration) and keyboard
events to whichever screen is active. This is what makes adding a real
game later a matter of registering it here, not rewriting navigation,
audio, or persistence.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import pygame

from visionarcade.arcade.state import ArcadeState
from visionarcade.audio.effects import SoundEffects
from visionarcade.audio.manager import AudioManager
from visionarcade.constants import GAME_METADATA
from visionarcade.persistence.profiles import PlayerProfile, save_profile
from visionarcade.persistence.scores import ScoresStore, save_scores
from visionarcade.persistence.settings import Settings, save_settings
from visionarcade.rendering.themes import Theme, get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.calibration import CalibrationScreen
from visionarcade.ui.home import HomeScreen
from visionarcade.ui.settings import SettingsScreen
from visionarcade.vision.calibration import CalibrationData, save_calibration
from visionarcade.vision.gestures import FrameIntent, PinchState
from visionarcade.vision.landmarks import HandResult

logger = logging.getLogger(__name__)

Point = Tuple[float, float]


def _pick_primary_raw_hand(hand_results: List[HandResult]) -> Optional[HandResult]:
    """Prefer the right hand, falling back to the left, matching
    `FrameIntent.primary()`'s convention elsewhere in the pipeline."""
    by_hand: Dict[str, HandResult] = {h.handedness: h for h in hand_results}
    return by_hand.get("Right") or by_hand.get("Left")


class ArcadeManager:
    """The arcade shell: home hub, settings, calibration, and (once a
    game is selected) a placeholder screen until Phase 4+ implements
    real games behind the same `ArcadeGame` interface."""

    def __init__(
        self,
        width: int,
        height: int,
        settings: Settings,
        scores: ScoresStore,
        profile: PlayerProfile,
        calibration: CalibrationData,
        audio: Optional[AudioManager] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.settings = settings
        self.scores = scores
        self.profile = profile
        self.calibration = calibration
        self.audio = audio if audio is not None else AudioManager()
        self.sfx = SoundEffects(self.audio)
        self.typography = Typography()

        self.state = ArcadeState.HOME
        self.active_game_id: Optional[str] = None
        self._should_quit = False

        self.home_screen = HomeScreen(width, height, scores, profile)
        self.settings_screen = SettingsScreen(width, height, settings)
        self.calibration_screen = CalibrationScreen(width, height)

        self.audio.apply_settings(
            settings.master_volume, settings.sfx_volume, settings.music_volume, settings.muted
        )

    @property
    def theme(self) -> Theme:
        theme_name = "mono" if self.settings.high_contrast else self.settings.theme
        return get_theme(theme_name)

    @property
    def should_quit(self) -> bool:
        return self._should_quit

    def update(
        self,
        intent: FrameIntent,
        raw_hand_results: List[HandResult],
        key_events: List[int],
        dt: float,
    ) -> None:
        primary = intent.primary()
        pointer: Optional[Point] = None
        if primary.present and primary.index_tip is not None:
            pointer = (primary.index_tip[0] * self.width, primary.index_tip[1] * self.height)
        confirm = primary.pinch_state == PinchState.START

        if self.state == ArcadeState.HOME:
            self._update_home(dt, pointer, confirm, key_events)
        elif self.state == ArcadeState.SETTINGS:
            self._update_settings(dt, pointer, confirm, key_events)
        elif self.state == ArcadeState.CALIBRATION:
            self._update_calibration(dt, raw_hand_results, pointer, confirm, key_events)
        elif self.state == ArcadeState.PLAYING:
            self._update_playing_placeholder(confirm, key_events)

    def _update_home(self, dt, pointer, confirm, key_events) -> None:
        result = self.home_screen.update(dt, pointer, confirm, key_events)
        if result is None:
            return
        if result == "quit":
            self._should_quit = True
        elif result == "settings":
            self.settings_screen.on_enter(self.settings)
            self.state = ArcadeState.SETTINGS
        elif result == "calibration":
            self.calibration_screen.on_enter()
            self.state = ArcadeState.CALIBRATION
        elif result.startswith("play:"):
            self.active_game_id = result.split(":", 1)[1]
            self.state = ArcadeState.PLAYING

    def _update_settings(self, dt, pointer, confirm, key_events) -> None:
        result = self.settings_screen.update(dt, pointer, confirm, key_events)
        if result == "reset_scores":
            self.scores.reset()
            save_scores(self.scores)
        elif result == "back":
            self.settings = self.settings_screen.settings.clamped()
            save_settings(self.settings)
            self.audio.apply_settings(
                self.settings.master_volume,
                self.settings.sfx_volume,
                self.settings.music_volume,
                self.settings.muted,
            )
            self.home_screen.refresh(self.scores, self.profile)
            self.state = ArcadeState.HOME

    def _update_calibration(self, dt, raw_hand_results, pointer, confirm, key_events) -> None:
        primary_raw_hand = _pick_primary_raw_hand(raw_hand_results)
        result = self.calibration_screen.update(dt, primary_raw_hand, pointer, confirm, key_events)
        if result == "home":
            session_result = self.calibration_screen.session.result
            if session_result is not None:
                self.calibration = session_result
                save_calibration(self.calibration)
            self.state = ArcadeState.HOME

    def _update_playing_placeholder(self, confirm: bool, key_events: List[int]) -> None:
        # No real game exists yet (Phase 4+) — any confirm/back input
        # returns to the hub rather than leaving the player stuck.
        if confirm or pygame.K_ESCAPE in key_events or pygame.K_BACKSPACE in key_events:
            self.active_game_id = None
            self.state = ArcadeState.HOME

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        if self.state == ArcadeState.HOME:
            self.home_screen.draw(surface, self.typography, theme)
        elif self.state == ArcadeState.SETTINGS:
            self.settings_screen.draw(surface, self.typography, theme)
        elif self.state == ArcadeState.CALIBRATION:
            self.calibration_screen.draw(surface, self.typography, theme)
        elif self.state == ArcadeState.PLAYING:
            self._draw_playing_placeholder(surface, theme)

    def _draw_playing_placeholder(self, surface: pygame.Surface, theme: Theme) -> None:
        surface.fill(theme.background)
        meta = GAME_METADATA.get(self.active_game_id or "", {})
        title = meta.get("title", self.active_game_id or "Game")
        self.typography.render(
            surface, title, "title", theme.text_primary, center=(self.width // 2, self.height // 2 - 30)
        )
        self.typography.render(
            surface,
            "Coming in a future phase — pinch or press Escape to return to the hub.",
            "body",
            theme.text_secondary,
            center=(self.width // 2, self.height // 2 + 30),
        )

    def shutdown(self) -> None:
        """Persist everything on the way out. Never raises."""
        save_settings(self.settings)
        save_scores(self.scores)
        save_profile(self.profile)
