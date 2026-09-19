# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 7 of 10 (Vision Aim — the fourth real, fully
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

**Phase 6 — Vision Slice:** trajectory-based swipe collision
(`segment_circle_intersect`), targets that arc under gravity, three
target categories, a fast-decaying chain multiplier, a fading blade
trail, and rotating shard effects on every cut.

**Phase 7 — Vision Aim:**
- A crosshair reticle follows your index fingertip, with a visible
  hover highlight before you commit — "the UI should show what the
  system thinks the player is doing"
- A sequence of 20 targets, one at a time, each with a shrinking time
  limit that gets tighter as the sequence progresses (ramped by target
  index rather than wall-clock time, since Aim's pacing is inherently
  target-by-target)
- Scoring rewards both accuracy (you have to actually hit it) and
  reaction time (a speed bonus that tapers to zero near the limit),
  plus a streak multiplier for consecutive hits
- Tracks accuracy, average reaction time, missed-target count, and
  best streak — all surfaced on the results screen
- A miss budget (5) that ends the sequence early as "Sequence Failed"
  if exceeded, giving Aim genuine win/loss feedback despite having no
  lives or opponent in the traditional sense

Test suite (`tests/`) covers all of the above — 450 tests, including
end-to-end tests that play real rounds of Catch, Pong, Slice, and Aim
through the actual app loop, nothing mocked below the OS event queue.

While wiring up this phase's end-to-end test, I found and fixed a real
bug from Phase 6: an earlier edit had accidentally merged the Pong
end-to-end test's body into the Slice test (its `def` line was lost in
the edit), so it silently stopped existing as its own discoverable
test — nothing failed, it just quietly ran as unreachable-looking
trailing code inside a different test. Fixed by splitting it back into
its own function; the suite now correctly discovers and runs it
separately.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch: Catch, Pong, Slice, and Aim are all fully playable
python main.py --debug        # verbose logging + on-screen intent debug text
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches —
    # play any implemented game without a webcam
```

Vision Puzzle still shows a "coming in a future phase" placeholder
when selected — that's expected until Phase 8.

## Running tests

```bash
pytest
```

Tests run headless via pygame's dummy video/audio drivers. Anything
involving randomness (target placement) is seeded via an injected
`random.Random`, so gameplay tests are fully deterministic.

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically on first use, and disables hand tracking
gracefully (no crash) if that download ever fails.

## Roadmap

Vision Puzzle (Phase 8, implementing `arcade.game.ArcadeGame` and
registering one line in `arcade/manager.py`'s `GAME_FACTORIES`) — the
fifth and final minimum-required game — followed by polish (particle
variety, transitions, a full accessibility pass, Phase 9) and full
documentation/packaging (Phase 10).
