"""Tests for `visionarcade.vision.calibration`."""

from __future__ import annotations

import pytest

from visionarcade.vision.calibration import (
    CalibrationData,
    CalibrationSession,
    CalibrationStep,
    load_calibration,
    save_calibration,
)
from visionarcade.vision.simulation import SimulatedHandInputSource

DT = 1 / 30


# --- CalibrationData: remap ---------------------------------------------------

def test_default_calibration_is_not_marked_calibrated():
    data = CalibrationData.default()
    assert data.calibrated is False


def test_remap_maps_calibrated_range_to_unit_square():
    data = CalibrationData(x_min=0.2, x_max=0.8, y_min=0.3, y_max=0.7, calibrated=True)
    assert data.remap((0.2, 0.3)) == pytest.approx((0.0, 0.0))
    assert data.remap((0.8, 0.7)) == pytest.approx((1.0, 1.0))
    assert data.remap((0.5, 0.5)) == pytest.approx((0.5, 0.5))


def test_remap_clamps_values_outside_the_calibrated_range():
    data = CalibrationData(x_min=0.2, x_max=0.8, y_min=0.2, y_max=0.8, calibrated=True)
    assert data.remap((0.0, 0.0)) == pytest.approx((0.0, 0.0))
    assert data.remap((1.0, 1.0)) == pytest.approx((1.0, 1.0))


def test_remap_falls_back_to_raw_value_on_degenerate_range():
    # x_min == x_max: a real range this narrow would make remapping
    # meaningless, so it should fall back to the clamped raw value.
    data = CalibrationData(x_min=0.5, x_max=0.5, y_min=0.2, y_max=0.8, calibrated=True)
    x, _ = data.remap((0.5, 0.5))
    assert x == pytest.approx(0.5)


# --- Persistence: save/load ---------------------------------------------------

def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "calibration.json"
    data = CalibrationData(x_min=0.1, x_max=0.9, y_min=0.15, y_max=0.85, calibrated=True)
    assert save_calibration(data, path=path) is True

    loaded = load_calibration(path=path)
    assert loaded == data


def test_load_missing_file_returns_defaults(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"
    loaded = load_calibration(path=missing_path)
    assert loaded == CalibrationData.default()


def test_load_corrupted_file_falls_back_to_defaults_without_raising(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text("{not valid json!!", encoding="utf-8")
    loaded = load_calibration(path=path)  # must not raise
    assert loaded == CalibrationData.default()


def test_load_file_with_wrong_types_falls_back_gracefully(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text('{"x_min": "not-a-number"}', encoding="utf-8")
    loaded = load_calibration(path=path)
    assert loaded == CalibrationData.default()


def test_save_failure_returns_false_without_raising(tmp_path):
    # Point "inside" a file instead of a directory, so parent.mkdir()
    # fails — this must be reported, not raised.
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("x", encoding="utf-8")
    bad_path = blocking_file / "calibration.json"

    result = save_calibration(CalibrationData.default(), path=bad_path)
    assert result is False


# --- CalibrationSession -------------------------------------------------------

def test_session_starts_at_place_hand():
    session = CalibrationSession()
    assert session.step == CalibrationStep.PLACE_HAND
    assert session.is_done is False


def test_session_without_a_hand_never_advances_past_place_hand():
    session = CalibrationSession(step_hold_seconds=0.2)
    for _ in range(30):
        session.update(None, DT)
    assert session.step == CalibrationStep.PLACE_HAND


def test_full_session_walkthrough_produces_calibrated_result():
    session = CalibrationSession(move_phase_seconds=0.3, step_hold_seconds=0.1)
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), openness=1.0, pinch=False)

    # PLACE_HAND
    for _ in range(10):
        if session.step is not CalibrationStep.PLACE_HAND:
            break
        session.update(source.get_hand_results()[0], DT)
    assert session.step == CalibrationStep.MOVE_RANGE

    # MOVE_RANGE: sweep across a wide area so the observed range is real.
    positions = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9), (0.5, 0.5)]
    for i in range(20):
        if session.step is not CalibrationStep.MOVE_RANGE:
            break
        pos = positions[i % len(positions)]
        source.move_hand("Right", pos)
        session.update(source.get_hand_results()[0], DT)
    assert session.step == CalibrationStep.PINCH

    # PINCH
    source.set_pinch("Right", True)
    for _ in range(10):
        if session.step is not CalibrationStep.PINCH:
            break
        session.update(source.get_hand_results()[0], DT)
    assert session.step == CalibrationStep.OPEN_PALM

    # OPEN_PALM
    source.set_pinch("Right", False)
    source.set_openness("Right", 1.0)
    for _ in range(10):
        if session.step is not CalibrationStep.OPEN_PALM:
            break
        session.update(source.get_hand_results()[0], DT)
    assert session.step == CalibrationStep.SWIPE

    # SWIPE: a bigger per-frame step than the pipeline test above, since
    # the session's swipe detector trims its history to its own window
    # and needs enough displacement/speed within that trimmed window.
    for i in range(25):
        if session.step is not CalibrationStep.SWIPE:
            break
        source.move_hand("Right", (0.2 + i * 0.15, 0.5))
        session.update(source.get_hand_results()[0], DT)

    assert session.is_done is True
    result = session.result
    assert result is not None
    assert result.calibrated is True
    # The observed range should reflect the wide sweep, not the defaults.
    assert result.x_max - result.x_min > 0.5


def test_session_with_no_movement_reaches_pinch_step_without_crashing():
    session = CalibrationSession(move_phase_seconds=0.1, step_hold_seconds=0.05)
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))

    for _ in range(5):
        if session.step is not CalibrationStep.PLACE_HAND:
            break
        session.update(source.get_hand_results()[0], DT)

    # MOVE_RANGE with the hand held perfectly still (a degenerate range).
    for _ in range(10):
        if session.step is not CalibrationStep.MOVE_RANGE:
            break
        session.update(source.get_hand_results()[0], DT)

    assert session.step == CalibrationStep.PINCH
    # The numeric fallback for a degenerate range is covered directly by
    # test_remap_falls_back_to_raw_value_on_degenerate_range above; this
    # test only proves the session's own timing logic doesn't get stuck.


def test_skip_returns_default_calibration_and_marks_session_done():
    session = CalibrationSession()
    result = session.skip()
    assert result == CalibrationData.default()
    assert session.is_done is True
    assert session.result == CalibrationData.default()
