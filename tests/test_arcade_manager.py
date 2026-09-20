"""Tests for `visionarcade.arcade.manager.ArcadeManager`.

Persistence writes are redirected to a temp directory for every test
here (via the `isolated_user_data_dir` fixture) so these tests never
touch the real per-user data directory.
"""

from __future__ import annotations

import pygame
import pytest

from visionarcade.arcade.games.catch import _Phase as _CatchPhase
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
    monkeypatch.setattr("visionarcade.arcade.manager.get_user_data_dir", lambda: tmp_path)
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


def test_navigating_to_tutorial_and_back_returns_home(isolated_user_data_dir):
    manager = _manager()
    tutorial_item = next(i for i in manager.home_screen._focus.items if i.item_id == "tutorial")
    pointer = _normalized(tutorial_item.rect.center)
    manager.update(_intent_with_pointer(*pointer), [], [], DT)
    manager.update(_intent_with_pointer(*pointer, pinch=PinchState.START), [], [], DT)
    assert manager.state == ArcadeState.TUTORIAL

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


def test_save_share_card_from_results_writes_a_file_and_shows_a_message(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.active_game._phase = _CatchPhase.PLAYING
    manager.active_game._lives = 0
    manager.active_game._objects = []
    manager.update(_empty_intent(), [], [], DT)  # -> RESULTS
    assert manager.state == ArcadeState.RESULTS

    manager.update(_empty_intent(), [], [pygame.K_RIGHT], DT)  # focus Save Share Card
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)

    assert manager.results_screen._message_timer > 0
    share_cards_dir = isolated_user_data_dir / "share_cards"
    assert share_cards_dir.exists()
    assert any(share_cards_dir.iterdir())


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


# --- Real gameplay: catch, pause, results (Phase 4) ---------------------------

def test_selecting_catch_instantiates_a_real_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    assert manager.active_game is not None
    assert manager.active_game.id == "catch"
    assert manager.state == ArcadeState.PLAYING


def test_selecting_an_unregistered_game_id_still_uses_the_placeholder(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("some_future_game")
    assert manager.active_game is None
    assert manager.state == ArcadeState.PLAYING


def test_escape_during_real_gameplay_pauses_instead_of_returning_home(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.PAUSED
    assert manager.active_game is not None  # game is frozen, not discarded


def test_resume_from_pause_returns_to_playing_with_same_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    game_before = manager.active_game
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # -> PAUSED
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)  # Resume is focused by default
    assert manager.state == ArcadeState.PLAYING
    assert manager.active_game is game_before


def test_restart_from_pause_gives_a_fresh_game_instance(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.active_game._score.add(500)  # dirty the state
    game_before = manager.active_game

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # -> PAUSED
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)  # focus Restart
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)

    assert manager.state == ArcadeState.PLAYING
    assert manager.active_game is not game_before
    assert manager.active_game._score.score == 0


def test_quit_to_hub_from_pause_records_partial_score(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.active_game._score.add(77)

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # -> PAUSED
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)  # focus Quit to Hub
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)

    assert manager.state == ArcadeState.HOME
    assert manager.active_game is None
    assert manager.scores.best_score("catch") == 77


def test_finishing_a_round_transitions_to_results_and_saves_score(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.active_game._phase = _CatchPhase.PLAYING
    manager.active_game._lives = 0
    manager.active_game._objects = []
    manager.update(_empty_intent(), [], [], DT)  # triggers game-over inside update()

    assert manager.state == ArcadeState.RESULTS
    assert manager.scores.best_score("catch") is not None
    assert manager.profile.total_games_played == 1


def test_play_again_from_results_starts_a_fresh_round(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.active_game._phase = _CatchPhase.PLAYING
    manager.active_game._lives = 0
    manager.active_game._objects = []
    manager.update(_empty_intent(), [], [], DT)  # -> RESULTS
    assert manager.state == ArcadeState.RESULTS

    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)  # Play Again is focused by default
    assert manager.state == ArcadeState.PLAYING
    assert manager.active_game is not None
    assert manager.active_game.is_finished() is False


def test_back_to_hub_from_results(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.active_game._phase = _CatchPhase.PLAYING
    manager.active_game._lives = 0
    manager.active_game._objects = []
    manager.update(_empty_intent(), [], [], DT)  # -> RESULTS

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.HOME
    assert manager.active_game is None


def test_shutdown_during_active_playing_records_progress(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("catch")
    manager.active_game._score.add(33)
    manager.shutdown()

    from visionarcade.persistence.scores import load_scores

    assert load_scores().best_score("catch") == 33


def test_draw_does_not_raise_while_paused_or_in_results(renderer, isolated_user_data_dir):
    manager = ArcadeManager(
        width=renderer.surface.get_width(),
        height=renderer.surface.get_height(),
        settings=Settings(),
        scores=ScoresStore(),
        profile=PlayerProfile(),
        calibration=CalibrationData.default(),
    )
    manager._start_game("catch")
    manager.draw(renderer.surface)

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    manager.draw(renderer.surface)  # PAUSED

    manager.active_game._phase = _CatchPhase.PLAYING
    manager.active_game._lives = 0
    manager.state = ArcadeState.PLAYING
    manager.active_game._objects = []
    manager.update(_empty_intent(), [], [], DT)
    manager.draw(renderer.surface)  # RESULTS


# --- Pong is registered like any other game (Phase 5) --------------------------

def test_selecting_pong_instantiates_a_real_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("pong")
    assert manager.active_game is not None
    assert manager.active_game.id == "pong"
    assert manager.state == ArcadeState.PLAYING


def test_pong_pauses_like_any_other_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("pong")
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.PAUSED
    assert manager.active_game is not None


def test_pong_quit_to_hub_from_pause_records_score(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("pong")
    manager.active_game._right_score = 4

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # -> PAUSED
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)  # focus Quit to Hub
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)

    assert manager.state == ArcadeState.HOME
    assert manager.scores.best_score("pong") == 4


def test_pong_finishing_a_match_transitions_to_results(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("pong")
    from visionarcade.arcade.games.pong import PongMode
    from visionarcade.arcade.games.pong import _Phase as _PongPhase

    manager.active_game._mode = PongMode.SINGLE_PLAYER
    manager.active_game._phase = _PongPhase.PLAYING
    manager.active_game._right_score = manager.active_game._points_to_win - 1
    manager.active_game._serve_timer = 0.0
    manager.active_game._ball_x = manager.active_game.play_area.left - 100
    manager.update(_empty_intent(), [], [], DT)

    assert manager.state == ArcadeState.RESULTS
    assert manager.scores.best_score("pong") is not None
    assert manager.profile.total_games_played == 1


def test_draw_does_not_raise_for_pong_in_every_state(renderer, isolated_user_data_dir):
    manager = ArcadeManager(
        width=renderer.surface.get_width(),
        height=renderer.surface.get_height(),
        settings=Settings(),
        scores=ScoresStore(),
        profile=PlayerProfile(),
        calibration=CalibrationData.default(),
    )
    manager._start_game("pong")
    manager.draw(renderer.surface)  # PLAYING (mode select sub-screen)
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    manager.draw(renderer.surface)  # PAUSED


# --- Slice is registered like any other game (Phase 6) --------------------------

def test_selecting_slice_instantiates_a_real_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("slice")
    assert manager.active_game is not None
    assert manager.active_game.id == "slice"
    assert manager.state == ArcadeState.PLAYING


def test_slice_pauses_like_any_other_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("slice")
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.PAUSED
    assert manager.active_game is not None


def test_slice_quit_to_hub_from_pause_records_score(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("slice")
    manager.active_game._score.add(88)

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # -> PAUSED
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)  # focus Quit to Hub
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)

    assert manager.state == ArcadeState.HOME
    assert manager.scores.best_score("slice") == 88


def test_slice_finishing_a_round_transitions_to_results(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("slice")
    from visionarcade.arcade.games.slice import _Phase as _SlicePhase

    manager.active_game._phase = _SlicePhase.PLAYING
    manager.active_game._lives = 0
    manager.active_game._targets = []
    manager.update(_empty_intent(), [], [], DT)

    assert manager.state == ArcadeState.RESULTS
    assert manager.scores.best_score("slice") is not None
    assert manager.profile.total_games_played == 1


def test_draw_does_not_raise_for_slice_in_every_state(renderer, isolated_user_data_dir):
    manager = ArcadeManager(
        width=renderer.surface.get_width(),
        height=renderer.surface.get_height(),
        settings=Settings(),
        scores=ScoresStore(),
        profile=PlayerProfile(),
        calibration=CalibrationData.default(),
    )
    manager._start_game("slice")
    manager.draw(renderer.surface)  # PLAYING
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    manager.draw(renderer.surface)  # PAUSED


# --- Aim is registered like any other game (Phase 7) --------------------------

def test_selecting_aim_instantiates_a_real_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("aim")
    assert manager.active_game is not None
    assert manager.active_game.id == "aim"
    assert manager.state == ArcadeState.PLAYING


def test_aim_pauses_like_any_other_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("aim")
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.PAUSED
    assert manager.active_game is not None


def test_aim_quit_to_hub_from_pause_records_score(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("aim")
    manager.active_game._score.add(60)

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # -> PAUSED
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)  # focus Quit to Hub
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)

    assert manager.state == ArcadeState.HOME
    assert manager.scores.best_score("aim") == 60


def test_aim_finishing_a_round_transitions_to_results(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("aim")
    from visionarcade.arcade.games.aim import _Phase as _AimPhase
    from visionarcade.constants import AIM_MAX_MISSES

    manager.active_game._phase = _AimPhase.PLAYING
    manager.active_game._targets_missed = AIM_MAX_MISSES - 1
    manager.active_game._target_time_remaining = -1.0
    manager.update(_empty_intent(), [], [], DT)

    assert manager.state == ArcadeState.RESULTS
    assert manager.scores.best_score("aim") is not None
    assert manager.profile.total_games_played == 1


def test_draw_does_not_raise_for_aim_in_every_state(renderer, isolated_user_data_dir):
    manager = ArcadeManager(
        width=renderer.surface.get_width(),
        height=renderer.surface.get_height(),
        settings=Settings(),
        scores=ScoresStore(),
        profile=PlayerProfile(),
        calibration=CalibrationData.default(),
    )
    manager._start_game("aim")
    manager.draw(renderer.surface)  # PLAYING
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    manager.draw(renderer.surface)  # PAUSED


# --- Puzzle is registered like any other game (Phase 8) -----------------------

def test_selecting_puzzle_instantiates_a_real_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("puzzle")
    assert manager.active_game is not None
    assert manager.active_game.id == "puzzle"
    assert manager.state == ArcadeState.PLAYING


def test_puzzle_pauses_like_any_other_game(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("puzzle")
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    assert manager.state == ArcadeState.PAUSED
    assert manager.active_game is not None


def test_puzzle_quit_to_hub_from_pause_records_score(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("puzzle")
    manager.active_game._score.add(45)

    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)  # -> PAUSED
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)
    manager.update(_empty_intent(), [], [pygame.K_DOWN], DT)  # focus Quit to Hub
    manager.update(_empty_intent(), [], [pygame.K_RETURN], DT)

    assert manager.state == ArcadeState.HOME
    assert manager.scores.best_score("puzzle") == 45


def test_puzzle_finishing_a_round_transitions_to_results(isolated_user_data_dir):
    manager = _manager()
    manager._start_game("puzzle")
    from visionarcade.arcade.games.puzzle import _Phase as _PuzzlePhase

    manager.active_game._phase = _PuzzlePhase.PLAYING
    manager.active_game._stage_time_remaining = -1.0
    manager.update(_empty_intent(), [], [], DT)

    assert manager.state == ArcadeState.RESULTS
    assert manager.scores.best_score("puzzle") is not None
    assert manager.profile.total_games_played == 1


def test_draw_does_not_raise_for_puzzle_in_every_state(renderer, isolated_user_data_dir):
    manager = ArcadeManager(
        width=renderer.surface.get_width(),
        height=renderer.surface.get_height(),
        settings=Settings(),
        scores=ScoresStore(),
        profile=PlayerProfile(),
        calibration=CalibrationData.default(),
    )
    manager._start_game("puzzle")
    manager.draw(renderer.surface)  # PLAYING
    manager.update(_empty_intent(), [], [pygame.K_ESCAPE], DT)
    manager.draw(renderer.surface)  # PAUSED
