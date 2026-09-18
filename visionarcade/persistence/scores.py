"""Local high-score and recent-play history persistence.

Scores are stored per game as a capped, timestamp-ordered list.
Loading validates each entry individually — one malformed record (a
missing field, a wrong type) is skipped and logged rather than
discarding every other score in the file, per the project's
persistence requirements.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from visionarcade.constants import MAX_SCORE_HISTORY_PER_GAME, SCORES_FILE_NAME
from visionarcade.persistence.storage import atomic_write_json, read_json_or_none
from visionarcade.utils.paths import get_user_data_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreEntry:
    """One recorded round: what was played, how well, and when."""

    game_id: str
    score: int
    timestamp: float
    difficulty: str = "normal"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> Optional["ScoreEntry"]:
        """Parse one entry, returning None (not raising) if it's malformed."""
        try:
            return ScoreEntry(
                game_id=str(data["game_id"]),
                score=int(data["score"]),
                timestamp=float(data["timestamp"]),
                difficulty=str(data.get("difficulty", "normal")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping a malformed score entry (%s): %r", exc, data)
            return None


class ScoresStore:
    """In-memory score history, one capped list per game."""

    def __init__(self) -> None:
        self._by_game: Dict[str, List[ScoreEntry]] = {}

    def record_score(
        self,
        game_id: str,
        score: int,
        difficulty: str = "normal",
        timestamp: Optional[float] = None,
    ) -> ScoreEntry:
        """Record a new score, most-recent-first, capped per game."""
        entry = ScoreEntry(
            game_id=game_id,
            score=score,
            timestamp=timestamp if timestamp is not None else time.time(),
            difficulty=difficulty,
        )
        entries = self._by_game.setdefault(game_id, [])
        entries.insert(0, entry)
        del entries[MAX_SCORE_HISTORY_PER_GAME:]
        return entry

    def best_score(self, game_id: str) -> Optional[int]:
        entries = self._by_game.get(game_id)
        if not entries:
            return None
        return max(e.score for e in entries)

    def recent(self, game_id: str, limit: int = 10) -> List[ScoreEntry]:
        """Most recent entries for one game, newest first."""
        return list(self._by_game.get(game_id, []))[:limit]

    def recent_across_games(self, limit: int = 10) -> List[ScoreEntry]:
        """A unified "recently played" feed across every game, newest
        first — used by the hub's recent-activity display."""
        all_entries = [entry for entries in self._by_game.values() for entry in entries]
        all_entries.sort(key=lambda e: e.timestamp, reverse=True)
        return all_entries[:limit]

    def known_games(self) -> List[str]:
        return list(self._by_game.keys())

    def reset(self, game_id: Optional[str] = None) -> None:
        """Clear one game's history, or every game's if `game_id` is None.

        Backs the Developer Mode "reset local scores" requirement.
        """
        if game_id is None:
            self._by_game.clear()
        else:
            self._by_game.pop(game_id, None)

    def to_dict(self) -> dict:
        return {
            game_id: [entry.to_dict() for entry in entries]
            for game_id, entries in self._by_game.items()
        }

    @staticmethod
    def from_dict(data: dict) -> "ScoresStore":
        store = ScoresStore()
        if not isinstance(data, dict):
            return store
        for game_id, raw_entries in data.items():
            if not isinstance(raw_entries, list):
                logger.warning("Skipping scores for '%s': not a list.", game_id)
                continue
            parsed = [ScoreEntry.from_dict(raw) for raw in raw_entries]
            valid = [entry for entry in parsed if entry is not None]
            if valid:
                store._by_game[str(game_id)] = valid[:MAX_SCORE_HISTORY_PER_GAME]
        return store


def _scores_path(path: Optional[Path] = None) -> Path:
    return path if path is not None else (get_user_data_dir() / SCORES_FILE_NAME)


def load_scores(path: Optional[Path] = None) -> ScoresStore:
    """Load scores, tolerating a partially corrupted file (bad entries
    are skipped, good ones are kept) or a missing/unreadable file
    (falls back to an empty store)."""
    raw = read_json_or_none(_scores_path(path))
    if raw is None:
        return ScoresStore()
    return ScoresStore.from_dict(raw)


def save_scores(store: ScoresStore, path: Optional[Path] = None) -> bool:
    """Save scores atomically. Returns True/False; never raises."""
    return atomic_write_json(_scores_path(path), store.to_dict())
