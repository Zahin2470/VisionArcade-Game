"""Webcam capture service.

Every failure mode here (camera missing, camera busy, camera dropping
frames mid-session) must be handled without raising into the caller's
main loop — the arcade should degrade gracefully, never crash, when a
camera is unavailable or briefly loses frames.
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

from visionarcade.constants import (
    CAMERA_OPEN_MAX_RETRIES,
    CAMERA_READ_MAX_CONSECUTIVE_FAILURES,
    DEFAULT_CAMERA_FRAME_HEIGHT,
    DEFAULT_CAMERA_FRAME_WIDTH,
    DEFAULT_CAMERA_INDEX,
)

logger = logging.getLogger(__name__)


class CameraError(Exception):
    """Raised only for programmer-error cases (e.g. reading before opening).

    Runtime hardware failures (camera missing/busy) are NOT raised as
    exceptions — they are reported via return values so the caller can
    degrade gracefully, per the project's error-handling requirements.
    """


class CameraService:
    """Thin, defensive wrapper around `cv2.VideoCapture`.

    Usage:
        camera = CameraService(camera_index=0)
        if camera.open():
            frame = camera.read_frame()  # np.ndarray (BGR) or None
        camera.close()
    """

    def __init__(
        self,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        frame_width: int = DEFAULT_CAMERA_FRAME_WIDTH,
        frame_height: int = DEFAULT_CAMERA_FRAME_HEIGHT,
        max_open_retries: int = CAMERA_OPEN_MAX_RETRIES,
    ) -> None:
        self.camera_index = camera_index
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.max_open_retries = max_open_retries

        self._capture: Optional[cv2.VideoCapture] = None
        self._is_open: bool = False
        self._consecutive_read_failures: int = 0

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def consecutive_read_failures(self) -> int:
        return self._consecutive_read_failures

    def open(self) -> bool:
        """Attempt to open the configured camera.

        Returns True on success, False on failure — never raises for
        hardware-related problems. Retries up to `max_open_retries` times
        in case the device is transiently busy.
        """
        if self._is_open:
            return True

        attempts = max(1, self.max_open_retries + 1)
        for attempt in range(1, attempts + 1):
            try:
                capture = cv2.VideoCapture(self.camera_index)
                if capture is not None and capture.isOpened():
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
                    self._capture = capture
                    self._is_open = True
                    self._consecutive_read_failures = 0
                    logger.info(
                        "Camera %s opened (attempt %d/%d).",
                        self.camera_index,
                        attempt,
                        attempts,
                    )
                    return True
                if capture is not None:
                    capture.release()
            except Exception as exc:  # noqa: BLE001 - hardware I/O, must not propagate
                logger.warning(
                    "Camera %s failed to open on attempt %d/%d: %s",
                    self.camera_index,
                    attempt,
                    attempts,
                    exc,
                )

        logger.warning(
            "Camera %s is unavailable after %d attempt(s). "
            "Continuing without live video.",
            self.camera_index,
            attempts,
        )
        self._is_open = False
        self._capture = None
        return False

    def read_frame(self) -> Optional[np.ndarray]:
        """Read one BGR frame, or None if unavailable/temporarily lost.

        A None return does not close the camera — occasional dropped
        frames are expected and must not crash the game loop. Callers
        can inspect `consecutive_read_failures` to decide whether to
        prompt the player to check their camera.
        """
        if not self._is_open or self._capture is None:
            return None

        try:
            success, frame = self._capture.read()
        except Exception as exc:  # noqa: BLE001 - hardware I/O, must not propagate
            logger.warning("Camera %s raised while reading: %s", self.camera_index, exc)
            success, frame = False, None

        if not success or frame is None:
            self._consecutive_read_failures += 1
            if self._consecutive_read_failures == CAMERA_READ_MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "Camera %s has failed to produce a frame for %d consecutive reads.",
                    self.camera_index,
                    self._consecutive_read_failures,
                )
            return None

        self._consecutive_read_failures = 0
        return frame

    def retry(self) -> bool:
        """Close (if needed) and attempt to reopen the camera."""
        self.close()
        return self.open()

    def close(self) -> None:
        """Release the underlying device. Safe to call multiple times."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception as exc:  # noqa: BLE001 - hardware I/O, must not propagate
                logger.debug("Ignoring error releasing camera %s: %s", self.camera_index, exc)
        self._capture = None
        self._is_open = False

    def __enter__(self) -> "CameraService":
        self.open()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
