"""MediaPipe Tasks-backed hand tracking.

MediaPipe's older `mp.solutions.hands` API has been removed from the
current PyPI package in favor of the Tasks API (`HandLandmarker`),
which loads its model from a downloadable `.task` bundle rather than
one bundled inside the pip package. `HandTracker` downloads that model
once into the app's local data directory (see `utils/paths.py`) and
caches it for subsequent runs.

`HandTracker` is the only place in the codebase that imports MediaPipe.
Everything downstream consumes `HandResult` objects from `landmarks.py`.
If the backend can't be initialized for any reason (missing model,
no network on first run, unsupported platform, etc.) the tracker
disables itself and reports `available = False` instead of raising —
the arcade should still run, just without hand tracking, rather than
crash on startup.
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import numpy as np

from visionarcade.constants import (
    DEFAULT_MAX_NUM_HANDS,
    DEFAULT_MIN_DETECTION_CONFIDENCE,
    DEFAULT_MIN_TRACKING_CONFIDENCE,
    HAND_LANDMARKER_MODEL_FILENAME,
    HAND_LANDMARKER_MODEL_URL,
)
from visionarcade.utils.paths import get_user_data_dir
from visionarcade.vision.landmarks import HandLandmark, HandResult

logger = logging.getLogger(__name__)

#: Signature: (url, destination_path) -> None. Overridable for tests.
Downloader = Callable[[str, Path], None]


def _download_file(url: str, destination: Path) -> None:
    """Download `url` to `destination`, atomically (via a temp file)."""
    tmp_path = destination.with_suffix(destination.suffix + ".part")
    urllib.request.urlretrieve(url, tmp_path)  # noqa: S310 - trusted, fixed HTTPS URL
    tmp_path.replace(destination)


def ensure_hand_landmarker_model(
    models_dir: Optional[Path] = None,
    downloader: Optional[Downloader] = None,
) -> Optional[Path]:
    """Return a local path to the hand_landmarker.task model.

    Downloads the model into `models_dir` (default: the app's user data
    directory, under "models/") the first time it's needed, then reuses
    the cached copy on every later call. Returns None — without raising
    — if the model can't be obtained (e.g. no network on first run), so
    callers can disable tracking gracefully instead of crashing.
    """
    resolved_models_dir = models_dir if models_dir is not None else (get_user_data_dir() / "models")
    resolved_models_dir.mkdir(parents=True, exist_ok=True)
    model_path = resolved_models_dir / HAND_LANDMARKER_MODEL_FILENAME

    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path

    download = downloader if downloader is not None else _download_file
    try:
        download(HAND_LANDMARKER_MODEL_URL, model_path)
    except Exception as exc:  # noqa: BLE001 - network I/O must not crash startup
        logger.error("Could not download the hand-tracking model: %s", exc)
        return None

    if not model_path.exists() or model_path.stat().st_size == 0:
        logger.error("Hand-tracking model download produced an empty/missing file.")
        return None

    return model_path


class HandTracker:
    """Runs MediaPipe's HandLandmarker task on individual BGR frames.

    This class deliberately does NOT do any smoothing, gesture
    classification, or coordinate normalization to a game-space — that
    is the job of the stabilization layer added in a later phase
    (`vision/smoothing.py`, `vision/gestures.py`, `vision/features.py`).
    """

    def __init__(
        self,
        max_num_hands: int = DEFAULT_MAX_NUM_HANDS,
        min_detection_confidence: float = DEFAULT_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = DEFAULT_MIN_TRACKING_CONFIDENCE,
        model_path: Optional[Path] = None,
    ) -> None:
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        self._landmarker = None
        self._mp_image_factory = None  # set on successful init
        self._available = False
        self._init_backend(model_path)

    def _init_backend(self, model_path: Optional[Path]) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import (
                HandLandmarker,
                HandLandmarkerOptions,
                RunningMode,
            )

            resolved_model_path = (
                model_path if model_path is not None else ensure_hand_landmarker_model()
            )
            if resolved_model_path is None:
                logger.error("Hand tracking unavailable — no model file could be obtained.")
                self._available = False
                return

            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(resolved_model_path)),
                num_hands=self.max_num_hands,
                min_hand_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                running_mode=RunningMode.IMAGE,
            )
            self._landmarker = HandLandmarker.create_from_options(options)
            self._mp_image_factory = lambda rgb: mp.Image(
                image_format=mp.ImageFormat.SRGB, data=rgb
            )
            self._available = True
        except Exception as exc:  # noqa: BLE001 - must never crash startup
            logger.error("Hand tracking unavailable — MediaPipe failed to initialize: %s", exc)
            self._landmarker = None
            self._mp_image_factory = None
            self._available = False

    @property
    def available(self) -> bool:
        """Whether the tracking backend initialized successfully."""
        return self._available

    def process(self, frame_bgr: Optional[np.ndarray]) -> List[HandResult]:
        """Detect hands in a single BGR frame.

        Returns an empty list if tracking is unavailable, the frame is
        None, or no hands were detected — callers should treat "no
        hands" as a normal, expected state rather than an error.
        """
        if not self._available or self._landmarker is None or frame_bgr is None:
            return []

        try:
            rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = self._mp_image_factory(rgb_frame)
            result = self._landmarker.detect(mp_image)
        except Exception as exc:  # noqa: BLE001 - a bad frame must not crash the loop
            logger.warning("Hand tracking failed on this frame: %s", exc)
            return []

        return self._parse_results(result)

    @staticmethod
    def _parse_results(result) -> List[HandResult]:
        hands: List[HandResult] = []

        hand_landmarks_list = getattr(result, "hand_landmarks", None) or []
        handedness_list = getattr(result, "handedness", None) or []

        for index, hand_landmarks in enumerate(hand_landmarks_list):
            landmarks = tuple(
                HandLandmark(x=lm.x, y=lm.y, z=lm.z) for lm in hand_landmarks
            )

            label = "Unknown"
            score = 0.0
            if index < len(handedness_list) and handedness_list[index]:
                category = handedness_list[index][0]
                label = getattr(category, "category_name", "Unknown")
                score = getattr(category, "score", 0.0)

            hands.append(HandResult(handedness=label, landmarks=landmarks, score=score))

        return hands

    def close(self) -> None:
        """Release MediaPipe resources. Safe to call multiple times."""
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Ignoring error closing hand tracker: %s", exc)
        self._landmarker = None
        self._mp_image_factory = None
        self._available = False

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
