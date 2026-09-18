"""End-to-end smoke test for `VisionArcadeApp`.

This deliberately does NOT mock the camera — in this headless test
environment there is no real webcam, so `CameraService.open()` returns
False naturally. That's exactly the "no camera available" path the
project's error-handling requirements call for, so exercising it for
real (rather than mocking a success) is the more valuable test here.
"""

from __future__ import annotations

import pygame

from visionarcade.app import VisionArcadeApp
from visionarcade.arcade.state import ArcadeState
from visionarcade.config import AppConfig


def test_app_runs_bounded_loop_without_camera_or_crashing():
    config = AppConfig(window_width=320, window_height=240, debug=True)
    app = VisionArcadeApp(config)

    app.run(max_frames=5)  # must return normally, not hang or raise

    assert app.renderer.is_open is False  # shutdown() closed everything
    assert app.camera.is_open is False


def test_app_start_is_idempotent():
    config = AppConfig(window_width=320, window_height=240)
    app = VisionArcadeApp(config)
    app.start()
    app.start()  # should not reopen or raise
    assert app.renderer.is_open is True
    app.shutdown()


def test_app_shutdown_before_start_does_not_raise():
    config = AppConfig(window_width=320, window_height=240)
    app = VisionArcadeApp(config)
    app.shutdown()  # nothing was ever opened; must be a safe no-op


def test_app_runs_in_simulate_mode_without_a_camera_or_tracker():
    config = AppConfig(window_width=320, window_height=240, debug=True, simulate=True)
    app = VisionArcadeApp(config)

    assert app.camera is None
    assert app.tracker is None
    assert app.simulator is not None

    app.run(max_frames=10)  # must produce FrameIntents from the simulator alone

    assert app.latest_intent is not None
    assert app.renderer.is_open is False


def test_simulate_mode_reports_the_default_right_hand_as_present_eventually():
    config = AppConfig(window_width=320, window_height=240, simulate=True)
    app = VisionArcadeApp(config)
    app.run(max_frames=10)  # a few frames beyond the presence-confirmation delay
    assert app.latest_intent.right.present is True


def test_app_starts_on_home_screen(tmp_path, monkeypatch):
    monkeypatch.setattr("visionarcade.persistence.settings.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.scores.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.profiles.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.vision.calibration.get_user_data_dir", lambda: tmp_path)

    config = AppConfig(window_width=320, window_height=240)
    app = VisionArcadeApp(config)
    app.start()
    assert app.arcade_manager.state == ArcadeState.HOME
    app.shutdown()


def test_keyboard_navigation_reaches_quit_end_to_end(tmp_path, monkeypatch):
    # Redirect persistence so this doesn't touch the real user data dir.
    monkeypatch.setattr("visionarcade.persistence.settings.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.scores.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.profiles.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.vision.calibration.get_user_data_dir", lambda: tmp_path)

    config = AppConfig(window_width=320, window_height=240)
    app = VisionArcadeApp(config)
    app.start()

    # Enough RIGHT presses to reach the Quit button (the last hub item),
    # then Enter to activate it — all queued before the single frame
    # that processes them, exercising the real event -> FocusGroup ->
    # ArcadeManager path with nothing mocked.
    item_count = len(app.arcade_manager.home_screen._focus.items)
    for _ in range(item_count - 1):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))

    app.run(max_frames=1)

    assert app.arcade_manager.should_quit is True


def test_simulate_mode_plays_a_real_round_of_catch_end_to_end(tmp_path, monkeypatch):
    """Drive the actual app (simulated hand, no camera) from the home
    screen into a real game of Vision Catch, catch a real falling
    object, and pause/resume — nothing mocked below the OS event
    queue."""
    monkeypatch.setattr("visionarcade.persistence.settings.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.scores.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.profiles.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.vision.calibration.get_user_data_dir", lambda: tmp_path)

    config = AppConfig(window_width=640, window_height=480, simulate=True)
    app = VisionArcadeApp(config)
    app.start()

    try:
        # Let the simulated hand register as present, then select Vision
        # Catch's card (the first item in the hub).
        for _ in range(5):
            app.step()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        app.step()
        assert app.arcade_manager.active_game is not None
        assert app.arcade_manager.active_game.id == "catch"

        # Fast-forward through the countdown, then force a catchable
        # object right on top of the catcher and let one real frame
        # resolve it.
        from visionarcade.arcade.games.catch import _FallingObject, _Phase

        game = app.arcade_manager.active_game
        game._phase = _Phase.PLAYING
        game._objects = [_FallingObject(x=game._catcher_x, y=game._catcher_rect().centery, kind="good")]
        app.step()
        assert game._score.score > 0

        # Pause, then resume, via the real keyboard path.
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        app.step()
        assert app.arcade_manager.state.value == "paused"
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        app.step()
        assert app.arcade_manager.state.value == "playing"
    finally:
        app.shutdown()
