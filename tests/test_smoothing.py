"""Tests for `visionarcade.vision.smoothing`."""

from __future__ import annotations

import pytest

from visionarcade.vision.smoothing import ExponentialSmoother, HysteresisGate, PointSmoother


def test_first_update_snaps_to_raw_value():
    smoother = ExponentialSmoother(time_constant=0.1)
    assert smoother.value is None
    result = smoother.update(10.0, dt=1 / 60)
    assert result == pytest.approx(10.0)


def test_smoother_converges_toward_a_held_target():
    smoother = ExponentialSmoother(time_constant=0.1)
    smoother.update(0.0, dt=1 / 60)
    for _ in range(300):  # far more than enough time to settle
        value = smoother.update(1.0, dt=1 / 60)
    assert value == pytest.approx(1.0, abs=1e-3)


def test_smoother_lags_a_sudden_jump_short_term():
    smoother = ExponentialSmoother(time_constant=0.5)
    smoother.update(0.0, dt=1 / 60)
    value = smoother.update(1.0, dt=1 / 60)
    assert 0.0 < value < 0.5  # one small frame shouldn't jump all the way


def test_reset_clears_and_reseeds_value():
    smoother = ExponentialSmoother()
    smoother.update(5.0, dt=1 / 60)
    smoother.reset()
    assert smoother.value is None
    smoother.reset(2.0)
    assert smoother.value == 2.0


def test_nonpositive_time_constant_rejected():
    with pytest.raises(ValueError):
        ExponentialSmoother(time_constant=0.0)


def test_zero_or_negative_dt_snaps_instead_of_smoothing():
    smoother = ExponentialSmoother()
    smoother.update(0.0, dt=1 / 60)
    result = smoother.update(99.0, dt=0.0)
    assert result == pytest.approx(99.0)


def test_point_smoother_smooths_each_axis_independently():
    smoother = PointSmoother(time_constant=0.1)
    assert smoother.value is None
    smoother.update((0.0, 0.0), dt=1 / 60)
    for _ in range(300):
        point = smoother.update((1.0, -1.0), dt=1 / 60)
    assert point[0] == pytest.approx(1.0, abs=1e-3)
    assert point[1] == pytest.approx(-1.0, abs=1e-3)


def test_point_smoother_reset():
    smoother = PointSmoother()
    smoother.update((1.0, 1.0), dt=1 / 60)
    smoother.reset()
    assert smoother.value is None
    smoother.reset((3.0, 4.0))
    assert smoother.value == (3.0, 4.0)


# --- HysteresisGate ----------------------------------------------------------

def test_gate_starts_at_initial_state():
    gate = HysteresisGate(enter_frames=2, exit_frames=3, initial=False)
    assert gate.state is False


def test_gate_requires_enter_frames_before_flipping_true():
    gate = HysteresisGate(enter_frames=3, exit_frames=1, initial=False)
    assert gate.update(True) is False
    assert gate.update(True) is False
    assert gate.update(True) is True  # third consecutive confirmation


def test_gate_requires_exit_frames_before_flipping_false():
    gate = HysteresisGate(enter_frames=1, exit_frames=3, initial=True)
    assert gate.update(False) is True
    assert gate.update(False) is True
    assert gate.update(False) is False  # third consecutive confirmation


def test_gate_resets_counter_on_flicker():
    gate = HysteresisGate(enter_frames=3, exit_frames=3, initial=False)
    gate.update(True)
    gate.update(True)
    gate.update(False)  # flicker back — counter should reset
    assert gate.update(True) is False
    assert gate.update(True) is False
    assert gate.update(True) is True


def test_gate_reset_method():
    gate = HysteresisGate(enter_frames=1, exit_frames=1, initial=False)
    gate.update(True)
    assert gate.state is True
    gate.reset(False)
    assert gate.state is False
