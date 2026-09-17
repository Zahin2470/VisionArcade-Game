"""Tests for `visionarcade.vision.tracker`.

MediaPipe's Tasks API loads its model from a downloadable `.task` file
rather than one bundled in the pip package, so these tests split into:

  1. Model provisioning (`ensure_hand_landmarker_model`) — tested with
     an injected fake downloader, so no real network call is made.
  2. Result parsing (`HandTracker._parse_results`) — tested against a
     mocked object shaped like a real `HandLandmarkerResult`.
  3. Graceful-failure behavior — tested against the REAL MediaPipe
     backend given a deliberately invalid model file, confirming
     `HandTracker` disables itself instead of raising.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from visionarcade.vision.landmarks import NUM_HAND_LANDMARKS
from visionarcade.vision.tracker import HandTracker, ensure_hand_landmarker_model


# --- Model provisioning ----------------------------------------------------

def test_ensure_model_downloads_when_missing(tmp_path):
    def fake_downloader(url, destination):
        destination.write_bytes(b"fake-model-bytes")

    model_path = ensure_hand_landmarker_model(models_dir=tmp_path, downloader=fake_downloader)
    assert model_path == tmp_path / "hand_landmarker.task"
    assert model_path.read_bytes() == b"fake-model-bytes"


def test_ensure_model_reuses_cached_file_without_downloading(tmp_path):
    cached = tmp_path / "hand_landmarker.task"
    cached.write_bytes(b"already-here")

    calls = []

    def fake_downloader(url, destination):
        calls.append((url, destination))

    model_path = ensure_hand_landmarker_model(models_dir=tmp_path, downloader=fake_downloader)
    assert model_path == cached
    assert calls == []  # cache hit — downloader must not be invoked


def test_ensure_model_returns_none_when_download_fails(tmp_path):
    def failing_downloader(url, destination):
        raise OSError("simulated network failure")

    model_path = ensure_hand_landmarker_model(models_dir=tmp_path, downloader=failing_downloader)
    assert model_path is None


def test_ensure_model_returns_none_when_download_produces_empty_file(tmp_path):
    def empty_downloader(url, destination):
        destination.write_bytes(b"")

    model_path = ensure_hand_landmarker_model(models_dir=tmp_path, downloader=empty_downloader)
    assert model_path is None


# --- Result parsing ----------------------------------------------------------

def _fake_landmarker_result(num_hands: int = 1):
    """Build an object shaped like a real `HandLandmarkerResult`:
    `hand_landmarks: List[List[landmark]]`, `handedness: List[List[category]]`,
    with landmarks exposing `.x/.y/.z` directly (Tasks API shape).
    """
    hand_landmarks_list = []
    handedness_list = []
    for i in range(num_hands):
        landmarks = [
            SimpleNamespace(x=0.1 * j, y=0.2 * j, z=-0.01 * j)
            for j in range(NUM_HAND_LANDMARKS)
        ]
        hand_landmarks_list.append(landmarks)
        category = SimpleNamespace(category_name="Right" if i == 0 else "Left", score=0.95)
        handedness_list.append([category])

    return SimpleNamespace(hand_landmarks=hand_landmarks_list, handedness=handedness_list)


def test_parse_results_builds_correct_hand_results():
    fake_result = _fake_landmarker_result(num_hands=2)
    hands = HandTracker._parse_results(fake_result)

    assert len(hands) == 2
    assert hands[0].handedness == "Right"
    assert hands[1].handedness == "Left"
    assert hands[0].score == pytest.approx(0.95)
    assert len(hands[0].landmarks) == NUM_HAND_LANDMARKS
    assert hands[0].landmarks[1].x == pytest.approx(0.1)


def test_parse_results_handles_no_hands_detected():
    empty_result = SimpleNamespace(hand_landmarks=[], handedness=[])
    assert HandTracker._parse_results(empty_result) == []


def test_parse_results_handles_missing_attributes_gracefully():
    bare_result = SimpleNamespace()  # neither attribute present
    assert HandTracker._parse_results(bare_result) == []


# --- Graceful failure (real MediaPipe, invalid/no model) --------------------

def test_tracker_unavailable_when_model_cannot_be_obtained(tmp_path, monkeypatch):
    # Force provisioning to fail (simulating "no network on first run").
    monkeypatch.setattr(
        "visionarcade.vision.tracker.ensure_hand_landmarker_model",
        lambda *a, **kw: None,
    )
    tracker = HandTracker()
    assert tracker.available is False
    assert tracker.process(np.zeros((10, 10, 3), dtype=np.uint8)) == []
    tracker.close()


def test_tracker_unavailable_with_invalid_model_file(tmp_path):
    bad_model = tmp_path / "hand_landmarker.task"
    bad_model.write_bytes(b"not a real model bundle")

    tracker = HandTracker(model_path=bad_model)  # real MediaPipe call, expected to fail
    assert tracker.available is False
    tracker.close()


def test_process_returns_empty_before_any_init_success():
    tracker = HandTracker.__new__(HandTracker)  # bypass __init__
    tracker._available = False
    tracker._landmarker = None
    assert tracker.process(np.zeros((10, 10, 3), dtype=np.uint8)) == []


def test_process_none_frame_returns_empty_list_when_available():
    tracker = HandTracker.__new__(HandTracker)
    tracker._available = True
    tracker._landmarker = MagicMock()
    assert tracker.process(None) == []


def test_process_survives_backend_exception():
    tracker = HandTracker.__new__(HandTracker)
    tracker._available = True
    tracker._landmarker = MagicMock()
    tracker._landmarker.detect.side_effect = RuntimeError("simulated decode failure")
    tracker._mp_image_factory = lambda rgb: rgb  # identity stand-in

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    assert tracker.process(frame) == []  # must not raise


def test_process_happy_path_with_mocked_backend():
    tracker = HandTracker.__new__(HandTracker)
    tracker._available = True
    tracker._landmarker = MagicMock()
    tracker._landmarker.detect.return_value = _fake_landmarker_result(num_hands=1)
    tracker._mp_image_factory = lambda rgb: rgb

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    hands = tracker.process(frame)
    assert len(hands) == 1
    assert hands[0].handedness == "Right"


def test_close_is_idempotent_and_disables_tracker():
    tracker = HandTracker.__new__(HandTracker)
    tracker._available = True
    tracker._landmarker = MagicMock()
    tracker._mp_image_factory = lambda rgb: rgb

    tracker.close()
    tracker.close()  # must not raise the second time
    assert tracker.available is False


def test_context_manager_does_not_reopen_or_raise():
    tracker = HandTracker.__new__(HandTracker)
    tracker._available = False
    tracker._landmarker = None
    tracker._mp_image_factory = None
    with tracker as t:
        assert t is tracker
    assert tracker.available is False
