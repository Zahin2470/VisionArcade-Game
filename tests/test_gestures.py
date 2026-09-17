"""Tests for `visionarcade.vision.gestures`.

The `PinchStateMachine` is tested directly with raw distance values.
`IntentBuilder` is tested end-to-end using `SimulatedHandInputSource`,
which is exactly how Developer Mode and later game-logic tests will
exercise it — no camera or mocking required.
"""

from __future__ import annotations

from visionarcade.vision.gestures import IntentBuilder, PinchState, PinchStateMachine
from visionarcade.vision.motion import SwipeDirection
from visionarcade.vision.simulation import SimulatedHandInputSource

DT = 1 / 60


# --- PinchStateMachine --------------------------------------------------------

def test_pinch_starts_at_none():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=2)
    assert machine.state == PinchState.NONE


def test_pinch_requires_min_hold_frames_before_start():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=2)
    assert machine.update(0.1) == PinchState.NONE  # 1st closed frame: not yet confirmed
    assert machine.update(0.1) == PinchState.START  # 2nd closed frame: confirmed


def test_pinch_holds_after_start():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=1)
    assert machine.update(0.1) == PinchState.START
    assert machine.update(0.1) == PinchState.HOLD
    assert machine.update(0.1) == PinchState.HOLD


def test_pinch_releases_only_past_exit_threshold_not_enter_threshold():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=1)
    machine.update(0.1)  # START
    # A value between enter (0.35) and exit (0.55) should NOT release —
    # this is the hysteresis gap that prevents flicker.
    assert machine.update(0.45) == PinchState.HOLD
    assert machine.update(0.60) == PinchState.RELEASE


def test_pinch_returns_to_none_after_release():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=1)
    machine.update(0.1)  # START
    machine.update(0.60)  # RELEASE
    assert machine.update(0.60) == PinchState.NONE


def test_a_single_noisy_open_frame_during_hold_confirmation_resets_progress():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=3)
    machine.update(0.1)  # pending frame 1
    machine.update(0.1)  # pending frame 2
    machine.update(0.9)  # noisy open frame — should reset pending count
    assert machine.update(0.1) == PinchState.NONE  # pending frame 1 again, not START yet


def test_force_release_if_active_only_fires_when_closed():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=1)
    assert machine.force_release_if_active() is None  # never pinched
    machine.update(0.1)  # START -> closed
    assert machine.force_release_if_active() == PinchState.RELEASE
    assert machine.force_release_if_active() is None  # already released


def test_reset_clears_pinch_state():
    machine = PinchStateMachine(enter_distance=0.35, exit_distance=0.55, min_hold_frames=1)
    machine.update(0.1)
    machine.reset()
    assert machine.state == PinchState.NONE


# --- IntentBuilder (via the simulator) ----------------------------------------

def test_no_hands_yields_absent_intents():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    intent = builder.update(source.get_hand_results(), DT)
    assert intent.left.present is False
    assert intent.right.present is False
    assert intent.any_hand_present is False


def test_hand_present_requires_confirm_frames_before_reporting_present():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))

    # HAND_PRESENCE_CONFIRM_FRAMES defaults to 3 — the first couple of
    # frames should not yet report the hand as stably present.
    first = builder.update(source.get_hand_results(), DT)
    second = builder.update(source.get_hand_results(), DT)
    assert first.right.present is False
    assert second.right.present is False

    third = builder.update(source.get_hand_results(), DT)
    assert third.right.present is True


def _settle_hand_present(builder: IntentBuilder, source: SimulatedHandInputSource, frames: int = 5):
    intent = None
    for _ in range(frames):
        intent = builder.update(source.get_hand_results(), DT)
    return intent


def test_present_hand_reports_a_calibrated_position():
    builder = IntentBuilder()  # default calibration
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))
    intent = _settle_hand_present(builder, source)
    assert intent.right.present is True
    assert intent.right.position is not None
    x, y = intent.right.position
    assert 0.0 <= x <= 1.0
    assert 0.0 <= y <= 1.0


def test_pinch_flows_through_the_full_pipeline():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), pinch=False)
    _settle_hand_present(builder, source)

    source.set_pinch("Right", True)
    states_seen = []
    # The pinch-distance smoother starts from a fully-open value and
    # needs several time constants to decay across the enter threshold
    # — 60 frames at 1/60s is a full second, comfortably enough.
    for _ in range(60):
        intent = builder.update(source.get_hand_results(), DT)
        states_seen.append(intent.right.pinch_state)

    from visionarcade.vision.gestures import PinchState

    assert PinchState.START in states_seen or PinchState.HOLD in states_seen


def test_swipe_flows_through_the_full_pipeline():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.2, 0.5))
    _settle_hand_present(builder, source)

    swipe_seen = None
    # Move steadily rightward across many frames — enough distance and
    # speed within the swipe detector's window to register.
    for i in range(20):
        source.move_hand("Right", (0.2 + i * 0.04, 0.5))
        intent = builder.update(source.get_hand_results(), DT)
        if intent.right.swipe is not None:
            swipe_seen = intent.right.swipe
            break

    assert swipe_seen == SwipeDirection.RIGHT


def test_hand_disappearing_briefly_does_not_immediately_report_absent():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))
    _settle_hand_present(builder, source)

    source.hide_hand("Right")
    intent = builder.update([], DT)  # one missing frame
    assert intent.right.present is True  # still within the grace period


def test_hand_disappearing_for_a_long_time_reports_absent():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))
    _settle_hand_present(builder, source)

    source.hide_hand("Right")
    intent = None
    for _ in range(30):  # well past HAND_PRESENCE_GRACE_FRAMES
        intent = builder.update([], DT)
    assert intent.right.present is False


def test_mid_pinch_disappearance_forces_a_release_not_a_stuck_hold():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), pinch=True)
    _settle_hand_present(builder, source)
    # Give the pinch machine time to confirm START/HOLD.
    for _ in range(5):
        intent = builder.update(source.get_hand_results(), DT)

    source.hide_hand("Right")
    intent = builder.update([], DT)  # still within grace period
    assert intent.right.present is True
    assert intent.right.pinch_state == PinchState.RELEASE


def test_two_hand_distance_is_none_unless_both_hands_present():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))
    intent = _settle_hand_present(builder, source)
    assert intent.two_hand_distance is None


def test_two_hand_distance_is_computed_when_both_present():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Left", present=True, position=(0.2, 0.5))
    source.set_hand("Right", present=True, position=(0.8, 0.5))
    intent = _settle_hand_present(builder, source)
    assert intent.left.present and intent.right.present
    assert intent.two_hand_distance is not None
    assert intent.two_hand_distance > 0.0


def test_primary_prefers_right_hand():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Left", present=True, position=(0.5, 0.5))
    source.set_hand("Right", present=True, position=(0.5, 0.5))
    intent = _settle_hand_present(builder, source)
    assert intent.primary().handedness == "Right"


def test_primary_falls_back_to_left_hand():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Left", present=True, position=(0.5, 0.5))
    intent = _settle_hand_present(builder, source)
    assert intent.primary().handedness == "Left"


def test_reset_clears_all_per_hand_state():
    builder = IntentBuilder()
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))
    _settle_hand_present(builder, source)

    builder.reset()
    intent = builder.update([], DT)
    assert intent.right.present is False
