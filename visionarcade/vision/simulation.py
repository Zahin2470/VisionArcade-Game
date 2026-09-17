"""A simulated hand input source for developer/debug mode and tests.

`SimulatedHandInputSource` produces `HandResult` objects shaped exactly
like the real `HandTracker` would, so the rest of the pipeline
(features -> smoothing -> gestures -> future game logic) runs through
identical code whether the input is a real camera or this simulator.
This is the "Developer Mode... replace real vision input with
simulated hand positions" requirement, and what lets game logic be
tested deterministically without a webcam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from visionarcade.vision.landmarks import (
    INDEX_FINGER_DIP,
    INDEX_FINGER_MCP,
    INDEX_FINGER_PIP,
    INDEX_FINGER_TIP,
    MIDDLE_FINGER_DIP,
    MIDDLE_FINGER_MCP,
    MIDDLE_FINGER_PIP,
    MIDDLE_FINGER_TIP,
    NUM_HAND_LANDMARKS,
    PINKY_DIP,
    PINKY_MCP,
    PINKY_PIP,
    PINKY_TIP,
    RING_FINGER_DIP,
    RING_FINGER_MCP,
    RING_FINGER_PIP,
    RING_FINGER_TIP,
    THUMB_CMC,
    THUMB_IP,
    THUMB_MCP,
    THUMB_TIP,
    WRIST,
    HandLandmark,
    HandResult,
)

Point = Tuple[float, float]

#: Tuned only to produce plausible, well-separated synthetic geometry
#: for feature extraction to measure — not for visual accuracy.
_OPEN_FINGER_LENGTH = 0.12
_HAND_SIZE = 0.10


@dataclass
class SimulatedHandState:
    """The controllable parameters of one simulated hand."""

    present: bool = False
    position: Point = (0.5, 0.5)  # palm/wrist position, normalized [0, 1]
    pinch: bool = False
    openness: float = 1.0  # 0 (fist) .. 1 (fully open)
    handedness: str = "Right"


class SimulatedHandInputSource:
    """Generates `HandResult` lists from simple, directly-settable
    state instead of running a camera + MediaPipe — a drop-in
    replacement for `HandTracker.process()` from the caller's side.
    """

    def __init__(self) -> None:
        self._hands: Dict[str, SimulatedHandState] = {
            "Left": SimulatedHandState(handedness="Left", present=False),
            "Right": SimulatedHandState(handedness="Right", present=False),
        }

    def set_hand(
        self,
        handedness: str,
        present: bool = True,
        position: Point = (0.5, 0.5),
        pinch: bool = False,
        openness: float = 1.0,
    ) -> None:
        """Set the full state of one simulated hand in a single call."""
        self._hands[handedness] = SimulatedHandState(
            handedness=handedness,
            present=present,
            position=position,
            pinch=pinch,
            openness=max(0.0, min(1.0, openness)),
        )

    def move_hand(self, handedness: str, position: Point) -> None:
        """Move an already-present hand without touching pinch/openness."""
        state = self._hands.get(handedness)
        if state is not None and state.present:
            state.position = position

    def set_pinch(self, handedness: str, pinch: bool) -> None:
        state = self._hands.get(handedness)
        if state is not None:
            state.pinch = pinch

    def set_openness(self, handedness: str, openness: float) -> None:
        state = self._hands.get(handedness)
        if state is not None:
            state.openness = max(0.0, min(1.0, openness))

    def hide_hand(self, handedness: str) -> None:
        state = self._hands.get(handedness)
        if state is not None:
            state.present = False

    def get_position(self, handedness: str) -> Optional[Point]:
        """The current position of a hand, or None if it isn't present."""
        state = self._hands.get(handedness)
        if state is None or not state.present:
            return None
        return state.position

    def is_present(self, handedness: str) -> bool:
        state = self._hands.get(handedness)
        return state is not None and state.present

    def get_hand_results(self) -> List[HandResult]:
        """Return this frame's simulated `HandResult`s, in exactly the
        shape `HandTracker.process()` would produce."""
        return [_synthesize_hand_result(s) for s in self._hands.values() if s.present]


def _synthesize_hand_result(state: SimulatedHandState) -> HandResult:
    x, y = state.position
    finger_length = _OPEN_FINGER_LENGTH * state.openness

    points: List[Optional[HandLandmark]] = [None] * NUM_HAND_LANDMARKS

    def put(index: int, dx: float, dy: float) -> None:
        points[index] = HandLandmark(x=x + dx, y=y + dy, z=0.0)

    put(WRIST, 0.0, 0.0)

    # The four non-thumb fingers extend upward from the palm by
    # `finger_length`, driven entirely by `openness` (0 = curled into
    # the palm, 1 = fully extended) — exactly what `features.py`
    # measures to compute its own openness score.
    for mcp, pip, dip, tip, dx in (
        (INDEX_FINGER_MCP, INDEX_FINGER_PIP, INDEX_FINGER_DIP, INDEX_FINGER_TIP, 0.02),
        (MIDDLE_FINGER_MCP, MIDDLE_FINGER_PIP, MIDDLE_FINGER_DIP, MIDDLE_FINGER_TIP, 0.0),
        (RING_FINGER_MCP, RING_FINGER_PIP, RING_FINGER_DIP, RING_FINGER_TIP, -0.02),
        (PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP, -0.04),
    ):
        put(mcp, dx, -_HAND_SIZE * 0.4)
        put(pip, dx, -_HAND_SIZE * 0.4 - finger_length * 0.4)
        put(dip, dx, -_HAND_SIZE * 0.4 - finger_length * 0.7)
        put(tip, dx, -_HAND_SIZE * 0.4 - finger_length)

    index_tip = points[INDEX_FINGER_TIP]
    assert index_tip is not None  # set by the loop above

    # The thumb is driven entirely by `pinch`: snapped right next to
    # the index fingertip when pinching, held well away from it
    # otherwise — exactly what `features.py` measures as pinch distance.
    put(THUMB_CMC, -0.02, -0.02)
    put(THUMB_MCP, -0.04, -0.03)
    if state.pinch:
        points[THUMB_IP] = HandLandmark(
            x=index_tip.x - 0.01, y=index_tip.y + 0.01, z=0.0
        )
        points[THUMB_TIP] = HandLandmark(
            x=index_tip.x + 0.004, y=index_tip.y + 0.004, z=0.0
        )
    else:
        put(THUMB_IP, -0.07, -0.02)
        put(THUMB_TIP, -0.09, 0.0)

    landmarks = tuple(points)  # type: ignore[arg-type]  # fully populated above
    return HandResult(handedness=state.handedness, landmarks=landmarks, score=1.0)
