"""Asset loading and caching.

Missing or broken image/sound files must never crash the game — a
missing image becomes a visible placeholder square, a missing sound
becomes silence. This lets the app keep running (and stay testable)
even before every art/audio asset exists.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import pygame

from visionarcade.constants import PLACEHOLDER_IMAGE_COLOR, PLACEHOLDER_IMAGE_SIZE
from visionarcade.utils.paths import get_asset_dir

logger = logging.getLogger(__name__)


class AssetManager:
    """Loads images and sounds from `asset_dir`, caching by relative path."""

    def __init__(self, asset_dir: Optional[Path] = None) -> None:
        self.asset_dir = asset_dir if asset_dir is not None else get_asset_dir()
        self._image_cache: Dict[str, pygame.Surface] = {}
        self._sound_cache: Dict[str, Optional[pygame.mixer.Sound]] = {}

    def load_image(self, relative_path: str, convert_alpha: bool = True) -> pygame.Surface:
        """Load (and cache) an image. Returns a placeholder on failure."""
        if relative_path in self._image_cache:
            return self._image_cache[relative_path]

        full_path = self.asset_dir / relative_path
        try:
            image = pygame.image.load(str(full_path))
            image = image.convert_alpha() if convert_alpha else image.convert()
        except Exception as exc:  # noqa: BLE001 - asset I/O must not crash the app
            logger.warning(
                "Missing or unreadable image asset '%s' (%s). Using placeholder.",
                relative_path,
                exc,
            )
            image = self._placeholder_surface()

        self._image_cache[relative_path] = image
        return image

    def load_sound(self, relative_path: str) -> Optional[pygame.mixer.Sound]:
        """Load (and cache) a sound. Returns None on failure (silence)."""
        if relative_path in self._sound_cache:
            return self._sound_cache[relative_path]

        full_path = self.asset_dir / relative_path
        sound: Optional[pygame.mixer.Sound] = None
        try:
            sound = pygame.mixer.Sound(str(full_path))
        except Exception as exc:  # noqa: BLE001 - asset/audio backend issues must not crash the app
            logger.warning(
                "Missing or unreadable sound asset '%s' (%s). Playback will be silent.",
                relative_path,
                exc,
            )

        self._sound_cache[relative_path] = sound
        return sound

    def _placeholder_surface(self) -> pygame.Surface:
        surface = pygame.Surface(
            (PLACEHOLDER_IMAGE_SIZE, PLACEHOLDER_IMAGE_SIZE), pygame.SRCALPHA
        )
        surface.fill(PLACEHOLDER_IMAGE_COLOR)
        return surface

    def clear_cache(self) -> None:
        """Drop all cached images/sounds (e.g. on theme change)."""
        self._image_cache.clear()
        self._sound_cache.clear()
