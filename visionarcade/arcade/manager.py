"""The arcade shell controller.

Owns the current screen, `Settings`/`ScoresStore`/`PlayerProfile`, the
audio manager, and calibration data, and dispatches each frame's
`FrameIntent` (plus raw hand results, for calibration) and keyboard
events to whichever screen is active.

Adding a mini-game is a matter of implementing `ArcadeGame` and adding
one entry to `GAME_FACTORIES` — everything else (pause, results,
scoring persistence, navigation) is already handled here, generically,
for every game.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Tuple

import pygame

from visionarcade.arcade.game import ArcadeGame
from visionarcade.arcade.games.catch import CatchGame
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
from visionarcade.ui.pause import PauseScreen
from visionarcade.ui.results import ResultsScreen
from visionarcade.ui.settings import SettingsScreen
from visionarcade.vision.calibration import CalibrationData, save_calibration
from visionarcade.vision.gestures import FrameIntent, PinchState
from visionarcade.vision.landmarks import HandResult

logger = logging.getLogger(__name__)

Point = Tuple[float, float]

#: Maps a game id to a factory building a fresh `ArcadeGame` instance.
#: Games without an entry here fall back to a "coming soon" placeholder
#: — this is the one line Phases 5-8 each add to register their game.
GameFactory = Callable[[int, int, Theme, Typography], ArcadeGame]
GAME_FACTORIES: Dict[str, GameFactory] = {
    "catch": lambda w, h, theme, typography: CatchGame(w, h, theme, typography),
}


def _pick_primary_raw_hand(hand_results: List[HandResult]) -> Optional[HandResult]:
    """Prefer the right hand, falling back to the left, matching
    `FrameIntent.primary()`'s convention elsewhere in the pipeline."""
    by_hand: Dict[str, HandResult] = {h.handedness: h for h in hand_results}
    return by_hand.get("Right") or by_hand.get("Left")


class ArcadeManager:
    """The arcade shell: home hub, settings, calibration, gameplay
    (for registered games), pause, and results."""

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
        self.active_game: Optional[ArcadeGame] = None
        self._should_quit = False

        self.home_screen = HomeScreen(width, height, scores, profile)
        self.settings_screen = SettingsScreen(width, height, settings)
        self.calibration_screen = CalibrationScreen(width, height)
        self.pause_screen = PauseScreen(width, height)
        self.results_screen = ResultsScreen(width, height)

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
            self._update_playing(dt, intent, confirm, key_events)
        elif self.state == ArcadeState.PAUSED:
            self._update_paused(dt, pointer, confirm, key_events)
        elif self.state == ArcadeState.RESULTS:
            self._update_results(dt, pointer, confirm, key_events)

    # --- Home --------------------------------------------------------------

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
            self._start_game(result.split(":", 1)[1])

    def _start_game(self, game_id: str) -> None:
        self.active_game_id = game_id
        self.active_game = self._instantiate_game(game_id)
        self.state = ArcadeState.PLAYING

    def _instantiate_game(self, game_id: Optional[str]) -> Optional[ArcadeGame]:
        factory = GAME_FACTORIES.get(game_id or "")
        if factory is None:
            return None
        return factory(self.width, self.height, self.theme, self.typography)

    def _active_game_title(self) -> str:
        if self.active_game is not None:
            return self.active_game.title
        meta = GAME_METADATA.get(self.active_game_id or "", {})
        return meta.get("title", self.active_game_id or "Game")

    # --- Settings ------------------------------------------------------------

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

    # --- Calibration ---------------------------------------------------------

    def _update_calibration(self, dt, raw_hand_results, pointer, confirm, key_events) -> None:
        primary_raw_hand = _pick_primary_raw_hand(raw_hand_results)
        result = self.calibration_screen.update(dt, primary_raw_hand, pointer, confirm, key_events)
        if result == "home":
            session_result = self.calibration_screen.session.result
            if session_result is not None:
                self.calibration = session_result
                save_calibration(self.calibration)
            self.state = ArcadeState.HOME

    # --- Playing / Pause / Results --------------------------------------------

    def _update_playing(self, dt, intent, confirm, key_events) -> None:
        if self.active_game is None:
            self._update_playing_placeholder(confirm, key_events)
            return

        if any(key in (pygame.K_ESCAPE, pygame.K_p) for key in key_events):
            self.pause_screen.on_enter()
            self.state = ArcadeState.PAUSED
            return

        self.active_game.handle_intent(intent)
        self.active_game.update(dt)
        if self.active_game.is_finished():
            self._enter_results()

    def _update_playing_placeholder(self, confirm: bool, key_events: List[int]) -> None:
        # No real game exists yet for this id — any confirm/back input
        # returns to the hub rather than leaving the player stuck.
        if confirm or pygame.K_ESCAPE in key_events or pygame.K_BACKSPACE in key_events:
            self.active_game_id = None
            self.state = ArcadeState.HOME

    def _update_paused(self, dt, pointer, confirm, key_events) -> None:
        result = self.pause_screen.update(dt, pointer, confirm, key_events)
        if result == "resume":
            self.state = ArcadeState.PLAYING
        elif result == "restart":
            self.active_game = self._instantiate_game(self.active_game_id)
            self.state = ArcadeState.PLAYING
        elif result == "quit_to_hub":
            self._record_current_game_progress()
            self.active_game = None
            self.active_game_id = None
            self.home_screen.refresh(self.scores, self.profile)
            self.state = ArcadeState.HOME

    def _enter_results(self) -> None:
        results = self.active_game.get_results()
        game_id = results.get("game_id", self.active_game_id)
        previous_best = self.scores.best_score(game_id)
        score = results.get("score", 0)

        self.scores.record_score(game_id, score)
        save_scores(self.scores)
        self.profile = self.profile.record_game_played(game_id)
        save_profile(self.profile)

        is_new_best = previous_best is None or score > previous_best
        self.results_screen.on_enter(results, is_new_best)
        self.home_screen.refresh(self.scores, self.profile)
        self.state = ArcadeState.RESULTS

    def _update_results(self, dt, pointer, confirm, key_events) -> None:
        result = self.results_screen.update(dt, pointer, confirm, key_events)
        if result == "play_again":
            self.active_game = self._instantiate_game(self.active_game_id)
            self.state = ArcadeState.PLAYING
        elif result == "back_to_hub":
            self.active_game = None
            self.active_game_id = None
            self.state = ArcadeState.HOME

    def _record_current_game_progress(self) -> None:
        """Save an in-progress round's score when the player quits to
        the hub early, so effort already spent isn't silently lost."""
        if self.active_game is None:
            return
        results = self.active_game.get_results()
        game_id = results.get("game_id", self.active_game_id)
        score = results.get("score", 0)
        self.scores.record_score(game_id, score)
        save_scores(self.scores)

    # --- Drawing ---------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        if self.state == ArcadeState.HOME:
            self.home_screen.draw(surface, self.typography, theme)
        elif self.state == ArcadeState.SETTINGS:
            self.settings_screen.draw(surface, self.typography, theme)
        elif self.state == ArcadeState.CALIBRATION:
            self.calibration_screen.draw(surface, self.typography, theme)
        elif self.state == ArcadeState.PLAYING:
            self._draw_playing(surface, theme)
        elif self.state == ArcadeState.PAUSED:
            self._draw_playing(surface, theme)  # frozen game frame behind the overlay
            self.pause_screen.draw(surface, self.typography, theme)
        elif self.state == ArcadeState.RESULTS:
            self.results_screen.draw(surface, self.typography, theme, game_title=self._active_game_title())

    def _draw_playing(self, surface: pygame.Surface, theme: Theme) -> None:
        if self.active_game is not None:
            self.active_game.draw(surface)
        else:
            self._draw_playing_placeholder(surface, theme)

    def _draw_playing_placeholder(self, surface: pygame.Surface, theme: Theme) -> None:
        surface.fill(theme.background)
        title = self._active_game_title()
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
        if self.state == ArcadeState.PLAYING:
            self._record_current_game_progress()
        save_settings(self.settings)
        save_scores(self.scores)
        save_profile(self.profile)
