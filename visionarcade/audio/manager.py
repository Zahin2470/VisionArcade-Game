"""Reusable audio playback: music and sound effects.

Every method here fails softly: if the mixer backend isn't available,
or an asset is missing, playback is silently skipped rather than
raising — audio is a nice-to-have, never a crash risk.
"""

from __future__ import annotations

import logging
from typing import Optional

import pygame

from visionarcade.utils.assets import AssetManager

logger = logging.getLogger(__name__)


class AudioManager:
    """Owns mixer initialization, current volume state, and playback.

    Volumes are tracked here (0..1 for master/sfx/music, plus a mute
    flag) so `apply_settings()` can push a `Settings` object's audio
    preferences in without every call site needing to know about
    `persistence.settings`.
    """

    def __init__(self, assets: Optional[AssetManager] = None) -> None:
        self.assets = assets if assets is not None else AssetManager()
        self._available = False
        self._master_volume = 1.0
        self._sfx_volume = 1.0
        self._music_volume = 1.0
        self._muted = False
        self._current_music_track: Optional[str] = None
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._available = pygame.mixer.get_init() is not None
        except Exception as exc:  # noqa: BLE001 - audio backend issues must not crash the app
            logger.warning("Audio unavailable — mixer failed to initialize: %s", exc)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def apply_settings(
        self, master_volume: float, sfx_volume: float, music_volume: float, muted: bool
    ) -> None:
        """Push volume/mute preferences (typically from `Settings`)."""
        self._master_volume = max(0.0, min(1.0, master_volume))
        self._sfx_volume = max(0.0, min(1.0, sfx_volume))
        self._music_volume = max(0.0, min(1.0, music_volume))
        self._muted = muted
        self._apply_music_volume()

    def _effective_music_volume(self) -> float:
        return 0.0 if self._muted else self._master_volume * self._music_volume

    def _effective_sfx_volume(self) -> float:
        return 0.0 if self._muted else self._master_volume * self._sfx_volume

    def _apply_music_volume(self) -> None:
        if not self._available:
            return
        try:
            pygame.mixer.music.set_volume(self._effective_music_volume())
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not update music volume: %s", exc)

    def play_music(self, relative_path: str, loop: bool = True) -> None:
        """Start looping background music. Missing files play silence."""
        if not self._available:
            return
        if self._current_music_track == relative_path and pygame.mixer.music.get_busy():
            return  # already playing this track; avoid restarting it every frame

        full_path = self.assets.asset_dir / relative_path
        try:
            pygame.mixer.music.load(str(full_path))
            pygame.mixer.music.set_volume(self._effective_music_volume())
            pygame.mixer.music.play(loops=-1 if loop else 0)
            self._current_music_track = relative_path
        except Exception as exc:  # noqa: BLE001 - missing/broken music must not crash the app
            logger.warning("Could not play music '%s': %s", relative_path, exc)
            self._current_music_track = None

    def stop_music(self) -> None:
        if not self._available:
            return
        try:
            pygame.mixer.music.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not stop music: %s", exc)
        self._current_music_track = None

    def play_sfx(self, relative_path: str) -> None:
        """Play a one-shot sound effect. Missing files play silence."""
        if not self._available or self._muted:
            return
        sound = self.assets.load_sound(relative_path)
        if sound is None:
            return
        try:
            sound.set_volume(self._effective_sfx_volume())
            sound.play()
        except Exception as exc:  # noqa: BLE001 - playback issues must not crash the app
            logger.debug("Could not play sound '%s': %s", relative_path, exc)
