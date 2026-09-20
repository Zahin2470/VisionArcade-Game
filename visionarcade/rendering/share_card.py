"""Share-card generation: a simple PNG summarizing a completed round,
saved locally so a player can share their result.

This is the only module in the project that imports Pillow — kept
isolated so the rest of the rendering layer stays pygame-only. Never
raises: a failure here (a missing font, a bad path) should degrade to
"no share card was saved" rather than crash a results screen.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_CARD_SIZE = (1200, 630)  # a common social-share aspect ratio
_BACKGROUND_COLOR = (18, 20, 28)
_ACCENT_COLOR = (90, 170, 255)
_TEXT_COLOR = (235, 238, 245)
_SECONDARY_COLOR = (150, 155, 170)

#: (results key, display label, optional value formatter) for the
#: secondary stat lines — only keys actually present are drawn, so
#: this one list covers every game's differently-shaped results dict.
_STAT_LINES = (
    ("best_streak", "Best Streak", str),
    ("accuracy", "Accuracy", lambda v: f"{v * 100:.0f}%"),
    ("average_reaction_time", "Avg Reaction", lambda v: f"{v:.2f}s"),
    ("stage_reached", "Stage Reached", str),
    ("targets_sliced", "Targets Sliced", str),
    ("pieces_placed", "Pieces Placed", str),
)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:  # noqa: BLE001 - missing font must not crash the app
        return ImageFont.load_default()


def generate_share_card(game_title: str, results: Dict[str, Any], output_path: Path) -> bool:
    """Render a PNG share card summarizing `results` to `output_path`.

    Returns True on success, False on any failure — a share card is a
    nice-to-have, never something that should crash the results screen.
    """
    try:
        image = Image.new("RGB", _CARD_SIZE, _BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)

        draw.text((60, 50), "VisionArcade", font=_load_font(40), fill=_ACCENT_COLOR)
        draw.text((60, 140), game_title, font=_load_font(64), fill=_TEXT_COLOR)

        score = results.get("score", 0)
        draw.text((60, 240), f"Score: {score}", font=_load_font(56), fill=_TEXT_COLOR)

        outcome = results.get("outcome")
        if outcome and outcome != "in_progress":
            draw.text(
                (60, 320), str(outcome).replace("_", " ").title(), font=_load_font(32), fill=_SECONDARY_COLOR
            )

        y = 390
        for key, label, formatter in _STAT_LINES:
            value = results.get(key)
            if value is None:
                continue
            try:
                display_value = formatter(value)
            except Exception:  # noqa: BLE001 - a bad value must not block the rest of the card
                display_value = str(value)
            draw.text((60, y), f"{label}: {display_value}", font=_load_font(28), fill=_SECONDARY_COLOR)
            y += 36

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")
        return True
    except Exception as exc:  # noqa: BLE001 - image/disk I/O must not crash the app
        logger.warning("Could not generate share card '%s': %s", output_path, exc)
        return False
