"""The top-level arcade screen states.

Not every state is reachable yet — PAUSED, RESULTS, and TUTORIAL are
reserved here so `arcade/manager.py`'s contract is stable, but they
only become reachable once real games exist (Phase 4 onward).
"""

from __future__ import annotations

import enum


class ArcadeState(enum.Enum):
    HOME = "home"
    SETTINGS = "settings"
    CALIBRATION = "calibration"
    PLAYING = "playing"
    PAUSED = "paused"  # reserved: wired up once a real game exists
    RESULTS = "results"  # reserved: wired up once a real game exists
    TUTORIAL = "tutorial"  # reserved: wired up once a real game exists
