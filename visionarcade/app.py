"""Application entry point and main loop.

Phase 3 wires the full arcade shell in:

    camera/simulator -> tracker -> IntentBuilder -> FrameIntent -> ArcadeManager

`ArcadeManager` owns the home hub, settings, and calibration screens,
plus the settings/scores/profile persisted on disk and the audio
manager. `run()` still accepts an optional `max_frames` so tests can
drive a real (non-mocked) instance deterministically without a human
closing the window.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

import cv2
import pygame

from visionarcade.arcade.manager import ArcadeManager
from visionarcade.audio.manager import AudioManager
from visionarcade.config import AppConfig, config_from_args
from visionarcade.constants import APP_NAME
from visionarcade.persistence.profiles import load_profile
from visionarcade.persistence.scores import load_scores
from visionarcade.persistence.settings import load_settings
from visionarcade.rendering.renderer import Renderer
from visionarcade.vision.calibration import load_calibration
from visionarcade.vision.camera import CameraService
from visionarcade.vision.gestures import FrameIntent, IntentBuilder
from visionarcade.vision.landmarks import HandResult
from visionarcade.vision.simulation import SimulatedHandInputSource
from visionarcade.vision.tracker import HandTracker

logger = logging.getLogger(__name__)

#: How far the simulated hand moves per second while an arrow key is held.
_SIMULATED_HAND_SPEED = 0.6


def configure_logging(debug: bool) -> None:
    """Set up basic logging. Debug mode is more verbose."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


class VisionArcadeApp:
    """Owns the top-level renderer, input source, intent pipeline, and
    the arcade shell for one run of the application."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.renderer = Renderer(
            width=config.window_width,
            height=config.window_height,
            title=APP_NAME,
        )

        self.camera: Optional[CameraService] = None if config.simulate else CameraService(
            camera_index=config.camera_index
        )
        self.tracker: Optional[HandTracker] = None if config.simulate else HandTracker()
        self.simulator: Optional[SimulatedHandInputSource] = (
            SimulatedHandInputSource() if config.simulate else None
        )

        self.settings = load_settings()
        self.scores = load_scores()
        self.profile = load_profile()
        self.calibration = load_calibration()

        self.intent_builder = IntentBuilder(calibration=self.calibration)
        self.latest_intent: Optional[FrameIntent] = None

        self.arcade_manager: Optional[ArcadeManager] = None
        self._camera_available = False
        self._started = False
        self._clock: Optional[pygame.time.Clock] = None

        if self.simulator is not None:
            # Start with a visible, centered right hand so debug mode is
            # immediately useful without extra setup.
            self.simulator.set_hand("Right", present=True, position=(0.5, 0.5))

    def start(self) -> None:
        """Open the window, build the arcade shell, and (unless
        simulating) attempt the camera."""
        if self._started:
            return
        self.renderer.open()
        self._clock = pygame.time.Clock()

        self.arcade_manager = ArcadeManager(
            width=self.config.window_width,
            height=self.config.window_height,
            settings=self.settings,
            scores=self.scores,
            profile=self.profile,
            calibration=self.calibration,
            audio=AudioManager(),
        )

        if self.camera is not None:
            self._camera_available = self.camera.open()
            if not self._camera_available:
                logger.warning(
                    "Starting without a camera. Hand tracking will be disabled "
                    "until a camera becomes available."
                )
        if self.tracker is not None and not self.tracker.available:
            logger.warning(
                "Hand tracking backend failed to initialize; running in "
                "vision-disabled mode."
            )
        if self.simulator is not None:
            logger.info(
                "Running with a simulated hand (arrow keys move it, space "
                "toggles pinch, O toggles openness/fist)."
            )
        self._started = True

    def run(self, max_frames: Optional[int] = None) -> None:
        """Run the main loop until the player quits, then shut down.

        If `max_frames` is given, the loop exits after that many frames
        regardless of window events — used by smoke tests that want a
        single self-contained call. For tests that need to step the
        app frame-by-frame while keeping it alive between steps (e.g.
        to manipulate game state mid-round), call `start()` once, then
        `step()` repeatedly, then `shutdown()` — see `step()`.
        """
        self.start()
        frame_count = 0
        try:
            running = True
            while running:
                running = self.step()
                frame_count += 1
                if max_frames is not None and frame_count >= max_frames:
                    break
        finally:
            self.shutdown()

    def step(self) -> bool:
        """Advance the app by exactly one frame.

        Does not call `start()` or `shutdown()` — callers that want a
        fully self-contained single call should use `run()` instead.
        `step()` exists so tests can drive several frames in a row
        (with real state manipulation in between) without tearing down
        and reopening pygame's display each time, the way repeated
        `run(max_frames=1)` calls otherwise would via `run()`'s cleanup.
        Returns whether the app should keep running.
        """
        dt = self._clock.tick(self.config.fps_target) / 1000.0
        window_open, key_events = self.renderer.pump_events()

        hand_results = self._collect_hand_results(dt)
        self.latest_intent = self.intent_builder.update(hand_results, dt)
        self.arcade_manager.update(self.latest_intent, hand_results, key_events, dt)

        self._render_frame()

        return window_open and not self.arcade_manager.should_quit

    def _collect_hand_results(self, dt: float) -> List[HandResult]:
        if self.simulator is not None:
            self._apply_simulated_keyboard_input(dt)
            return self.simulator.get_hand_results()

        frame = self.camera.read_frame() if self._camera_available else None
        if frame is None or self.tracker is None:
            return []

        if self.arcade_manager is not None and self.arcade_manager.settings.camera_mirror:
            frame = cv2.flip(frame, 1)  # horizontal flip: feels like a mirror to the player

        return self.tracker.process(frame)

    def _apply_simulated_keyboard_input(self, dt: float) -> None:
        """Let the developer drive the simulated hand from the keyboard,
        so the whole vision->intent->arcade pipeline can be exercised by
        hand without a camera (Developer Mode's "simulate hand
        positions" and "simulate pinch/swipe gestures"). Note: the same
        arrow keys also move menu focus via the discrete keydown events
        `ArcadeManager` receives — both are intentional for a developer
        tool, if a little redundant."""
        assert self.simulator is not None
        keys = pygame.key.get_pressed()

        if not self.simulator.is_present("Right"):
            return
        position = self.simulator.get_position("Right")
        if position is None:
            return

        dx = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * _SIMULATED_HAND_SPEED * dt
        dy = (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * _SIMULATED_HAND_SPEED * dt
        if dx or dy:
            x = min(1.0, max(0.0, position[0] + dx))
            y = min(1.0, max(0.0, position[1] + dy))
            self.simulator.move_hand("Right", (x, y))

        self.simulator.set_pinch("Right", bool(keys[pygame.K_SPACE]))

    def _render_frame(self) -> None:
        self.arcade_manager.draw(self.renderer.surface)

        if self.config.debug and self.latest_intent is not None:
            self._draw_debug_intent_text(self.latest_intent)

        self.renderer.present()

    def _draw_debug_intent_text(self, intent: FrameIntent) -> None:
        hand = intent.primary()
        if not hand.present:
            line = "hand: not detected"
        else:
            pos = hand.position or (0.0, 0.0)
            line = (
                f"hand={hand.handedness} pos=({pos[0]:.2f}, {pos[1]:.2f}) "
                f"pinch={hand.pinch_state.value} openness={hand.openness:.2f} "
                f"fist={hand.is_fist} swipe={hand.swipe}"
            )
        debug_center = (self.renderer.width // 2, self.renderer.height - 16)
        self.renderer.draw_placeholder_text(line, color=(120, 220, 160), center=debug_center)

    def shutdown(self) -> None:
        """Persist state and release the camera, tracker, and window."""
        if self.arcade_manager is not None:
            self.arcade_manager.shutdown()
        if self.camera is not None:
            self.camera.close()
        if self.tracker is not None:
            self.tracker.close()
        self.renderer.close()
        self._started = False


def main(argv: Optional[Sequence[str]] = None) -> None:
    """CLI entry point. See `config.build_arg_parser` for usage."""
    config = config_from_args(argv)
    configure_logging(config.debug)
    logger.info(
        "Starting %s (debug=%s, camera=%s, simulate=%s)",
        APP_NAME,
        config.debug,
        config.camera_index,
        config.simulate,
    )

    app = VisionArcadeApp(config)
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user; shutting down.")
        app.shutdown()


if __name__ == "__main__":
    main()
