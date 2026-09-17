"""Central, tunable constants for VisionArcade.

Nothing outside this module should hard-code a "magic number" for window
sizing, frame rate, camera defaults, or similar tunables. Gesture
thresholds and per-game tuning constants are added here (or in dedicated
config sections) as later phases introduce them.
"""

from __future__ import annotations

# --- Application ---------------------------------------------------------
APP_NAME: str = "VisionArcade"
APP_VERSION: str = "0.1.0-phase1"

# --- Window / rendering ---------------------------------------------------
DEFAULT_WINDOW_WIDTH: int = 1280
DEFAULT_WINDOW_HEIGHT: int = 720
DEFAULT_FPS_TARGET: int = 60
BACKGROUND_COLOR: tuple[int, int, int] = (12, 14, 20)
PLACEHOLDER_TEXT_COLOR: tuple[int, int, int] = (225, 230, 240)

# --- Camera / vision -------------------------------------------------------
DEFAULT_CAMERA_INDEX: int = 0
DEFAULT_CAMERA_FRAME_WIDTH: int = 960
DEFAULT_CAMERA_FRAME_HEIGHT: int = 540
CAMERA_OPEN_MAX_RETRIES: int = 2
CAMERA_READ_MAX_CONSECUTIVE_FAILURES: int = 30  # ~0.5s at 60fps before we flag it

DEFAULT_MAX_NUM_HANDS: int = 2
DEFAULT_MIN_DETECTION_CONFIDENCE: float = 0.6
DEFAULT_MIN_TRACKING_CONFIDENCE: float = 0.5

# MediaPipe's legacy `mp.solutions.hands` API was removed from the pip
# package in favor of the Tasks API, which requires a downloadable model
# bundle rather than a bundled model. It is cached locally after the
# first successful download (see vision/tracker.py).
HAND_LANDMARKER_MODEL_FILENAME: str = "hand_landmarker.task"
HAND_LANDMARKER_MODEL_URL: str = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

# --- Assets -----------------------------------------------------------------
PLACEHOLDER_IMAGE_SIZE: int = 64
PLACEHOLDER_IMAGE_COLOR: tuple[int, int, int, int] = (255, 0, 200, 255)

# --- Persistence / paths -----------------------------------------------------
CONFIG_FILE_NAME: str = "config.json"
SCORES_FILE_NAME: str = "scores.json"
PROFILES_FILE_NAME: str = "profiles.json"
CALIBRATION_FILE_NAME: str = "calibration.json"

# --- Gesture / intent tuning (Phase 2) ---------------------------------------
# Pinch distance is normalized by hand scale (see vision/features.py), so
# these thresholds are roughly resolution- and hand-size-independent.
# Enter/exit are deliberately different (hysteresis) so a pinch distance
# hovering near one value can't flicker between states every frame.
PINCH_ENTER_DISTANCE: float = 0.35
PINCH_EXIT_DISTANCE: float = 0.55
PINCH_MIN_HOLD_FRAMES: int = 2

OPENNESS_FIST_THRESHOLD: float = 0.6

HAND_PRESENCE_CONFIRM_FRAMES: int = 3
HAND_PRESENCE_GRACE_FRAMES: int = 10  # ~0.15s at 60fps of tolerated dropout

SWIPE_DETECTION_WINDOW_SECONDS: float = 0.35
SWIPE_MIN_SPEED: float = 1.8  # normalized units/second
SWIPE_MIN_DISPLACEMENT: float = 0.18  # normalized units over the window
SWIPE_COOLDOWN_SECONDS: float = 0.4

SMOOTHING_TIME_CONSTANT_SECONDS: float = 0.12

# --- Calibration (Phase 2) ---------------------------------------------------
# Generic fallback bounds used before calibration ever runs, or if it was
# skipped/degenerate — most people's comfortable hand movement covers
# roughly the middle 60% of the frame, not the true edges.
CALIBRATION_DEFAULT_X_MIN: float = 0.2
CALIBRATION_DEFAULT_X_MAX: float = 0.8
CALIBRATION_DEFAULT_Y_MIN: float = 0.2
CALIBRATION_DEFAULT_Y_MAX: float = 0.8
CALIBRATION_MOVE_PHASE_SECONDS: float = 4.0
CALIBRATION_STEP_HOLD_SECONDS: float = 1.0
