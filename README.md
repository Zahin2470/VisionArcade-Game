# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 9 of 10 (polish and accessibility).** This README is
> a working placeholder. The full project overview, gesture/control
> tables, game descriptions, screenshots, and troubleshooting guide
> are written in Phase 10.

## What exists right now

**Phases 1-8:** the full vision pipeline (camera → hand tracking →
gesture/intent), the arcade shell (home hub, settings, calibration,
pause, results, persistence, audio, themes), and all 5 minimum-required
mini-games — Catch, Pong, Slice, Aim, and Puzzle — fully playable.

**Phase 9 — polish and accessibility:**
- **A real accessibility bug fixed, not just polish:** the Settings
  screen's sensitivity, smoothing, and reduced-particles controls
  existed and were adjustable — but did nothing. They're now wired
  into the actual gesture pipeline and every game's particle system:
  - `sensitivity` scales how far a physical hand movement translates
    into on-screen movement (amplifies for limited range of motion,
    dampens for finer control)
  - `smoothing` scales the gesture pipeline's smoothing time constant
    live, without resetting tracking state (no visible jump when you
    adjust it)
  - `reduced_particles` scales down (not eliminates) every game's
    particle burst sizes
- **A Tutorial screen** (`ui/tutorial.py`) — previously a stub with
  zero implementation, despite the hub's own design calling for a
  "help/tutorial" entry. Now a real screen explaining all five core
  gestures (move/point, pinch, open palm, fist, swipe) with simple
  icons, reachable from a new hub button
- **Screen transitions** — a brief fade applied automatically by the
  shell on every state change (Home → Settings, entering a game,
  reaching Results, etc.), so no individual screen needs transition
  logic of its own
- **Share cards** — Pillow (declared as a dependency since Phase 1,
  unused until now) generates a PNG summary of a completed round
  (score, outcome, best streak, etc.) via a new "Save Share Card"
  button on the Results screen, saved locally
- A debug-only FPS/frame-time readout, never shown to a normal player

**Deliberately scoped down, with reasoning:** the master prompt's full
"camera presentation" section (a live, letterboxed camera view with
vignette, tracked-hand overlay, gesture label, and confidence
indicator on the calibration screen and a debug preview panel during
gameplay) was not built this phase. It's a substantial, genuinely
useful feature, but attempting it with the remaining time in this
phase risked shipping something under-tested. Rather than rush it, I
left it out and am flagging it here plainly so it isn't mistaken for
an oversight — it's a good candidate for Phase 10 if there's room, or
a documented known gap in the final acceptance pass.

Test suite (`tests/`) covers all of the above — 509 tests.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch: all 5 games playable, tutorial available from the hub
python main.py --debug        # verbose logging + on-screen intent/FPS debug text
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches
```

## Running tests

```bash
pytest
```

Tests run headless via pygame's dummy video/audio drivers. Anything
involving randomness is seeded via an injected `random.Random`, so
gameplay tests are fully deterministic.

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically on first use, and disables hand tracking
gracefully (no crash) if that download ever fails.

## Roadmap

Phase 10: full documentation and packaging — a real README with
gesture/control tables and screenshots, a final acceptance pass against
every requirement in the original design brief (including an explicit
note on the deferred camera-presentation feature above), and general
release readiness.
