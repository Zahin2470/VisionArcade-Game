"""Runtime application configuration.

`AppConfig` holds the values needed to start the application (window
size, target frame rate, which camera to open, debug mode, and an
optional game to launch directly). It is intentionally separate from
user-adjustable *persisted* settings (theme, volume, calibration, etc.),
which are owned by `persistence.settings` starting in a later phase.
Keeping these separate avoids one module doing two jobs: "how do we
start" vs. "what did the player last choose".
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from typing import Optional, Sequence

from visionarcade.constants import (
    DEFAULT_CAMERA_INDEX,
    DEFAULT_FPS_TARGET,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)

#: Games recognized by --game. Extended as each mini-game ships.
KNOWN_GAMES: tuple[str, ...] = ("catch", "pong", "slice", "aim", "puzzle")


@dataclass(frozen=True)
class AppConfig:
    """Immutable startup configuration for a single run of the app."""

    camera_index: int = DEFAULT_CAMERA_INDEX
    window_width: int = DEFAULT_WINDOW_WIDTH
    window_height: int = DEFAULT_WINDOW_HEIGHT
    fps_target: int = DEFAULT_FPS_TARGET
    debug: bool = False
    selected_game: Optional[str] = None
    simulate: bool = False

    def with_overrides(self, **kwargs) -> "AppConfig":
        """Return a copy of this config with the given fields replaced."""
        return replace(self, **kwargs)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser described in the project's usage examples.

        python main.py
        python main.py --debug
        python main.py --game catch
        python main.py --camera 0
        python main.py --simulate
    """
    parser = argparse.ArgumentParser(
        prog="visionarcade",
        description="VisionArcade — a touchless, computer-vision arcade.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable developer/debug mode (verbose logging, debug overlays).",
    )
    parser.add_argument(
        "--game",
        choices=KNOWN_GAMES,
        default=None,
        help="Launch directly into a specific mini-game, skipping the hub.",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        metavar="INDEX",
        help="Camera device index to use (default: %(default)s).",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help=(
            "Use a keyboard-controlled simulated hand instead of the camera "
            "(developer mode; arrow keys move it, space toggles pinch, "
            "O toggles openness/fist)."
        ),
    )
    return parser


def config_from_args(argv: Optional[Sequence[str]] = None) -> AppConfig:
    """Parse CLI arguments (or `argv`, for testing) into an `AppConfig`."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return AppConfig(
        camera_index=args.camera,
        debug=args.debug,
        selected_game=args.game,
        simulate=args.simulate,
    )
