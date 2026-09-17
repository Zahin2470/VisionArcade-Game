"""Tests for `visionarcade.vision.camera.CameraService`.

The real webcam is mocked throughout — these tests verify the service's
own logic (retries, graceful failure, frame-loss bookkeeping), not
OpenCV or actual hardware.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from visionarcade.constants import CAMERA_READ_MAX_CONSECUTIVE_FAILURES
from visionarcade.vision.camera import CameraService


def _mock_capture(is_opened: bool = True, read_returns=(True, None)) -> MagicMock:
    capture = MagicMock()
    capture.isOpened.return_value = is_opened
    if read_returns[1] is None and read_returns[0]:
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        capture.read.return_value = (True, frame)
    else:
        capture.read.return_value = read_returns
    return capture


def test_open_succeeds_when_device_available():
    with patch("cv2.VideoCapture", return_value=_mock_capture(is_opened=True)):
        camera = CameraService(camera_index=0)
        assert camera.open() is True
        assert camera.is_open is True
        camera.close()


def test_open_fails_gracefully_when_device_unavailable():
    with patch("cv2.VideoCapture", return_value=_mock_capture(is_opened=False)):
        camera = CameraService(camera_index=5, max_open_retries=1)
        assert camera.open() is False
        assert camera.is_open is False


def test_open_does_not_raise_when_backend_throws():
    with patch("cv2.VideoCapture", side_effect=RuntimeError("device busy")):
        camera = CameraService(camera_index=0, max_open_retries=0)
        assert camera.open() is False  # must not raise


def test_read_frame_returns_none_before_open():
    camera = CameraService()
    assert camera.read_frame() is None


def test_read_frame_returns_frame_when_available():
    with patch("cv2.VideoCapture", return_value=_mock_capture(is_opened=True)):
        camera = CameraService()
        camera.open()
        frame = camera.read_frame()
        assert isinstance(frame, np.ndarray)
        camera.close()


def test_read_frame_returns_none_on_transient_failure_without_closing():
    mock_cap = _mock_capture(is_opened=True, read_returns=(False, None))
    with patch("cv2.VideoCapture", return_value=mock_cap):
        camera = CameraService()
        camera.open()
        for _ in range(5):
            assert camera.read_frame() is None
        assert camera.is_open is True  # a few dropped frames must not close the camera
        assert camera.consecutive_read_failures == 5
        camera.close()


def test_consecutive_failure_counter_resets_on_success():
    mock_cap = _mock_capture(is_opened=True, read_returns=(False, None))
    with patch("cv2.VideoCapture", return_value=mock_cap):
        camera = CameraService()
        camera.open()
        camera.read_frame()
        assert camera.consecutive_read_failures == 1

        mock_cap.read.return_value = (True, np.zeros((4, 4, 3), dtype=np.uint8))
        camera.read_frame()
        assert camera.consecutive_read_failures == 0
        camera.close()


def test_close_is_idempotent():
    camera = CameraService()
    camera.close()
    camera.close()
    assert camera.is_open is False


def test_retry_reopens_camera():
    with patch("cv2.VideoCapture", return_value=_mock_capture(is_opened=True)):
        camera = CameraService()
        camera.open()
        assert camera.retry() is True
        camera.close()


def test_context_manager_opens_and_closes():
    with patch("cv2.VideoCapture", return_value=_mock_capture(is_opened=True)):
        with CameraService() as camera:
            assert camera.is_open is True
        assert camera.is_open is False


def test_max_consecutive_failures_constant_is_positive():
    # Sanity check on the tunable constant used for UI warnings later.
    assert CAMERA_READ_MAX_CONSECUTIVE_FAILURES > 0
