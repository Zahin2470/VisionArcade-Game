# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 2 of 10 (gesture/intent layer, calibration, smoothing,
> debug simulation).** This README is a working placeholder. The full
> project overview, gesture/control tables, game descriptions,
> screenshots, and troubleshooting guide are written in Phase 10 once
> every system exists to document.

## What exists right now

**Phase 1 — skeleton:**
- Package skeleton matching the target architecture (`visionarcade/`)
- Runtime configuration (`config.py`) and CLI (`main.py`)
- Camera service (`vision/camera.py`) — opens the webcam, degrades
  gracefully (no crash) if one isn't available
- Hand tracker (`vision/tracker.py`) — wraps MediaPipe's Tasks API
  (`HandLandmarker`), downloading and caching its model automatically
- Base renderer (`rendering/renderer.py`) — window lifecycle and a
  bounded/testable main loop
- Asset manager (`utils/assets.py`) — caches images/sounds, falls back
  to a placeholder on missing assets

**Phase 2 — gesture/intent layer:**
- `vision/features.py` — stateless geometric features (pinch distance,
  openness, palm center) from raw landmarks
- `vision/smoothing.py` — frame-rate-independent exponential smoothing
  and a hysteresis gate, so single noisy frames can't flip game state
- `vision/motion.py` — velocity tracking and swipe detection over a
  short rolling window
- `vision/gestures.py` — the stabilized `IntentBuilder`: turns raw
  per-frame hand detections into a `FrameIntent` with debounced pinch
  START/HOLD/RELEASE, hand-presence grace periods, and swipes
- `vision/calibration.py` — `CalibrationData` (personalized coordinate
  mapping, safely persisted as JSON) and `CalibrationSession` (the
  step-by-step first-run calibration logic)
- `vision/simulation.py` — `SimulatedHandInputSource`, a keyboard-
  drivable stand-in for the camera+tracker, enabling Developer Mode
  (`--simulate`) and fully deterministic pipeline tests with no webcam

Test suite (`tests/`) covers all of the above, runnable without a
physical camera or display.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch the app
python main.py --debug        # verbose logging + on-screen intent debug text
python main.py --camera 1     # use a different camera index
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches,
    # useful for testing the gesture pipeline without a webcam
```

## Running tests

```bash
pytest
```

Tests run headless (no real window or camera needed) via pygame's dummy
video/audio drivers, configured in `tests/conftest.py`. The gesture and
calibration tests drive the pipeline with `SimulatedHandInputSource`
rather than a real camera, per the project's testing requirements.

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically into the app's local data directory on first
use, and disables hand tracking gracefully (no crash) if that download
ever fails — e.g. with no network on a fresh install.

## Roadmap

Arcade hub with audio/persistence (Phase 3), then Vision Catch, Pong,
Slice, Aim, and Puzzle (Phases 4-8), followed by polish (Phase 9) and
full documentation/packaging (Phase 10).
