"""Tests for `visionarcade.vision.features`."""

from __future__ import annotations

import pytest

from visionarcade.vision.features import extract_hand_features
from visionarcade.vision.landmarks import (
    INDEX_FINGER_MCP,
    INDEX_FINGER_TIP,
    MIDDLE_FINGER_MCP,
    MIDDLE_FINGER_TIP,
    NUM_HAND_LANDMARKS,
    PINKY_MCP,
    PINKY_TIP,
    RING_FINGER_MCP,
    RING_FINGER_TIP,
    THUMB_TIP,
    WRIST,
    HandLandmark,
    HandResult,
)


def _build_hand(overrides: dict) -> HandResult:
    """Build a HandResult with all 21 landmarks at the origin, except
    for the indices given in `overrides`."""
    landmarks = [HandLandmark(x=0.0, y=0.0, z=0.0) for _ in range(NUM_HAND_LANDMARKS)]
    for index, (x, y) in overrides.items():
        landmarks[index] = HandLandmark(x=x, y=y, z=0.0)
    return HandResult(handedness="Right", landmarks=tuple(landmarks), score=0.9)


def test_wrist_and_index_tip_pass_through_directly():
    hand = _build_hand(
        {
            WRIST: (0.5, 0.5),
            INDEX_FINGER_TIP: (0.6, 0.4),
            MIDDLE_FINGER_MCP: (0.5, 0.4),  # nonzero hand scale
        }
    )
    features = extract_hand_features(hand)
    assert features.wrist == (0.5, 0.5)
    assert features.index_tip == (0.6, 0.4)
    assert features.handedness == "Right"
    assert features.score == pytest.approx(0.9)


def test_pinch_distance_is_small_when_thumb_and_index_close():
    hand = _build_hand(
        {
            WRIST: (0.5, 0.5),
            MIDDLE_FINGER_MCP: (0.5, 0.4),  # hand_scale = 0.1
            THUMB_TIP: (0.60, 0.40),
            INDEX_FINGER_TIP: (0.601, 0.401),  # nearly touching the thumb
        }
    )
    features = extract_hand_features(hand)
    assert features.pinch_distance < 0.05


def test_pinch_distance_is_large_when_thumb_and_index_far_apart():
    hand = _build_hand(
        {
            WRIST: (0.5, 0.5),
            MIDDLE_FINGER_MCP: (0.5, 0.4),  # hand_scale = 0.1
            THUMB_TIP: (0.3, 0.3),
            INDEX_FINGER_TIP: (0.7, 0.7),
        }
    )
    features = extract_hand_features(hand)
    assert features.pinch_distance > 2.0


def test_openness_is_low_when_fingertips_are_near_palm_center():
    # All fingertips coincide with their MCPs (a "fist"): fingertip-to-
    # palm-center distance should be small relative to hand scale.
    hand = _build_hand(
        {
            WRIST: (0.5, 0.5),
            INDEX_FINGER_MCP: (0.52, 0.42),
            MIDDLE_FINGER_MCP: (0.50, 0.40),
            RING_FINGER_MCP: (0.48, 0.42),
            PINKY_MCP: (0.46, 0.44),
            INDEX_FINGER_TIP: (0.52, 0.42),
            MIDDLE_FINGER_TIP: (0.50, 0.40),
            RING_FINGER_TIP: (0.48, 0.42),
            PINKY_TIP: (0.46, 0.44),
        }
    )
    fist_features = extract_hand_features(hand)

    open_hand = _build_hand(
        {
            WRIST: (0.5, 0.5),
            INDEX_FINGER_MCP: (0.52, 0.42),
            MIDDLE_FINGER_MCP: (0.50, 0.40),
            RING_FINGER_MCP: (0.48, 0.42),
            PINKY_MCP: (0.46, 0.44),
            INDEX_FINGER_TIP: (0.62, 0.22),
            MIDDLE_FINGER_TIP: (0.50, 0.15),
            RING_FINGER_TIP: (0.38, 0.22),
            PINKY_TIP: (0.30, 0.30),
        }
    )
    open_features = extract_hand_features(open_hand)

    assert fist_features.openness < open_features.openness


def test_degenerate_hand_scale_does_not_raise_or_divide_by_zero():
    # Wrist and middle MCP coincide -> hand_scale would be zero without
    # the epsilon floor in extract_hand_features.
    hand = _build_hand(
        {
            WRIST: (0.5, 0.5),
            MIDDLE_FINGER_MCP: (0.5, 0.5),
            THUMB_TIP: (0.5, 0.5),
            INDEX_FINGER_TIP: (0.5, 0.5),
        }
    )
    features = extract_hand_features(hand)  # must not raise
    assert features.pinch_distance == pytest.approx(0.0)
