"""Gesture/intent layer: turns smoothed features into stabilized,
game-ready intent.

Implements the project's core interaction principle:

    raw detection -> stabilized intent -> game action

No single noisy frame can trigger a game action here — pinch state
requires hysteresis + hold confirmation, hand presence requires a
grace period before "disappearing", and swipes require sustained
motion over a short window (see `smoothing.py` and `motion.py`).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from visionarcade.constants import (
    HAND_PRESENCE_CONFIRM_FRAMES,
    HAND_PRESENCE_GRACE_FRAMES,
    OPENNESS_FIST_THRESHOLD,
    PINCH_ENTER_DISTANCE,
    PINCH_EXIT_DISTANCE,
    PINCH_MIN_HOLD_FRAMES,
)
from visionarcade.vision.calibration import CalibrationData
from visionarcade.vision.features import Point, extract_hand_features
from visionarcade.vision.landmarks import HandResult
from visionarcade.vision.motion import MotionTracker, SwipeDirection
from visionarcade.vision.smoothing import ExponentialSmoother, HysteresisGate, PointSmoother

KNOWN_HANDEDNESS: Tuple[str, ...] = ("Left", "Right")


class PinchState(enum.Enum):
    NONE = "none"  # not pinching, and wasn't last frame
    START = "start"  # just transitioned into a pinch this frame
    HOLD = "hold"  # continuing an existing pinch
    RELEASE = "release"  # just transitioned out of a pinch this frame


class PinchStateMachine:
    """Hysteresis + hold-confirmation state machine for pinch gestures.

    Separate enter/exit distance thresholds mean a pinch distance
    hovering near one boundary can't flicker START/RELEASE every other
    frame, and `min_hold_frames` requires a pinch to stay closed for a
    few consecutive frames before it's confirmed as a real START.
    """

    def __init__(
        self,
        enter_distance: float = PINCH_ENTER_DISTANCE,
        exit_distance: float = PINCH_EXIT_DISTANCE,
        min_hold_frames: int = PINCH_MIN_HOLD_FRAMES,
    ) -> None:
        self.enter_distance = enter_distance
        self.exit_distance = exit_distance
        self.min_hold_frames = max(1, min_hold_frames)

        self._closed = False
        self._pending_closed_frames = 0
        self._state = PinchState.NONE

    @property
    def state(self) -> PinchState:
        return self._state

    def reset(self) -> None:
        self._closed = False
        self._pending_closed_frames = 0
        self._state = PinchState.NONE

    def update(self, pinch_distance: float) -> PinchState:
        is_closed_now = (
            pinch_distance < self.exit_distance
            if self._closed
            else pinch_distance < self.enter_distance
        )

        if is_closed_now and not self._closed:
            self._pending_closed_frames += 1
            if self._pending_closed_frames >= self.min_hold_frames:
                self._closed = True
                self._pending_closed_frames = 0
                self._state = PinchState.START
            else:
                self._state = PinchState.NONE
        elif is_closed_now and self._closed:
            self._state = PinchState.HOLD
        elif not is_closed_now and self._closed:
            self._closed = False
            self._pending_closed_frames = 0
            self._state = PinchState.RELEASE
        else:
            self._pending_closed_frames = 0
            self._state = PinchState.NONE

        return self._state

    def force_release_if_active(self) -> Optional[PinchState]:
        """Called when a hand disappears mid-pinch, so lost tracking
        can't leave a game thinking a pinch is held forever."""
        if self._closed:
            self._closed = False
            self._pending_closed_frames = 0
            self._state = PinchState.RELEASE
            return self._state
        return None


def _pinch_strength(pinch_distance: float, machine: PinchStateMachine) -> float:
    """Map a raw pinch distance to a 0..1 "closedness" strength, for UI
    feedback like a pinch progress ring."""
    span = max(machine.exit_distance, 1e-6)
    strength = 1.0 - (pinch_distance / span)
    return max(0.0, min(1.0, strength))


@dataclass(frozen=True)
class HandIntent:
    """Stabilized, game-ready state for one hand (or its absence)."""

    handedness: str
    present: bool
    position: Optional[Point] = None  # smoothed palm center, calibrated to [0, 1]
    index_tip: Optional[Point] = None  # smoothed index fingertip, calibrated to [0, 1]
    velocity: Point = (0.0, 0.0)
    pinch_state: PinchState = PinchState.NONE
    pinch_strength: float = 0.0  # 0 (open) .. 1 (fully closed)
    openness: float = 0.0
    is_fist: bool = False
    swipe: Optional[SwipeDirection] = None

    @staticmethod
    def absent(handedness: str) -> "HandIntent":
        return HandIntent(handedness=handedness, present=False)


@dataclass(frozen=True)
class FrameIntent:
    """The full stabilized interaction state for a single frame."""

    left: HandIntent
    right: HandIntent
    two_hand_distance: Optional[float] = None  # normalized distance between palms

    @property
    def any_hand_present(self) -> bool:
        return self.left.present or self.right.present

    def primary(self) -> HandIntent:
        """The hand a single-hand game should use: right hand
        preferred, falling back to the left."""
        return self.right if self.right.present else self.left


class _PerHandState:
    """Mutable per-hand temporal state, private to `IntentBuilder`."""

    def __init__(self, handedness: str) -> None:
        self.handedness = handedness
        self.presence_gate = HysteresisGate(
            enter_frames=HAND_PRESENCE_CONFIRM_FRAMES,
            exit_frames=HAND_PRESENCE_GRACE_FRAMES,
        )
        self.position_smoother = PointSmoother()
        self.index_smoother = PointSmoother()
        self.pinch_distance_smoother = ExponentialSmoother()
        self.openness_smoother = ExponentialSmoother()
        self.motion_tracker = MotionTracker()
        self.pinch_machine = PinchStateMachine()
        self.last_intent: HandIntent = HandIntent.absent(handedness)


class IntentBuilder:
    """Turns per-frame `HandResult`s into a stabilized `FrameIntent`.

    The only place that owns per-hand temporal state — everything
    upstream (`features.py`) is stateless, and everything downstream
    (future game modules) only ever sees the resulting `FrameIntent`,
    never raw landmarks. This is what lets simulated input
    (`vision/simulation.py`) exercise the exact same downstream code
    path as a real camera.
    """

    def __init__(self, calibration: Optional[CalibrationData] = None) -> None:
        self.calibration = calibration if calibration is not None else CalibrationData.default()
        self._states: Dict[str, _PerHandState] = {
            name: _PerHandState(name) for name in KNOWN_HANDEDNESS
        }

    def set_calibration(self, calibration: CalibrationData) -> None:
        self.calibration = calibration

    def reset(self) -> None:
        for name in KNOWN_HANDEDNESS:
            self._states[name] = _PerHandState(name)

    def update(self, hand_results: List[HandResult], dt: float) -> FrameIntent:
        raw_by_hand: Dict[str, HandResult] = {}
        for hand in hand_results:
            if hand.handedness in KNOWN_HANDEDNESS and hand.handedness not in raw_by_hand:
                raw_by_hand[hand.handedness] = hand

        intents = {
            name: self._update_one_hand(self._states[name], raw_by_hand.get(name), dt)
            for name in KNOWN_HANDEDNESS
        }

        two_hand_distance = None
        left, right = intents["Left"], intents["Right"]
        if left.present and right.present and left.position and right.position:
            dx = left.position[0] - right.position[0]
            dy = left.position[1] - right.position[1]
            two_hand_distance = (dx**2 + dy**2) ** 0.5

        return FrameIntent(left=left, right=right, two_hand_distance=two_hand_distance)

    def _update_one_hand(
        self, state: _PerHandState, raw_hand: Optional[HandResult], dt: float
    ) -> HandIntent:
        stable_present = state.presence_gate.update(raw_hand is not None)

        if raw_hand is not None:
            return self._update_with_detection(state, raw_hand, dt, stable_present)
        if stable_present:
            return self._update_within_grace_period(state)
        return self._update_fully_absent(state)

    def _update_with_detection(
        self, state: _PerHandState, raw_hand: HandResult, dt: float, stable_present: bool
    ) -> HandIntent:
        features = extract_hand_features(raw_hand)
        calibrated_position = self.calibration.remap(features.palm_center)
        calibrated_index = self.calibration.remap(features.index_tip)

        smoothed_position = state.position_smoother.update(calibrated_position, dt)
        smoothed_index = state.index_smoother.update(calibrated_index, dt)
        smoothed_pinch_distance = state.pinch_distance_smoother.update(features.pinch_distance, dt)
        smoothed_openness = state.openness_smoother.update(features.openness, dt)

        velocity = state.motion_tracker.update(smoothed_position, dt)
        swipe = state.motion_tracker.detect_swipe()
        pinch_state = state.pinch_machine.update(smoothed_pinch_distance)

        intent = HandIntent(
            handedness=state.handedness,
            present=stable_present,
            position=smoothed_position,
            index_tip=smoothed_index,
            velocity=velocity,
            pinch_state=pinch_state,
            pinch_strength=_pinch_strength(smoothed_pinch_distance, state.pinch_machine),
            openness=smoothed_openness,
            is_fist=smoothed_openness < OPENNESS_FIST_THRESHOLD,
            swipe=swipe,
        )
        state.last_intent = intent
        return intent

    def _update_within_grace_period(self, state: _PerHandState) -> HandIntent:
        # Hold position steady and report no motion/swipe, but don't
        # let a lost pinch lock stay "held" forever while the hand is
        # merely out of frame for a moment.
        forced_release = state.pinch_machine.force_release_if_active()
        last = state.last_intent
        intent = HandIntent(
            handedness=state.handedness,
            present=True,
            position=last.position,
            index_tip=last.index_tip,
            velocity=(0.0, 0.0),
            pinch_state=forced_release if forced_release is not None else PinchState.NONE,
            pinch_strength=0.0 if forced_release is not None else last.pinch_strength,
            openness=last.openness,
            is_fist=last.is_fist,
            swipe=None,
        )
        state.last_intent = intent
        return intent

    def _update_fully_absent(self, state: _PerHandState) -> HandIntent:
        # Reset temporal state so a later re-detection starts clean
        # rather than resuming stale motion history or a stuck pinch.
        state.motion_tracker.reset()
        state.pinch_machine.reset()
        state.position_smoother.reset()
        state.index_smoother.reset()
        state.pinch_distance_smoother.reset()
        state.openness_smoother.reset()
        intent = HandIntent.absent(state.handedness)
        state.last_intent = intent
        return intent
