"""Structured representations of MediaPipe hand landmarks.

Downstream code (gestures, features, games) should depend on these
plain dataclasses rather than on MediaPipe's protobuf types directly,
so the tracking backend could be swapped later without touching the
rest of the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

#: Index of each of the 21 MediaPipe hand landmarks, for readability
#: (e.g. `landmarks[INDEX_FINGER_TIP]` instead of `landmarks[8]`).
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_FINGER_MCP = 5
INDEX_FINGER_PIP = 6
INDEX_FINGER_DIP = 7
INDEX_FINGER_TIP = 8
MIDDLE_FINGER_MCP = 9
MIDDLE_FINGER_PIP = 10
MIDDLE_FINGER_DIP = 11
MIDDLE_FINGER_TIP = 12
RING_FINGER_MCP = 13
RING_FINGER_PIP = 14
RING_FINGER_DIP = 15
RING_FINGER_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

NUM_HAND_LANDMARKS = 21


@dataclass(frozen=True)
class HandLandmark:
    """A single landmark in MediaPipe's normalized image coordinates.

    `x` and `y` are in [0, 1] relative to the input frame's width/height
    (0,0 = top-left). `z` is a rough, unitless depth relative to the
    wrist (more negative = closer to the camera).
    """

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class HandResult:
    """One detected hand for a single processed frame."""

    handedness: str  # "Left" or "Right", as reported by MediaPipe
    landmarks: Tuple[HandLandmark, ...]  # length == NUM_HAND_LANDMARKS
    score: float  # handedness classification confidence, in [0, 1]

    def landmark(self, index: int) -> HandLandmark:
        """Convenience accessor, e.g. `hand.landmark(INDEX_FINGER_TIP)`."""
        return self.landmarks[index]
