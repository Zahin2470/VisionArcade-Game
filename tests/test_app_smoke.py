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


def test_simulate_mode_plays_a_real_match_of_pong_end_to_end(tmp_path, monkeypatch):
    """Drive the actual app into Vision Pong, pick 1-player mode via a
    real touchless pinch on the in-game menu, and win a point — nothing
    mocked below the OS event queue.

    `--simulate` mode normally lets a human drive the simulated hand's
    pinch from the physical Space key (`_apply_simulated_keyboard_input`),
    which unconditionally follows real keyboard state every frame. This
    test drives the simulator's pinch programmatically instead, so that
    keyboard-follow (which would just keep re-asserting "not pressed"
    from the test's non-existent physical keyboard) is disabled here.
    """
    monkeypatch.setattr("visionarcade.persistence.settings.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.scores.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.persistence.profiles.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("visionarcade.vision.calibration.get_user_data_dir", lambda: tmp_path)

    config = AppConfig(window_width=640, window_height=480, simulate=True)
    app = VisionArcadeApp(config)
    app.start()
    monkeypatch.setattr(app, "_apply_simulated_keyboard_input", lambda dt: None)

    try:
        # Select Vision Pong's card (second item in the hub).
        for _ in range(5):
            app.step()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        app.step()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        app.step()
        assert app.arcade_manager.active_game is not None
        game = app.arcade_manager.active_game
        assert game.id == "pong"

        # Choose 1-player mode via a real touchless pinch: move the
        # simulated hand's normalized position onto the button, via the
        # simulator's public API, then hold a pinch. The pinch-distance
        # smoother needs many frames to converge from "open" to
        # "closed" (see Phase 2), so hold it rather than pulsing once.
        # The simulator feeds raw (pre-calibration) coordinates, and
        # IntentBuilder remaps those through the default calibration
        # range before they become HandIntent.position — invert that
        # remap so the final, post-calibration position lands on the
        # button.
        from visionarcade.vision.calibration import CalibrationData

        default_calibration = CalibrationData.default()
        single_item = next(i for i in game._mode_focus.items if i.item_id == "single")
        rel_x = (single_item.rect.centerx - game.play_area.x) / game.play_area.width
        rel_y = (single_item.rect.centery - game.play_area.y) / game.play_area.height
        raw_x = default_calibration.x_min + rel_x * (default_calibration.x_max - default_calibration.x_min)
        raw_y = default_calibration.y_min + rel_y * (default_calibration.y_max - default_calibration.y_min)
        app.simulator.move_hand("Right", (raw_x, raw_y))
        for _ in range(5):  # let the hover register
            app.step()
        app.simulator.set_pinch("Right", True)
        for _ in range(60):
            app.step()
            if game._mode is not None:
                break
        app.simulator.set_pinch("Right", False)

        from visionarcade.arcade.games.pong import PongMode
        from visionarcade.arcade.games.pong import _Phase as _PongPhase

        assert game._mode is PongMode.SINGLE_PLAYER

        # Force a real win via one real physics-resolving frame.
        game._phase = _PongPhase.PLAYING
        game._right_score = game._points_to_win - 1
        game._serve_timer = 0.0
        game._ball_x = game.play_area.left - 100
        app.step()
        assert game.is_finished() is True
        assert app.arcade_manager.state.value == "results"
    finally:
        app.shutdown()
