# VisionArcade

A completely touchless, computer-vision-controlled arcade — played entirely
through webcam-tracked hand gestures, no mouse or touchscreen required
during gameplay.

> **Status: Phase 3 of 10 (arcade shell — home screen, navigation,
> settings, audio, persistence).** This README is a working
> placeholder. The full project overview, gesture/control tables, game
> descriptions, screenshots, and troubleshooting guide are written in
> Phase 10 once every system exists to document.

## What exists right now

**Phase 1 — skeleton:** package structure, CLI/config, camera service,
MediaPipe Tasks-based hand tracker, base renderer, asset manager.

**Phase 2 — gesture/intent layer:** stateless feature extraction,
frame-rate-independent smoothing, swipe/velocity detection, a
debounced pinch state machine, `IntentBuilder` (raw detections ->
stabilized `FrameIntent`), calibration (data model + session logic),
and a keyboard-drivable hand simulator for Developer Mode and tests.

**Phase 3 — arcade shell:**
- `persistence/` — `Settings` (theme/audio/camera/accessibility,
  always clamped to valid ranges), `ScoresStore` (per-game history,
  tolerates partially corrupted files by skipping only the bad
  entries), `PlayerProfile` (display name + play count) — all through
  a shared atomic-write JSON helper (`persistence/storage.py`)
- `audio/` — `AudioManager` (mixer lifecycle, volume/mute, fails
  silently on a missing backend or asset) and named `Sfx` effects
- `rendering/themes.py` + `rendering/typography.py` — four palettes
  (dark/light/neon/mono) and a cached, named type scale
- `ui/navigation.py` — a shared `FocusGroup`/`SelectableItem`
  primitive: menus are navigable by keyboard (arrows + Enter/Space,
  the accessibility/testing fallback) **or** touchlessly, by pointing
  with a fingertip and pinching
- `ui/home.py` — the hub: a card per mini-game (best score,
  difficulty, description) plus Settings/Calibrate/Quit
- `ui/settings.py` — every `Settings` field, live-adjustable and
  auto-saved on exit, plus a "reset scores" action
- `ui/calibration.py` — the visual wrapper around Phase 2's
  `CalibrationSession`, with a skip affordance
- `arcade/state.py` + `arcade/game.py` — the `ArcadeState` enum and
  the `ArcadeGame` interface every future mini-game will implement
  (locked now, before any game exists, so adding one later never
  requires touching camera/tracking/rendering/persistence/audio code)
- `arcade/manager.py` — the shell controller tying all of the above
  together; selecting a mini-game currently opens a clearly-labeled
  placeholder screen, since Phases 4-8 haven't implemented the games
  yet

Test suite (`tests/`) covers all of the above — 249 tests, runnable
without a physical camera or display.

## Quick start

```bash
pip install -r requirements.txt
python main.py                # launch the app: home hub, settings, calibration all work
python main.py --debug        # verbose logging + on-screen intent debug text
python main.py --camera 1     # use a different camera index
python main.py --simulate --debug
    # keyboard-controlled hand: arrow keys move it, space pinches —
    # useful for navigating the whole hub without a webcam
```

Navigate the hub either with a real hand (point at a card, pinch to
select) or with arrow keys + Enter/Space — both drive the same menus.

## Running tests

```bash
pytest
```

Tests run headless (no real window, camera, or audio device needed)
via pygame's dummy video/audio drivers, configured in
`tests/conftest.py`. Persistence tests redirect file writes to a temp
directory rather than touching the real per-user data folder.

## A note on MediaPipe

The classic `mediapipe.solutions.hands` API has been removed from
current MediaPipe releases in favor of the Tasks API (`HandLandmarker`),
which loads its model from a small downloadable `.task` file rather
than one bundled in the pip package. `HandTracker` downloads and caches
that file automatically into the app's local data directory on first
use, and disables hand tracking gracefully (no crash) if that download
ever fails — e.g. with no network on a fresh install.

## Roadmap

Vision Catch, Pong, Slice, Aim, and Puzzle (Phases 4-8, each
implementing `arcade.game.ArcadeGame`), followed by polish — particle
effects, transitions, full accessibility pass (Phase 9) — and full
documentation/packaging (Phase 10).
