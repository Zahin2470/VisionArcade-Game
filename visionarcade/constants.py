"""Central, tunable constants for VisionArcade.

Nothing outside this module should hard-code a "magic number" for window
sizing, frame rate, camera defaults, or similar tunables. Gesture
thresholds and per-game tuning constants are added here (or in dedicated
config sections) as later phases introduce them.
"""

from __future__ import annotations

# --- Application ---------------------------------------------------------
APP_NAME: str = "VisionArcade"
APP_VERSION: str = "1.0.0"

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

# --- Themes / settings (Phase 3) ---------------------------------------------
THEMES: tuple[str, ...] = ("dark", "light", "neon", "mono")
DEFAULT_THEME: str = "dark"

MIN_VOLUME: float = 0.0
MAX_VOLUME: float = 1.0
DEFAULT_MASTER_VOLUME: float = 1.0
DEFAULT_SFX_VOLUME: float = 1.0
DEFAULT_MUSIC_VOLUME: float = 0.6

SENSITIVITY_MIN: float = 0.5
SENSITIVITY_MAX: float = 2.0
DEFAULT_SENSITIVITY: float = 1.0

SMOOTHING_MULTIPLIER_MIN: float = 0.5
SMOOTHING_MULTIPLIER_MAX: float = 2.0
DEFAULT_SMOOTHING_MULTIPLIER: float = 1.0

DEFAULT_PLAYER_DISPLAY_NAME: str = "Player"
DISPLAY_NAME_MAX_LENGTH: int = 24

MAX_SCORE_HISTORY_PER_GAME: int = 50

# --- Arcade hub layout / metadata (Phase 3) ----------------------------------
GAME_CARD_WIDTH: int = 220
GAME_CARD_HEIGHT: int = 260
GAME_CARD_GAP: int = 28
FOCUS_BORDER_WIDTH: int = 3

#: Static per-game metadata used by the hub before each game ships its
#: own richer description — keeps display strings out of UI code.
GAME_METADATA: dict = {
    "catch": {
        "title": "Vision Catch",
        "description": "Move a hand-controlled catcher to collect falling objects.",
        "difficulty": "Easy",
    },
    "pong": {
        "title": "Vision Pong",
        "description": "Control a paddle with your hand and rally the ball.",
        "difficulty": "Medium",
    },
    "slice": {
        "title": "Vision Slice",
        "description": "Swipe through moving targets with your hand's trajectory.",
        "difficulty": "Medium",
    },
    "aim": {
        "title": "Vision Aim",
        "description": "Point at targets and pinch to activate them.",
        "difficulty": "Hard",
    },
    "puzzle": {
        "title": "Vision Puzzle",
        "description": "Touchless spatial puzzle: pinch, move, and place pieces.",
        "difficulty": "Hard",
    },
}

# --- Vision Catch tuning (Phase 4) -------------------------------------------
CATCH_START_LIVES: int = 3
CATCH_ROUND_DURATION_SECONDS: float = 90.0
CATCH_COUNTDOWN_SECONDS: float = 3.0
CATCH_DIFFICULTY_RAMP_SECONDS: float = 60.0

CATCH_CATCHER_WIDTH: int = 130
CATCH_CATCHER_HEIGHT: int = 26
CATCH_OBJECT_RADIUS: float = 16.0

CATCH_FALL_SPEED_START: float = 140.0  # px/sec
CATCH_FALL_SPEED_END: float = 340.0  # px/sec
CATCH_SPAWN_INTERVAL_START: float = 1.1  # seconds between spawns
CATCH_SPAWN_INTERVAL_END: float = 0.45

CATCH_GOOD_WEIGHT: float = 70.0
CATCH_HAZARD_WEIGHT: float = 25.0
CATCH_BONUS_WEIGHT: float = 5.0

CATCH_GOOD_POINTS: int = 10
CATCH_BONUS_POINTS: int = 50
CATCH_NEAR_MISS_BONUS_POINTS: int = 5
CATCH_NEAR_MISS_DISTANCE: float = 40.0  # px

CATCH_COMBO_MAX_MULTIPLIER: float = 4.0
CATCH_COMBO_MULTIPLIER_STEP: float = 0.5
CATCH_COMBO_TIMEOUT_SECONDS: float = 2.5

CATCH_SCREEN_SHAKE_DURATION: float = 0.25
CATCH_SCREEN_SHAKE_MAGNITUDE: float = 8.0  # px

# --- Vision Pong tuning (Phase 5) --------------------------------------------
PONG_POINTS_TO_WIN: int = 7
PONG_COUNTDOWN_SECONDS: float = 3.0
PONG_SERVE_DELAY_SECONDS: float = 0.8
PONG_DIFFICULTY_RAMP_SECONDS: float = 60.0

PONG_PADDLE_WIDTH: int = 18
PONG_PADDLE_HEIGHT: int = 110
PONG_PADDLE_MARGIN: int = 30  # distance from the play area's left/right edge

PONG_BALL_RADIUS: float = 10.0
PONG_BALL_SPEED_START: float = 260.0  # px/sec
PONG_BALL_SPEED_END: float = 480.0
PONG_BALL_MAX_SPEED: float = 700.0  # absolute cap regardless of ramp + hit speedup
PONG_BALL_HIT_SPEEDUP: float = 1.05  # multiplicative speed boost per paddle hit

PONG_BOUNCE_MAX_ANGLE_SPEED: float = 340.0  # px/sec of vertical "english" from an edge hit

PONG_AI_SPEED_START: float = 220.0  # px/sec, AI paddle chase speed early on
PONG_AI_SPEED_END: float = 420.0  # AI gets tougher as the round goes on
PONG_AI_REACTION_ERROR: float = 18.0  # px of random aim error, so the AI is beatable

# --- Vision Slice tuning (Phase 6) -------------------------------------------
SLICE_START_LIVES: int = 3
SLICE_ROUND_DURATION_SECONDS: float = 75.0
SLICE_COUNTDOWN_SECONDS: float = 3.0
SLICE_DIFFICULTY_RAMP_SECONDS: float = 55.0

SLICE_TARGET_RADIUS: float = 26.0
SLICE_GRAVITY: float = 480.0  # px/sec^2, pulls arced targets back down

SLICE_LAUNCH_SPEED_START: float = 520.0  # px/sec, initial launch speed magnitude
SLICE_LAUNCH_SPEED_END: float = 720.0
SLICE_SPAWN_INTERVAL_START: float = 1.0  # seconds between spawns
SLICE_SPAWN_INTERVAL_END: float = 0.5

SLICE_COMMON_WEIGHT: float = 65.0
SLICE_GOLD_WEIGHT: float = 10.0
SLICE_BOMB_WEIGHT: float = 25.0

SLICE_COMMON_POINTS: int = 10
SLICE_GOLD_POINTS: int = 50

SLICE_CHAIN_MAX_MULTIPLIER: float = 5.0
SLICE_CHAIN_MULTIPLIER_STEP: float = 0.5
SLICE_CHAIN_TIMEOUT_SECONDS: float = 0.6

SLICE_TRAIL_LENGTH: int = 14

SLICE_SCREEN_SHAKE_DURATION: float = 0.25
SLICE_SCREEN_SHAKE_MAGNITUDE: float = 9.0  # px

# --- Vision Aim tuning (Phase 7) ----------------------------------------------
AIM_TARGET_COUNT: int = 20
AIM_MAX_MISSES: int = 5
AIM_COUNTDOWN_SECONDS: float = 3.0
AIM_TARGET_RADIUS: float = 34.0

# The per-target time limit ramps down over the *sequence* (by target
# index), not elapsed wall-clock time — Aim's pacing is target-by-target.
AIM_TIME_LIMIT_START: float = 1.8
AIM_TIME_LIMIT_END: float = 0.9
AIM_DIFFICULTY_RAMP_TARGETS: float = 15.0

AIM_BASE_POINTS: int = 20
AIM_SPEED_BONUS_MAX: int = 30  # extra points for an instant reaction, tapering to 0 near the limit

AIM_STREAK_MAX_MULTIPLIER: float = 3.0
AIM_STREAK_MULTIPLIER_STEP: float = 0.25

# --- Vision Puzzle tuning (Phase 8) -------------------------------------------
PUZZLE_STAGE_COUNT: int = 3
PUZZLE_BASE_PIECE_COUNT: int = 3  # stage i (0-indexed) presents BASE + i pieces
PUZZLE_COUNTDOWN_SECONDS: float = 3.0
PUZZLE_STAGE_TRANSITION_SECONDS: float = 1.5

# Later stages have more pieces AND less time — a genuine difficulty
# ramp, indexed by stage number rather than wall-clock time.
PUZZLE_STAGE_TIME_START: float = 45.0
PUZZLE_STAGE_TIME_END: float = 30.0

PUZZLE_PIECE_RADIUS: float = 30.0
PUZZLE_SLOT_RADIUS: float = 34.0  # slightly larger than a piece, for placement tolerance
PUZZLE_GRAB_RADIUS: float = 40.0  # how close a pointer must be to grab a loose piece

PUZZLE_BASE_POINTS_PER_PIECE: int = 30
PUZZLE_STAGE_BONUS_STEP: float = 0.25  # each stage's pieces are worth 25% more than the last

PUZZLE_STREAK_MAX_MULTIPLIER: float = 2.5
PUZZLE_STREAK_MULTIPLIER_STEP: float = 0.3

#: Five visually distinct piece kinds (shape name, polygon side count;
#: 0 sides means "draw a circle"), paired with a fixed, theme-independent
#: color palette — puzzle pieces need to be tellable apart from each
#: other more than they need to match a theme's palette.
PUZZLE_PIECE_KINDS: tuple = ("circle", "triangle", "square", "diamond", "pentagon")
PUZZLE_PIECE_COLORS: tuple = (
    (231, 76, 60),  # circle: red
    (241, 196, 15),  # triangle: yellow
    (46, 204, 113),  # square: green
    (52, 152, 219),  # diamond: blue
    (155, 89, 182),  # pentagon: purple
)
