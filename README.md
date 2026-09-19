# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 8 of 10 — all 5 minimum-required mini-games are now
> complete and fully playable.** This README is a working placeholder.
> The full project overview, gesture/control tables, game
> descriptions, screenshots, and troubleshooting guide are written in
> Phase 10 once every system exists to document.

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

**Phase 6 — Vision Slice:** trajectory-based swipe collision
(`segment_circle_intersect`), targets that arc under gravity, three
target categories, a fast-decaying chain multiplier, a fading blade
trail, and rotating shard effects on every cut.

**Phase 7 — Vision Aim:** a hover-aware reticle, a 20-target sequence
with a per-target time limit that tightens as it progresses, scoring
that rewards both speed and accuracy, and a miss budget that gives a
lives-free game genuine win/loss stakes.

**Phase 8 — Vision Puzzle (the fifth and final required game):**
- Pinch to grab a piece, drag it, release it on the matching
  shape-and-color slot — five distinct shapes (circle, triangle,
  square, diamond, pentagon), each with its own color, so pieces are
  never ambiguous
- Both hands work independently and simultaneously — grabbing and
  placing two pieces at once (one per hand) is just something a player
  can choose to do, not a separate mode to toggle
- Three stages, each with more pieces *and* less time than the last —
  a genuine difficulty ramp indexed by stage rather than wall-clock time
- Wrist/hand-orientation rotation (one of the spec's suggested
  "advanced" options, explicitly marked "if robust") was deliberately
  **not** built: our stabilized `HandIntent` has no orientation
  signal, and adding one would mean extending the whole vision
  pipeline for a single optional feature. Shape+color matching is a
  complete puzzle without it — documented in the game's own docstring
  rather than silently dropped

Test suite (`tests/`) covers all of the above — 477 tests, including
end-to-end tests that play real rounds of all five games through the
actual app loop, nothing mocked below the OS event queue.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch: all 5 games are fully playable
python main.py --debug        # verbose logging + on-screen intent debug text
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches —
    # play any game without a webcam
```

## Running tests

```bash
pytest
```

Tests run headless via pygame's dummy video/audio drivers. Anything
involving randomness (spawn/launch timing, target/piece placement, AI
aim error, particle bursts) is seeded via an injected `random.Random`,
so gameplay tests are fully deterministic.

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically on first use, and disables hand tracking
gracefully (no crash) if that download ever fails.

## Roadmap

With all 5 games playable, what's left is polish and packaging:
particle variety, transitions, a full accessibility pass (Phase 9),
then full documentation and packaging (Phase 10) — README overhaul
with gesture/control tables and screenshots, a proper project
structure writeup, and a final acceptance pass against every
requirement in the original design brief.
