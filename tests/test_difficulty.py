"""Tests for `visionarcade.arcade.difficulty.DifficultyCurve`."""

from __future__ import annotations

import pytest

from visionarcade.arcade.difficulty import DifficultyCurve


def test_value_at_zero_is_start():
    curve = DifficultyCurve(start=100.0, end=200.0, ramp_seconds=10.0)
    assert curve.value_at(0.0) == pytest.approx(100.0)


def test_value_at_ramp_end_is_end():
    curve = DifficultyCurve(start=100.0, end=200.0, ramp_seconds=10.0)
    assert curve.value_at(10.0) == pytest.approx(200.0)


def test_value_at_midpoint_is_halfway():
    curve = DifficultyCurve(start=100.0, end=200.0, ramp_seconds=10.0)
    assert curve.value_at(5.0) == pytest.approx(150.0)


def test_value_is_clamped_past_ramp_end():
    curve = DifficultyCurve(start=100.0, end=200.0, ramp_seconds=10.0)
    assert curve.value_at(999.0) == pytest.approx(200.0)


def test_value_is_clamped_before_zero():
    curve = DifficultyCurve(start=100.0, end=200.0, ramp_seconds=10.0)
    assert curve.value_at(-5.0) == pytest.approx(100.0)


def test_descending_curve_works_the_same_way():
    # e.g. a spawn interval that shrinks over time
    curve = DifficultyCurve(start=1.0, end=0.4, ramp_seconds=10.0)
    assert curve.value_at(0.0) == pytest.approx(1.0)
    assert curve.value_at(10.0) == pytest.approx(0.4)
    assert curve.value_at(5.0) == pytest.approx(0.7)


def test_nonpositive_ramp_seconds_rejected():
    with pytest.raises(ValueError):
        DifficultyCurve(start=1.0, end=2.0, ramp_seconds=0.0)
