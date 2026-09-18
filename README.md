# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 4 of 10 (Vision Catch — the first real, fully
> playable mini-game).** This README is a working placeholder. The
> full project overview, gesture/control tables, game descriptions,
> screenshots, and troubleshooting guide are written in Phase 10 once
> every system exists to document.

## What exists right now

**Phase 1 — skeleton:** package structure, CLI/config, camera service,
MediaPipe Tasks-based hand tracker, base renderer, asset manager.

**Phase 2 — gesture/intent layer:** stateless feature extraction,
frame-rate-independent smoothing, swipe/velocity detection, a
debounced pinch state machine, `IntentBuilder`, calibration, and a
keyboard-drivable hand simulator for Developer Mode and tests.

**Phase 3 — arcade shell:** persisted settings/scores/profile (all
tolerant of corrupted files), an audio manager, themes/typography, a
shared keyboard-or-touchless `FocusGroup` navigation primitive, the
home hub, settings screen, and calibration screen — plus the
`ArcadeGame` interface every mini-game implements.

**Phase 4 — Vision Catch (the first real game):**
- `arcade/collision.py`, `arcade/scoring.py`, `arcade/difficulty.py`,
  `arcade/input.py` — small, pure, reusable helpers (circle/rect
  overlap, score + combo-with-decay tracking, a linear difficulty
  ramp, and `FrameIntent` -> play-area-pixel-space mapping) that every
  future mini-game shares rather than reimplementing
- `rendering/particles.py` — a seedable particle-burst system for hit
  feedback
- `rendering/hud.py` — a reusable in-game score/lives/combo/timer
  overlay
- `arcade/games/catch.py` — **Vision Catch** itself: move a
  hand-controlled catcher to collect falling objects and avoid
  hazards, with a combo multiplier that decays if you go too long
  without a catch, fall speed and spawn rate that ramp up over a
  90-second round, a rare high-value bonus object, "near miss" bonus
  feedback for hazards that pass close by uncaught, and a screen
  shake used only when you get hit
- `ui/pause.py` + `ui/results.py` — generic Pause (Resume/Restart/Quit
  to Hub) and Results (score, best-streak, new-best callout, Play
  Again/Back to Hub) screens, shared by every mini-game — quitting
  mid-round still saves your score so far

Test suite (`tests/`) covers all of the above — 346 tests, including
an end-to-end test that plays a real round of Catch (catch an object,
pause, resume) through the actual app loop with nothing mocked below
the OS event queue.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch: home hub -> Vision Catch is fully playable
python main.py --debug        # verbose logging + on-screen intent debug text
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches —
    # play a full round of Catch without a webcam
```

Vision Pong, Slice, Aim, and Puzzle still show a "coming in a future
phase" placeholder when selected — that's expected until Phases 5-8.

## Running tests

```bash
pytest
```

Tests run headless via pygame's dummy video/audio drivers. Anything
involving randomness (spawn timing/kind/position, particle bursts) is
seeded via an injected `random.Random`, so gameplay tests are fully
deterministic — a separate, unseeded RNG is used only for cosmetic
screen-shake jitter, which no test asserts exact values against.

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically on first use, and disables hand tracking
gracefully (no crash) if that download ever fails.

## Roadmap

Vision Pong, Slice, Aim, and Puzzle (Phases 5-8, each implementing
`arcade.game.ArcadeGame` and registering one line in
`arcade/manager.py`'s `GAME_FACTORIES`), followed by polish — particle
variety, transitions, a full accessibility pass (Phase 9) — and full
documentation/packaging (Phase 10).
