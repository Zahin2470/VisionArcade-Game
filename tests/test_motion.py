"""Tests for `visionarcade.vision.motion`."""

from __future__ import annotations

import pytest

from visionarcade.vision.motion import MotionTracker, SwipeDirection


def test_velocity_is_zero_before_any_update():
    tracker = MotionTracker()
    assert tracker.velocity == (0.0, 0.0)


def test_velocity_reflects_position_delta_over_dt():
    tracker = MotionTracker()
    tracker.update((0.0, 0.0), dt=0.1)
    velocity = tracker.update((0.1, 0.0), dt=0.1)
    assert velocity[0] == pytest.approx(1.0)  # 0.1 units / 0.1s
    assert velocity[1] == pytest.approx(0.0)


def test_zero_dt_does_not_update_velocity():
    tracker = MotionTracker()
    tracker.update((0.0, 0.0), dt=0.1)
    tracker.update((0.1, 0.0), dt=0.1)
    before = tracker.velocity
    after = tracker.update((5.0, 5.0), dt=0.0)
    assert after == before


def test_fast_sustained_rightward_motion_detected_as_right_swipe():
    tracker = MotionTracker(
        window_seconds=0.3, min_speed=1.0, min_displacement=0.1, cooldown_seconds=0.5
    )
    # Move steadily rightward fast enough and far enough within the window.
    for i in range(6):
        tracker.update((i * 0.06, 0.0), dt=0.05)
    assert tracker.detect_swipe() == SwipeDirection.RIGHT


def test_slow_drift_is_not_detected_as_a_swipe():
    tracker = MotionTracker(
        window_seconds=0.3, min_speed=1.0, min_displacement=0.1, cooldown_seconds=0.5
    )
    for _ in range(6):
        tracker.update((0.001, 0.0), dt=0.05)  # tiny, slow movement
    assert tracker.detect_swipe() is None


def test_vertical_swipe_classified_as_up_or_down():
    tracker = MotionTracker(
        window_seconds=0.3, min_speed=1.0, min_displacement=0.1, cooldown_seconds=0.5
    )
    for i in range(6):
        tracker.update((0.0, i * 0.06), dt=0.05)
    assert tracker.detect_swipe() == SwipeDirection.DOWN


def test_swipe_has_a_cooldown_and_does_not_fire_twice():
    tracker = MotionTracker(
        window_seconds=0.3, min_speed=1.0, min_displacement=0.1, cooldown_seconds=0.5
    )
    for i in range(6):
        tracker.update((i * 0.06, 0.0), dt=0.05)
    first = tracker.detect_swipe()
    second = tracker.detect_swipe()
    assert first == SwipeDirection.RIGHT
    assert second is None


def test_reset_clears_history_and_velocity():
    tracker = MotionTracker()
    tracker.update((1.0, 1.0), dt=0.1)
    tracker.update((2.0, 2.0), dt=0.1)
    tracker.reset()
    assert tracker.velocity == (0.0, 0.0)
    assert tracker.detect_swipe() is None
