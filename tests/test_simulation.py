"""Tests for `visionarcade.vision.simulation`.

These confirm the synthetic landmarks produced by `SimulatedHandInputSource`
are realistic enough that `features.py` and the real gesture thresholds
in `constants.py` classify them the same way a real hand would — which
is what makes the simulator usable for exercising the rest of the
pipeline in Developer Mode and in tests.
"""

from __future__ import annotations

from visionarcade.constants import OPENNESS_FIST_THRESHOLD, PINCH_ENTER_DISTANCE, PINCH_EXIT_DISTANCE
from visionarcade.vision.features import extract_hand_features
from visionarcade.vision.landmarks import NUM_HAND_LANDMARKS
from visionarcade.vision.simulation import SimulatedHandInputSource


def test_no_hands_by_default():
    source = SimulatedHandInputSource()
    assert source.get_hand_results() == []


def test_set_hand_makes_it_present():
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5))
    results = source.get_hand_results()
    assert len(results) == 1
    assert results[0].handedness == "Right"
    assert len(results[0].landmarks) == NUM_HAND_LANDMARKS


def test_hidden_hand_is_not_in_results():
    source = SimulatedHandInputSource()
    source.set_hand("Left", present=True)
    source.hide_hand("Left")
    assert source.get_hand_results() == []


def test_both_hands_can_be_present_simultaneously():
    source = SimulatedHandInputSource()
    source.set_hand("Left", present=True, position=(0.2, 0.5))
    source.set_hand("Right", present=True, position=(0.8, 0.5))
    results = source.get_hand_results()
    assert {r.handedness for r in results} == {"Left", "Right"}


def test_pinch_true_yields_a_closed_pinch_distance():
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), pinch=True)
    hand = source.get_hand_results()[0]
    features = extract_hand_features(hand)
    assert features.pinch_distance < PINCH_ENTER_DISTANCE


def test_pinch_false_yields_an_open_pinch_distance():
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), pinch=False, openness=1.0)
    hand = source.get_hand_results()[0]
    features = extract_hand_features(hand)
    assert features.pinch_distance > PINCH_EXIT_DISTANCE


def test_high_openness_exceeds_fist_threshold():
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), openness=1.0, pinch=False)
    hand = source.get_hand_results()[0]
    features = extract_hand_features(hand)
    assert features.openness > OPENNESS_FIST_THRESHOLD


def test_low_openness_is_below_fist_threshold():
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.5, 0.5), openness=0.0, pinch=False)
    hand = source.get_hand_results()[0]
    features = extract_hand_features(hand)
    assert features.openness < OPENNESS_FIST_THRESHOLD


def test_move_hand_updates_position_of_a_present_hand():
    source = SimulatedHandInputSource()
    source.set_hand("Right", present=True, position=(0.2, 0.2))
    source.move_hand("Right", (0.9, 0.1))
    hand = source.get_hand_results()[0]
    features = extract_hand_features(hand)
    assert features.wrist == (0.9, 0.1)


def test_move_hand_on_absent_hand_is_a_safe_no_op():
    source = SimulatedHandInputSource()
    source.move_hand("Right", (0.9, 0.1))  # never set_hand'd -> not present
    assert source.get_hand_results() == []


def test_get_position_and_is_present_accessors():
    source = SimulatedHandInputSource()
    assert source.is_present("Left") is False
    assert source.get_position("Left") is None

    source.set_hand("Left", present=True, position=(0.3, 0.4))
    assert source.is_present("Left") is True
    assert source.get_position("Left") == (0.3, 0.4)
