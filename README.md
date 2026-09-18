# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 5 of 10 (Vision Pong — the second real, fully
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

**Phase 5 — Vision Pong:**
- A touchless in-game mode-select menu — point and pinch to choose
  1-player (vs AI) or 2-player, using the same `FocusGroup` primitive
  the hub uses, just driven inside the game itself rather than the shell
- Single-player: your right hand controls the right paddle; an AI
  controls the left paddle, chasing the ball with a capped speed and a
  small persistent aim error (re-rolled only once per approach) so
  it's beatable, not a perfect wall — and it gets faster as the match
  goes on
- Two-player: your left and right hands independently control the
  left and right paddles
- Ball speed ramps over the whole match, *and* gets an extra
  multiplicative boost on every paddle hit within a rally (capped), so
  a long rally visibly escalates — with real "English" off-center
  paddle hits, a `Rally xN!` feedback banner, and a brief serve delay
  between points
- `arcade/input.py` gained `map_point_to_rect`, extracted so two-hand
  games can map either hand's position independently, not just the
  primary hand `build_game_input` already handled

Test suite (`tests/`) covers all of the above — 388 tests, including
end-to-end tests that play a real round of Catch *and* a real match of
Pong (with a genuine touchless pinch-driven menu selection) through
the actual app loop, nothing mocked below the OS event queue.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch: home hub -> Catch and Pong are fully playable
python main.py --debug        # verbose logging + on-screen intent debug text
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches —
    # play a full round of Catch or a full match of Pong without a webcam
```

Vision Slice, Aim, and Puzzle still show a "coming in a future phase"
placeholder when selected — that's expected until Phases 6-8.

## Running tests

```bash
pytest
```

Tests run headless via pygame's dummy video/audio drivers. Anything
involving randomness (spawn/serve timing, direction, AI aim error,
particle bursts) is seeded via an injected `random.Random`, so
gameplay tests are fully deterministic.

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically on first use, and disables hand tracking
gracefully (no crash) if that download ever fails.

## Roadmap

Vision Slice, Aim, and Puzzle (Phases 6-8, each implementing
`arcade.game.ArcadeGame` and registering one line in
`arcade/manager.py`'s `GAME_FACTORIES`), followed by polish — particle
variety, transitions, a full accessibility pass (Phase 9) — and full
documentation/packaging (Phase 10).
