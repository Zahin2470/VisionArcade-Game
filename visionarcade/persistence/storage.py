"""Shared, safe JSON read/write helpers for the persistence layer.

Every persisted file (settings, scores, profile) goes through these
two functions so "never corrupt the entire save file, never crash on a
bad one" is implemented once instead of three times. Writes are
atomic (write to a temp file, then rename) so a crash or power loss
mid-write can't leave a half-written, corrupted file behind.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def read_json_or_none(path: Path) -> Optional[Any]:
    """Read and parse JSON from `path`.

    Returns None if the file doesn't exist, can't be read, or isn't
    valid JSON — callers should treat None as "use defaults" rather
    than propagating an exception.
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - a bad save file must not crash the app
        logger.warning("Could not read/parse '%s' (%s). Ignoring it.", path, exc)
        return None


def atomic_write_json(path: Path, data: Any) -> bool:
    """Write `data` as JSON to `path` atomically.

    Returns True on success, False on any failure — never raises, so a
    full disk or permissions problem degrades to "settings didn't
    save" rather than crashing the app.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        return True
    except Exception as exc:  # noqa: BLE001 - disk I/O must not crash the app
        logger.error("Could not save '%s': %s", path, exc)
        return False
