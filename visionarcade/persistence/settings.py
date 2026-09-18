"""User-adjustable settings: theme, audio, camera, and accessibility
preferences.

`Settings` is always valid — `clamped()` is applied on load and after
every change, so a corrupted or hand-edited settings file can't put
the app into a broken state (e.g. a negative volume or an unknown
theme name).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from visionarcade.constants import (
    CONFIG_FILE_NAME,
    DEFAULT_MASTER_VOLUME,
    DEFAULT_MUSIC_VOLUME,
    DEFAULT_SENSITIVITY,
    DEFAULT_SFX_VOLUME,
    DEFAULT_SMOOTHING_MULTIPLIER,
    DEFAULT_THEME,
    MAX_VOLUME,
    MIN_VOLUME,
    SENSITIVITY_MAX,
    SENSITIVITY_MIN,
    SMOOTHING_MULTIPLIER_MAX,
    SMOOTHING_MULTIPLIER_MIN,
    THEMES,
)
from visionarcade.persistence.storage import atomic_write_json, read_json_or_none
from visionarcade.utils.paths import get_user_data_dir

logger = logging.getLogger(__name__)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class Settings:
    """All user-adjustable preferences, always kept within valid ranges."""

    theme: str = DEFAULT_THEME
    master_volume: float = DEFAULT_MASTER_VOLUME
    sfx_volume: float = DEFAULT_SFX_VOLUME
    music_volume: float = DEFAULT_MUSIC_VOLUME
    muted: bool = False
    camera_mirror: bool = True
    sensitivity: float = DEFAULT_SENSITIVITY
    smoothing_multiplier: float = DEFAULT_SMOOTHING_MULTIPLIER
    high_contrast: bool = False
    reduced_particles: bool = False

    def clamped(self) -> "Settings":
        """Return a copy with every field forced into its valid range."""
        return Settings(
            theme=self.theme if self.theme in THEMES else DEFAULT_THEME,
            master_volume=_clamp(self.master_volume, MIN_VOLUME, MAX_VOLUME),
            sfx_volume=_clamp(self.sfx_volume, MIN_VOLUME, MAX_VOLUME),
            music_volume=_clamp(self.music_volume, MIN_VOLUME, MAX_VOLUME),
            muted=bool(self.muted),
            camera_mirror=bool(self.camera_mirror),
            sensitivity=_clamp(self.sensitivity, SENSITIVITY_MIN, SENSITIVITY_MAX),
            smoothing_multiplier=_clamp(
                self.smoothing_multiplier, SMOOTHING_MULTIPLIER_MIN, SMOOTHING_MULTIPLIER_MAX
            ),
            high_contrast=bool(self.high_contrast),
            reduced_particles=bool(self.reduced_particles),
        )

    def with_overrides(self, **kwargs) -> "Settings":
        """Return a new, clamped copy with the given fields replaced."""
        data = asdict(self)
        data.update(kwargs)
        return Settings(**data).clamped()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Settings":
        defaults = Settings()
        merged = {**asdict(defaults), **{k: v for k, v in data.items() if k in asdict(defaults)}}
        try:
            return Settings(**merged).clamped()
        except (TypeError, ValueError) as exc:
            logger.warning("Settings file had invalid values (%s). Using defaults.", exc)
            return defaults


def _settings_path(path: Optional[Path] = None) -> Path:
    return path if path is not None else (get_user_data_dir() / CONFIG_FILE_NAME)


def load_settings(path: Optional[Path] = None) -> Settings:
    """Load settings, falling back to (clamped) defaults on any problem."""
    raw = read_json_or_none(_settings_path(path))
    if raw is None or not isinstance(raw, dict):
        return Settings()
    return Settings.from_dict(raw)


def save_settings(settings: Settings, path: Optional[Path] = None) -> bool:
    """Save settings atomically. Returns True/False; never raises."""
    return atomic_write_json(_settings_path(path), settings.clamped().to_dict())
