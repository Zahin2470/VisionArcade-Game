"""Cross-platform filesystem path helpers.

No module outside this file should hard-code a personal username, an
absolute path, or a platform-specific directory layout — everything
that needs a writable, per-user location or a path to bundled assets
goes through here so macOS/Windows/Linux all work without changes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from visionarcade.constants import APP_NAME


def get_user_data_dir(app_name: str = APP_NAME) -> Path:
    """Return (and create if needed) a per-user, writable data directory.

    - macOS:   ~/Library/Application Support/<app_name>
    - Windows: %APPDATA%/<app_name>
    - Linux:   $XDG_DATA_HOME/<app_name> or ~/.local/share/<app_name>
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))

    data_dir = base / app_name
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_package_root() -> Path:
    """Return the root directory of the installed `visionarcade` package."""
    return Path(__file__).resolve().parent.parent


def get_asset_dir() -> Path:
    """Return the path to bundled, read-only assets shipped with the app."""
    return get_package_root() / "assets"
