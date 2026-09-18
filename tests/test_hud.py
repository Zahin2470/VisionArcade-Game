"""Tests for `visionarcade.rendering.hud.HUD`."""

from __future__ import annotations

from visionarcade.rendering.hud import HUD
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography


def test_draw_minimal_does_not_raise(renderer):
    hud = HUD(renderer.surface.get_width())
    hud.draw(renderer.surface, Typography(), get_theme("dark"), score=0)


def test_draw_with_lives_does_not_raise(renderer):
    hud = HUD(renderer.surface.get_width())
    hud.draw(
        renderer.surface, Typography(), get_theme("dark"), score=120, lives=2, max_lives=3
    )


def test_draw_with_combo_and_timer_does_not_raise(renderer):
    hud = HUD(renderer.surface.get_width())
    hud.draw(
        renderer.surface,
        Typography(),
        get_theme("neon"),
        score=500,
        lives=1,
        max_lives=3,
        combo=5,
        time_remaining=42.7,
    )


def test_draw_with_negative_time_remaining_does_not_raise(renderer):
    hud = HUD(renderer.surface.get_width())
    hud.draw(renderer.surface, Typography(), get_theme("dark"), score=0, time_remaining=-3.0)
