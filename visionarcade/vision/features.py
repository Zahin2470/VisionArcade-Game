"""Stateless geometric feature extraction from raw hand landmarks.

Everything here is a pure function of a single frame's `HandResult` —
no time, no history. Temporal behavior (smoothing, velocity, gesture
state machines) lives in `smoothing.py`, `motion.py`, and `gestures.py`,
which consume these features rather than raw landmarks directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from visionarcade.vision.landmarks import (
    INDEX_FINGER_MCP,
    INDEX_FINGER_TIP,
    MIDDLE_FINGER_MCP,
    MIDDLE_FINGER_TIP,
    PINKY_MCP,
    PINKY_TIP,
    RING_FINGER_MCP,
    RING_FINGER_TIP,
    THUMB_TIP,
    WRIST,
    HandResult,
)

Point = Tuple[float, float]


@dataclass(frozen=True)
class HandFeatures:
    """Normalized, hand-scale-aware geometric features for one hand."""

    handedness: str
    wrist: Point
    palm_center: Point
    index_tip: Point
    pinch_distance: float  # thumb-tip to index-tip distance, scale-normalized
    openness: float  # mean fingertip-to-palm distance, scale-normalized
    score: float


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def extract_hand_features(hand: HandResult) -> HandFeatures:
    """Compute `HandFeatures` for one detected hand.

    Distances are divided by a hand-scale reference length (wrist to
    middle-finger MCP) so pinch/openness are comparable across
    different hand sizes and camera distances, instead of depending on
    raw normalized-image units that shrink as a hand moves further
    from the camera.
    """
    lm = hand.landmarks

    wrist = (lm[WRIST].x, lm[WRIST].y)
    index_tip = (lm[INDEX_FINGER_TIP].x, lm[INDEX_FINGER_TIP].y)
    thumb_tip = (lm[THUMB_TIP].x, lm[THUMB_TIP].y)
    middle_mcp = (lm[MIDDLE_FINGER_MCP].x, lm[MIDDLE_FINGER_MCP].y)

    mcp_points = [
        (lm[INDEX_FINGER_MCP].x, lm[INDEX_FINGER_MCP].y),
        middle_mcp,
        (lm[RING_FINGER_MCP].x, lm[RING_FINGER_MCP].y),
        (lm[PINKY_MCP].x, lm[PINKY_MCP].y),
    ]
    palm_center = (
        (wrist[0] + sum(p[0] for p in mcp_points)) / 5.0,
        (wrist[1] + sum(p[1] for p in mcp_points)) / 5.0,
    )

    hand_scale = max(_distance(wrist, middle_mcp), 1e-6)
    pinch_distance = _distance(thumb_tip, index_tip) / hand_scale

    fingertip_points = [
        index_tip,
        (lm[MIDDLE_FINGER_TIP].x, lm[MIDDLE_FINGER_TIP].y),
        (lm[RING_FINGER_TIP].x, lm[RING_FINGER_TIP].y),
        (lm[PINKY_TIP].x, lm[PINKY_TIP].y),
    ]
    mean_fingertip_distance = sum(_distance(p, palm_center) for p in fingertip_points) / len(
        fingertip_points
    )
    openness = mean_fingertip_distance / hand_scale

    return HandFeatures(
        handedness=hand.handedness,
        wrist=wrist,
        palm_center=palm_center,
        index_tip=index_tip,
        pinch_distance=pinch_distance,
        openness=openness,
        score=hand.score,
    )
