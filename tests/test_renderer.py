"""Tests for `visionarcade.rendering.renderer.Renderer`.

These run against real pygame calls, backed by the dummy SDL video
driver configured in conftest.py — no real window or GPU is needed.
"""

from __future__ import annotations

import pygame
import pytest

from visionarcade.rendering.renderer import Renderer, RendererError


def test_open_creates_surface_of_requested_size(renderer):
    assert renderer.is_open is True
    assert renderer.surface.get_size() == (320, 240)


def test_surface_access_before_open_raises():
    r = Renderer(width=100, height=100)
    with pytest.raises(RendererError):
        _ = r.surface


def test_open_is_idempotent(renderer):
    renderer.open()  # should not raise or recreate awkwardly
    assert renderer.is_open is True


def test_clear_fills_surface_with_color(renderer):
    renderer.clear((10, 20, 30))
    assert renderer.surface.get_at((0, 0))[:3] == (10, 20, 30)


def test_draw_placeholder_text_does_not_raise(renderer):
    renderer.clear()
    renderer.draw_placeholder_text("VisionArcade")
    renderer.present()  # should not raise


def test_pump_events_true_with_no_events(renderer):
    pygame.event.clear()
    running, keys = renderer.pump_events()
    assert running is True
    assert keys == []


def test_pump_events_false_on_quit_event(renderer):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    running, keys = renderer.pump_events()
    assert running is False


def test_pump_events_reports_keydown_but_escape_no_longer_quits(renderer):
    # With real menus now in place, each screen interprets Escape itself
    # (e.g. "back"); the renderer must not treat it as a global quit.
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    running, keys = renderer.pump_events()
    assert running is True
    assert pygame.K_ESCAPE in keys


def test_pump_events_collects_multiple_keydowns_in_order(renderer):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    running, keys = renderer.pump_events()
    assert running is True
    assert keys == [pygame.K_LEFT, pygame.K_RETURN]


def test_close_is_idempotent(renderer):
    renderer.close()
    renderer.close()
    assert renderer.is_open is False


def test_context_manager_opens_and_closes():
    with Renderer(width=64, height=64) as r:
        assert r.is_open is True
    assert r.is_open is False
