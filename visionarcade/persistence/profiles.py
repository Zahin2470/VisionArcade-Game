"""Player identity: display name and lightweight play history.

Kept deliberately small — preferences live in `settings.py`, per-game
scores live in `scores.py`. This module only owns "who is playing" and
a couple of facts about their overall activity.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from visionarcade.constants import (
    DEFAULT_PLAYER_DISPLAY_NAME,
    DISPLAY_NAME_MAX_LENGTH,
    PROFILES_FILE_NAME,
)
from visionarcade.persistence.storage import atomic_write_json, read_json_or_none
from visionarcade.utils.paths import get_user_data_dir

logger = logging.getLogger(__name__)


def _sanitize_display_name(name: str) -> str:
    cleaned = str(name).strip()
    if not cleaned:
        return DEFAULT_PLAYER_DISPLAY_NAME
    return cleaned[:DISPLAY_NAME_MAX_LENGTH]


@dataclass(frozen=True)
class PlayerProfile:
    """The player's display identity and a couple of activity facts."""

    display_name: str = DEFAULT_PLAYER_DISPLAY_NAME
    total_games_played: int = 0
    last_played_game: Optional[str] = None

    def clamped(self) -> "PlayerProfile":
        return PlayerProfile(
            display_name=_sanitize_display_name(self.display_name),
            total_games_played=max(0, int(self.total_games_played)),
            last_played_game=self.last_played_game,
        )

    def record_game_played(self, game_id: str) -> "PlayerProfile":
        """Return a new profile reflecting one more completed round."""
        return PlayerProfile(
            display_name=self.display_name,
            total_games_played=self.total_games_played + 1,
            last_played_game=game_id,
        ).clamped()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "PlayerProfile":
        defaults = PlayerProfile()
        try:
            return PlayerProfile(
                display_name=str(data.get("display_name", defaults.display_name)),
                total_games_played=int(data.get("total_games_played", 0)),
                last_played_game=data.get("last_played_game"),
            ).clamped()
        except (TypeError, ValueError) as exc:
            logger.warning("Profile file had invalid values (%s). Using defaults.", exc)
            return defaults


def _profile_path(path: Optional[Path] = None) -> Path:
    return path if path is not None else (get_user_data_dir() / PROFILES_FILE_NAME)


def load_profile(path: Optional[Path] = None) -> PlayerProfile:
    """Load the player profile, falling back to defaults on any problem."""
    raw = read_json_or_none(_profile_path(path))
    if raw is None or not isinstance(raw, dict):
        return PlayerProfile()
    return PlayerProfile.from_dict(raw)


def save_profile(profile: PlayerProfile, path: Optional[Path] = None) -> bool:
    """Save the player profile atomically. Returns True/False; never raises."""
    return atomic_write_json(_profile_path(path), profile.clamped().to_dict())
