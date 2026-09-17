"""VisionArcade — a completely touchless, computer-vision-controlled arcade.

This package is organized into clearly separated layers so that new games
can be added without touching camera, tracking, gesture, rendering,
persistence, or audio systems:

    visionarcade/
    ├── app.py            Application entry point / main loop
    ├── config.py         Runtime configuration (CLI + defaults)
    ├── constants.py       Tunable constants, no magic numbers in logic
    ├── vision/            Camera capture, hand tracking, gestures
    ├── arcade/            Game engine, shared game interface, mini-games
    ├── rendering/         Drawing, HUD, themes, transitions, particles
    ├── audio/             Sound/music playback
    ├── persistence/       Settings, scores, profiles on disk
    ├── ui/                Menu/hub screens
    └── utils/             Paths, assets, shared helpers

Phase 1 implements the skeleton, configuration, camera service, hand
tracker, base renderer, and asset manager. Everything else is stubbed
with clear placeholders until its corresponding development phase.
"""

__version__ = "0.1.0-phase1"
