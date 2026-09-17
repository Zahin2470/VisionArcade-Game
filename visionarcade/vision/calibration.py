"""First-run calibration: personalizes the coordinate mapping to the
player's actual reach.

`CalibrationData` remaps a hand's raw normalized camera position into
the arcade's logical [0, 1] interaction space using the range the
player actually moved through during calibration, so someone with a
smaller comfortable movement range still reaches the full screen
rather than being stuck in the camera's center.

The game must remain fully usable even if calibration was skipped or
came out degenerate (e.g. the player barely moved) — `CalibrationData`
always falls back to sane defaults instead of producing an unusable
mapping. `CalibrationSession` (below) only contains the *logic* of
walking through the calibration steps; presenting the guide box and
instructions visually is `ui/calibration.py`'s job in a later phase.
"""

from __future__ import annotations

import enum
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Tuple

from visionarcade.constants import (
    CALIBRATION_DEFAULT_X_MAX,
    CALIBRATION_DEFAULT_X_MIN,
    CALIBRATION_DEFAULT_Y_MAX,
    CALIBRATION_DEFAULT_Y_MIN,
    CALIBRATION_FILE_NAME,
    CALIBRATION_MOVE_PHASE_SECONDS,
    CALIBRATION_STEP_HOLD_SECONDS,
    OPENNESS_FIST_THRESHOLD,
    PINCH_ENTER_DISTANCE,
)
from visionarcade.utils.paths import get_user_data_dir
from visionarcade.vision.features import Point, extract_hand_features
from visionarcade.vision.landmarks import HandResult
from visionarcade.vision.motion import MotionTracker

logger = logging.getLogger(__name__)

_MIN_AXIS_RANGE = 0.05  # below this, an observed calibration range is degenerate


@dataclass(frozen=True)
class CalibrationData:
    """A personalized coordinate mapping produced by calibration."""

    x_min: float = CALIBRATION_DEFAULT_X_MIN
    x_max: float = CALIBRATION_DEFAULT_X_MAX
    y_min: float = CALIBRATION_DEFAULT_Y_MIN
    y_max: float = CALIBRATION_DEFAULT_Y_MAX
    calibrated: bool = False

    @staticmethod
    def default() -> "CalibrationData":
        """A sane, generic mapping used before calibration ever runs, or
        if calibration was skipped/failed."""
        return CalibrationData()

    def remap(self, point: Point) -> Point:
        """Remap a raw normalized camera-space point into [0, 1] arcade
        space, clamped so values outside the calibrated range stay in
        bounds instead of driving a game object off-screen."""
        return (
            _remap_axis(point[0], self.x_min, self.x_max),
            _remap_axis(point[1], self.y_min, self.y_max),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "CalibrationData":
        return CalibrationData(
            x_min=float(data.get("x_min", CALIBRATION_DEFAULT_X_MIN)),
            x_max=float(data.get("x_max", CALIBRATION_DEFAULT_X_MAX)),
            y_min=float(data.get("y_min", CALIBRATION_DEFAULT_Y_MIN)),
            y_max=float(data.get("y_max", CALIBRATION_DEFAULT_Y_MAX)),
            calibrated=bool(data.get("calibrated", False)),
        )


def _remap_axis(value: float, axis_min: float, axis_max: float) -> float:
    span = axis_max - axis_min
    if span < _MIN_AXIS_RANGE:
        return max(0.0, min(1.0, value))  # degenerate calibration: fall back to the raw value
    return max(0.0, min(1.0, (value - axis_min) / span))


def _calibration_path(path: Optional[Path] = None) -> Path:
    return path if path is not None else (get_user_data_dir() / CALIBRATION_FILE_NAME)


def load_calibration(path: Optional[Path] = None) -> CalibrationData:
    """Load calibration data, falling back to defaults on any problem
    (missing file, corrupted JSON, wrong types) rather than raising."""
    resolved_path = _calibration_path(path)
    if not resolved_path.exists():
        return CalibrationData.default()

    try:
        raw = json.loads(resolved_path.read_text(encoding="utf-8"))
        return CalibrationData.from_dict(raw)
    except Exception as exc:  # noqa: BLE001 - a bad save file must not crash the app
        logger.warning(
            "Could not read calibration file '%s' (%s). Using defaults.", resolved_path, exc
        )
        return CalibrationData.default()


def save_calibration(data: CalibrationData, path: Optional[Path] = None) -> bool:
    """Save calibration data atomically. Returns True/False; never raises."""
    resolved_path = _calibration_path(path)
    tmp_path = resolved_path.with_suffix(resolved_path.suffix + ".tmp")
    try:
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(data.to_dict(), indent=2), encoding="utf-8")
        tmp_path.replace(resolved_path)
        return True
    except Exception as exc:  # noqa: BLE001 - disk I/O must not crash the app
        logger.error("Could not save calibration file '%s': %s", resolved_path, exc)
        return False


class CalibrationStep(enum.Enum):
    PLACE_HAND = "place_hand"
    MOVE_RANGE = "move_range"
    PINCH = "pinch"
    OPEN_PALM = "open_palm"
    SWIPE = "swipe"
    DONE = "done"


_STEP_ORDER: Tuple[CalibrationStep, ...] = (
    CalibrationStep.PLACE_HAND,
    CalibrationStep.MOVE_RANGE,
    CalibrationStep.PINCH,
    CalibrationStep.OPEN_PALM,
    CalibrationStep.SWIPE,
    CalibrationStep.DONE,
)

_STEP_INSTRUCTIONS = {
    CalibrationStep.PLACE_HAND: "Place your hand inside the guide.",
    CalibrationStep.MOVE_RANGE: "Move your hand around comfortably: left, right, up, down.",
    CalibrationStep.PINCH: "Pinch your thumb and index finger together.",
    CalibrationStep.OPEN_PALM: "Open your palm wide.",
    CalibrationStep.SWIPE: "Perform a short swipe.",
    CalibrationStep.DONE: "Calibration complete!",
}


class CalibrationSession:
    """Walks the player through first-run calibration and produces a
    `CalibrationData` at the end.

    Driven purely by `update(hand, dt)` calls, so it can be unit tested
    with synthetic hand features (or the Phase 2 hand simulator) and no
    rendering or real camera at all.
    """

    def __init__(
        self,
        move_phase_seconds: float = CALIBRATION_MOVE_PHASE_SECONDS,
        step_hold_seconds: float = CALIBRATION_STEP_HOLD_SECONDS,
    ) -> None:
        self.move_phase_seconds = move_phase_seconds
        self.step_hold_seconds = step_hold_seconds

        self._step_index = 0
        self._step_elapsed = 0.0
        self._hold_elapsed = 0.0

        self._x_min: Optional[float] = None
        self._x_max: Optional[float] = None
        self._y_min: Optional[float] = None
        self._y_max: Optional[float] = None
        self._pinch_observed = False
        self._open_palm_observed = False
        self._swipe_observed = False

        self._motion_tracker = MotionTracker()
        self._result: Optional[CalibrationData] = None

    @property
    def step(self) -> CalibrationStep:
        return _STEP_ORDER[self._step_index]

    @property
    def instruction(self) -> str:
        return _STEP_INSTRUCTIONS[self.step]

    @property
    def is_done(self) -> bool:
        return self.step is CalibrationStep.DONE

    @property
    def result(self) -> Optional[CalibrationData]:
        return self._result

    def update(self, hand: Optional[HandResult], dt: float) -> CalibrationStep:
        """Advance the session by one frame given the primary detected
        hand (or None if no hand is visible this frame)."""
        if self.is_done:
            return self.step

        self._step_elapsed += dt
        features = extract_hand_features(hand) if hand is not None else None
        step = self.step

        if step is CalibrationStep.PLACE_HAND:
            if features is not None:
                self._hold_elapsed += dt
                if self._hold_elapsed >= self.step_hold_seconds:
                    self._advance()
            else:
                self._hold_elapsed = 0.0

        elif step is CalibrationStep.MOVE_RANGE:
            if features is not None:
                self._observe_range(features.palm_center)
            if self._step_elapsed >= self.move_phase_seconds:
                self._advance()

        elif step is CalibrationStep.PINCH:
            if features is not None and features.pinch_distance < PINCH_ENTER_DISTANCE:
                self._pinch_observed = True
                self._hold_elapsed += dt
            else:
                self._hold_elapsed = 0.0
            if self._pinch_observed and self._hold_elapsed >= self.step_hold_seconds:
                self._advance()

        elif step is CalibrationStep.OPEN_PALM:
            if features is not None and features.openness > OPENNESS_FIST_THRESHOLD * 1.4:
                self._open_palm_observed = True
                self._hold_elapsed += dt
            else:
                self._hold_elapsed = 0.0
            if self._open_palm_observed and self._hold_elapsed >= self.step_hold_seconds:
                self._advance()

        elif step is CalibrationStep.SWIPE:
            if features is not None:
                self._motion_tracker.update(features.palm_center, dt)
                if self._motion_tracker.detect_swipe() is not None:
                    self._swipe_observed = True
            if self._swipe_observed:
                self._advance()

        if self.is_done and self._result is None:
            self._result = self._build_result()

        return self.step

    def _observe_range(self, point: Point) -> None:
        x, y = point
        self._x_min = x if self._x_min is None else min(self._x_min, x)
        self._x_max = x if self._x_max is None else max(self._x_max, x)
        self._y_min = y if self._y_min is None else min(self._y_min, y)
        self._y_max = y if self._y_max is None else max(self._y_max, y)

    def _advance(self) -> None:
        self._step_index = min(self._step_index + 1, len(_STEP_ORDER) - 1)
        self._step_elapsed = 0.0
        self._hold_elapsed = 0.0

    def _build_result(self) -> CalibrationData:
        if (
            self._x_min is None
            or self._x_max is None
            or (self._x_max - self._x_min) < _MIN_AXIS_RANGE
        ):
            x_min, x_max = CALIBRATION_DEFAULT_X_MIN, CALIBRATION_DEFAULT_X_MAX
        else:
            x_min, x_max = self._x_min, self._x_max

        if (
            self._y_min is None
            or self._y_max is None
            or (self._y_max - self._y_min) < _MIN_AXIS_RANGE
        ):
            y_min, y_max = CALIBRATION_DEFAULT_Y_MIN, CALIBRATION_DEFAULT_Y_MAX
        else:
            y_min, y_max = self._y_min, self._y_max

        return CalibrationData(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max, calibrated=True)

    def skip(self) -> CalibrationData:
        """Abandon calibration early and fall back to defaults — backs
        the "skip calibration" affordance a later phase's hub UI exposes."""
        self._result = CalibrationData.default()
        self._step_index = len(_STEP_ORDER) - 1
        return self._result
