# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 6 of 10 (Vision Slice — the third real, fully
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

**Phase 4 — Vision Catch:** shared collision/scoring/difficulty/input
helpers, a particle system, a reusable HUD, and the first fully
playable game — plus generic Pause and Results screens shared by every
game.

**Phase 5 — Vision Pong:** a touchless in-game mode-select menu
(1-player vs AI, or 2-player), a beatable AI opponent, and two-layer
ball acceleration (match-long ramp plus per-rally speedup).

**Phase 6 — Vision Slice:**
- `arcade/collision.py` gained `segment_circle_intersect` — tests each
  frame's hand-motion segment against every target, not just the
  current point, so a fast swipe that would sail past a target's
  center between two sampled frames still registers as a hit
- Targets launch from the bottom in a parabolic arc (gravity pulls
  them back down) rather than falling straight like Catch's objects,
  giving Slice a distinct feel
- Three target categories: common (chain-scored), rare gold (flat
  bonus), and bombs (avoid — slicing one costs a life and screen-shakes)
- A short fading trail follows your hand for both feedback and
  readability, and a genuine "satisfying slice animation": particle
  bursts plus small rotating shards that fly apart on every cut
- A chain/combo multiplier that decays fast (0.6s) if you stop
  slicing, distinct from Catch/Pong's slower combo windows —
  matching Slice's faster-paced feel

Test suite (`tests/`) covers all of the above — 422 tests, including
end-to-end tests that play real rounds of Catch, Pong, and Slice
through the actual app loop, nothing mocked below the OS event queue.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch: Catch, Pong, and Slice are all fully playable
python main.py --debug        # verbose logging + on-screen intent debug text
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches —
    # play any implemented game without a webcam
```

Vision Aim and Puzzle still show a "coming in a future phase"
placeholder when selected — that's expected until Phases 7-8.

## Running tests

```bash
pytest
```

Tests run headless via pygame's dummy video/audio drivers. Anything
involving randomness (spawn/launch timing, direction, target category,
AI aim error, particle bursts) is seeded via an injected
`random.Random`, so gameplay tests are fully deterministic. Building
the Phase 6 end-to-end test surfaced a good general lesson, noted in
the test file: a target that's independently simulated with real
physics (gravity) during a scripted test can't be aimed at using a
stale, pre-computed position — either track its live position each
frame, or pin it if the test is really about something else (here,
swipe *detection* through the real smoothing pipeline, not tracking a
falling target, which is already covered by `test_slice_game.py`).

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically on first use, and disables hand tracking
gracefully (no crash) if that download ever fails.

## Roadmap

Vision Aim and Puzzle (Phases 7-8, each implementing
`arcade.game.ArcadeGame` and registering one line in
`arcade/manager.py`'s `GAME_FACTORIES`), followed by polish — particle
variety, transitions, a full accessibility pass (Phase 9) — and full
documentation/packaging (Phase 10).
