"""Tests for `visionarcade.ui.calibration.CalibrationScreen`."""

from __future__ import annotations

import pygame

from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography
from visionarcade.ui.calibration import CalibrationScreen
from visionarcade.vision.calibration import CalibrationStep
from visionarcade.vision.simulation import SimulatedHandInputSource

DT = 1 / 30


def test_escape_skips_and_returns_home():
    screen = CalibrationScreen(1280, 720)
    result = screen.update(DT, None, None, False, [pygame.K_ESCAPE])
    assert result == "home"
    assert screen.session.is_done is True


def test_pointer_confirm_on_skip_button_skips():
    screen = CalibrationScreen(1280, 720)
    pointer = screen._skip_rect.center
    result = screen.update(DT, None, pointer, True, [])
    assert result == "home"


def test_pointer_confirm_elsewhere_does_not_skip():
    screen = CalibrationScreen(1280, 720)
    result = screen.update(DT, None, (5, 5), True, [])
    assert result is None
    assert screen.session.is_done is False


def test_on_enter_starts_a_fresh_session():
    screen = CalibrationScreen(1280, 720)
    screen.update(DT, None, None, False, [pygame.K_ESCAPE])  # skip -> done
    assert screen.session.is_done is True
    screen.on_enter()
    assert screen.session.is_done is False
    assert screen.session.step == CalibrationStep.PLACE_HAND


def test_full_walkthrough_via_simulator_reaches_home():
    screen = CalibrationScreen(1280, 720)
    screen.session = _fast_session()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), openness=1.0, pinch=False)

    result = None
    positions = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
    for i in range(400):
        step = screen.session.step
        if step is CalibrationStep.MOVE_RANGE:
            source.move_hand("Right", positions[i % len(positions)])
        elif step is CalibrationStep.PINCH:
            source.set_pinch("Right", True)
        elif step is CalibrationStep.OPEN_PALM:
            source.set_pinch("Right", False)
            source.set_openness("Right", 1.0)
        elif step is CalibrationStep.SWIPE:
            source.move_hand("Right", (0.1 + (i % 10) * 0.15, 0.5))

        primary_hand = source.get_hand_results()[0] if source.is_present("Right") else None
        result = screen.update(DT, primary_hand, None, False, [])
        if result == "home":
            break

    assert result == "home"
    assert screen.session.result is not None
    assert screen.session.result.calibrated is True


def _fast_session():
    from visionarcade.vision.calibration import CalibrationSession

    return CalibrationSession(move_phase_seconds=0.2, step_hold_seconds=0.05)


def test_draw_does_not_raise(renderer):
    screen = CalibrationScreen(renderer.surface.get_width(), renderer.surface.get_height())
    screen.draw(renderer.surface, Typography(), get_theme("dark"))
