"""Tests for `visionarcade.rendering.typography.Typography`."""

from __future__ import annotations

from visionarcade.rendering.typography import Typography


def test_render_returns_a_rect_and_does_not_raise(renderer):
    typography = Typography()
    rect = typography.render(renderer.surface, "Hello", "body", (255, 255, 255))
    assert rect.width > 0
    assert rect.height > 0


def test_render_defaults_to_surface_center(renderer):
    typography = Typography()
    rect = typography.render(renderer.surface, "Hi", "body", (255, 255, 255))
    assert rect.center == renderer.surface.get_rect().center


def test_render_respects_explicit_topleft(renderer):
    typography = Typography()
    rect = typography.render(renderer.surface, "Hi", "body", (255, 255, 255), topleft=(10, 20))
    assert rect.topleft == (10, 20)


def test_measure_returns_positive_dimensions():
    typography = Typography()
    width, height = typography.measure("Hello world", "body")
    assert width > 0
    assert height > 0


def test_longer_text_measures_wider():
    typography = Typography()
    short_width, _ = typography.measure("Hi", "body")
    long_width, _ = typography.measure("Hello there, world!", "body")
    assert long_width > short_width


def test_fonts_are_cached_per_size():
    typography = Typography()
    typography.measure("a", "body")
    typography.measure("b", "body")
    typography.measure("c", "heading")
    assert len(typography._fonts) == 2  # one per distinct size name


def test_clear_cache_empties_font_cache():
    typography = Typography()
    typography.measure("a", "body")
    typography.clear_cache()
    assert typography._fonts == {}


def test_unknown_size_name_falls_back_to_body_size():
    typography = Typography()
    fallback_width, fallback_height = typography.measure("Hi", "not-a-real-size")
    body_width, body_height = typography.measure("Hi", "body")
    assert (fallback_width, fallback_height) == (body_width, body_height)
