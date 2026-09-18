"""Tests for `visionarcade.arcade.manager.ArcadeManager`.

Persistence writes are redirected to a temp directory for every test
here (via the `isolated_user_data_dir` fixture) so these tests never
touch the real per-user data directory.
"""

from __future__ import annotations

import pygame
import pytest

from visionarcade.arcade.manager import ArcadeManager
from visionarcade.arcade.state import ArcadeState
from visionarcade.config import KNOWN_GAMES
from visionarcade.persistence.profiles import PlayerProfile
from visionarcade.persistence.scores import ScoresStore
from visionarcade.persistence.settings import Settings
from visionarcade.vision.calibration import CalibrationData
from visionarcade.vision.gestures import FrameIntent, HandIntent, PinchState

DT = 1 / 60
WIDTH, HEIGHT = 1280, 720


@pytest.fixture
def isolated_user_data_dir(tmp_path, monkeypatch):
    """Redirect every persistence module's `get_user_data_dir()` to a
    temp directory, so ArcadeManager's save calls (which always use
    the default location) can't touch the real one."""
    monkeypatch.setattr("visionarcade.persistence.settings.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.scores.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.profiles.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.vision.calibration.get_user_data_dir", lambda: tmp_path)
    return tmp_path


def _manager() -> ArcadeManager:
    return ArcadeManager(
        width=WIDTH,
        height=HEIGHT,
        settings=Settings(),
        scores=ScoresStore(),
        profile=PlayerProfile(),
        calibration=CalibrationData.default(),
    )


def _absent() -> HandIntent:
    return HandIntent.absent("Right")


def _intent_with_pointer(x: float, y: float, pinch: PinchState = PinchState.NONE) -> FrameIntent:
    """`x`/`y` are normalized [0, 1] hand-space coordinates, matching
    what `IntentBuilder` actually produces — `ArcadeManager` multiplies
    these by the window size itself to get a pixel pointer."""
    right = HandIntent(
        handedness="Right",
        present=True,
        position=(x, y),
        index_tip=(x, y),
        pinch_state=pinch,
    )
    return FrameIntent(left=_absent(), right=right)


def _normalized(pixel_point) -> tuple[float, float]:
    return (pixel_point[0] / WIDTH, pixel_point[1] / HEIGHT)


def _empty_intent() -> FrameIntent:
    return FrameIntent(left=_absent(), right=_absent())


def test_starts_on_home():
    manager = _manager()
    assert manager.state == ArcadeState.HOME


def test_quit_via_home_sets_should_quit(isolated_user_data_dir):
    manager = _manager()
    # Navigate to the quit button (last focus item) and confirm.
    for _ in range(len(manager.home_screen._focus.items) - 1):
        manager.update(_empty_intent(), [], [pygame.K_RIGHT], DT)
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)
    assert manager.should_quit is True


def test_navigating_to_settings_and_back_persists_settings(isolated_user_data_dir):
    manager = _manager()
    settings_item = next(i for i in manager.home_screen._focus.items if i.item_id == "settings")
    pointer = _normalized(settings_item.rect.center)

    manager.update(_intent_with_pointer(*pointer), [], [], DT)  # hover
    manager.update(_intent_with_pointer(*pointer, pinch=PinchState.START), [], [], DT)  # confirm
    assert manager.state == ArcadeState.SETTINGS

    manager.update(_empty_intent(), [], [pygame.K_RIGHT], DT)  # cycle theme forward
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # back to home
    assert manager.state == ArcadeState.HOME
    assert manager.settings.theme != Settings().theme

    from visionarcade.persistence.settings import load_settings

    reloaded = load_settings()
    assert reloaded.theme == manager.settings.theme


def test_navigating_to_calibration_and_skipping_returns_home(isolated_user_data_dir):
    manager = _manager()
    calibration_item = next(
        i for i in manager.home_screen._focus.items if i.item_id == "calibration"
    )
    pointer = _normalized(calibration_item.rect.center)
    manager.update(_intent_with_pointer(*pointer), [], [], DT)
    manager.update(_intent_with_pointer(*pointer, pinch=PinchState.START), [], [], DT)
    assert manager.state == ArcadeState.CALIBRATION

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.HOME


def test_selecting_a_game_enters_playing_placeholder(isolated_user_data_dir):
    manager = _manager()
    game_id = KNOWN_GAMES[0]
    card = next(
        i for i in manager.home_screen._focus.items if i.item_id == f"play:{game_id}"
    )
    pointer = _normalized(card.rect.center)
    manager.update(_intent_with_pointer(*pointer), [], [], DT)
    manager.update(_intent_with_pointer(*pointer, pinch=PinchState.START), [], [], DT)
    assert manager.state == ArcadeState.PLAYING
    assert manager.active_game_id == game_id


def test_escape_from_playing_placeholder_returns_home(isolated_user_data_dir):
    manager = _manager()
    manager.state = ArcadeState.PLAYING
    manager.active_game_id = KNOWN_GAMES[0]
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.HOME
    assert manager.active_game_id is None


def test_reset_scores_from_settings_clears_scores(isolated_user_data_dir):
    scores = ScoresStore()
    scores.record_score(KNOWN_GAMES[0], 50, timestamp=1.0)
    manager = ArcadeManager(
        width=WIDTH,
        height=HEIGHT,
        settings=Settings(),
        scores=scores,
        profile=PlayerProfile(),
        calibration=CalibrationData.default(),
    )
    manager.state = ArcadeState.SETTINGS
    manager.settings_screen.on_enter(manager.settings)

    reset_item = next(
        i for i in manager.settings_screen._focus.items if i.item_id == "reset_scores"
    )
    manager.settings_screen._focus._focus_index = manager.settings_screen._focus.items.index(
        reset_item
    )
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)
    assert manager.scores.best_score(KNOWN_GAMES[0]) is None


def test_high_contrast_forces_mono_theme():
    manager = _manager()
    manager.settings = manager.settings.with_overrides(high_contrast=True, theme="neon")
    assert manager.theme.name == "mono"


def test_shutdown_persists_settings_scores_and_profile(isolated_user_data_dir):
    manager = _manager()
    manager.settings = manager.settings.with_overrides(theme="neon")
    manager.scores.record_score(KNOWN_GAMES[0], 77, timestamp=1.0)
    manager.profile = manager.profile.record_game_played(KNOWN_GAMES[0])

    manager.shutdown()

    from visionarcade.persistence.profiles import load_profile
    from visionarcade.persistence.scores import load_scores
    from visionarcade.persistence.settings import load_settings

    assert load_settings().theme == "neon"
    assert load_scores().best_score(KNOWN_GAMES[0]) == 77
    assert load_profile().total_games_played == 1


def test_draw_does_not_raise_in_every_state(renderer):
    manager = _manager()
    for state in (ArcadeState.HOME, ArcadeState.SETTINGS, ArcadeState.CALIBRATION, ArcadeState.PLAYING):
        manager.state = state
        manager.active_game_id = KNOWN_GAMES[0]
        manager.draw(renderer.surface)
