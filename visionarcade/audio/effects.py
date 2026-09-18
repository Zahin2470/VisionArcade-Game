"""Named sound effects layered on top of `AudioManager`.

Games and UI screens call `play(Sfx.SELECT)` instead of remembering
asset filenames — the mapping lives in one place, and missing files
degrade to silence exactly like any other `AudioManager` call.
"""

from __future__ import annotations

import enum

from visionarcade.audio.manager import AudioManager


class Sfx(enum.Enum):
    HOVER = "hover"
    SELECT = "select"
    GESTURE_CONFIRM = "gesture_confirm"
    SCORE = "score"
    COMBO = "combo"
    GAME_OVER = "game_over"
    VICTORY = "victory"


#: Relative paths under the bundled asset directory. These files don't
#: exist yet (no art/audio pass has happened), which is fine —
#: `AudioManager.play_sfx` degrades to silence for a missing asset.
_SFX_PATHS: dict[Sfx, str] = {
    Sfx.HOVER: "audio/sfx/hover.wav",
    Sfx.SELECT: "audio/sfx/select.wav",
    Sfx.GESTURE_CONFIRM: "audio/sfx/gesture_confirm.wav",
    Sfx.SCORE: "audio/sfx/score.wav",
    Sfx.COMBO: "audio/sfx/combo.wav",
    Sfx.GAME_OVER: "audio/sfx/game_over.wav",
    Sfx.VICTORY: "audio/sfx/victory.wav",
}


class SoundEffects:
    """Thin, named-effect convenience wrapper around an `AudioManager`."""

    def __init__(self, audio: AudioManager) -> None:
        self.audio = audio

    def play(self, effect: Sfx) -> None:
        self.audio.play_sfx(_SFX_PATHS[effect])
