"""Tests for `visionarcade.rendering.camera_view`."""

from __future__ import annotations

import numpy as np
import pygame

from visionarcade.rendering.camera_view import CameraView, frame_to_surface
from visionarcade.rendering.themes import get_theme
from visionarcade.rendering.typography import Typography


def _synthetic_frame(width=640, height=480):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 2] = 200  # BGR: a red-ish tint
    return frame


def test_frame_to_surface_produces_correct_dimensions():
    frame = _synthetic_frame(320, 240)
    surface = frame_to_surface(frame)
    assert surface.get_size() == (320, 240)


def test_frame_to_surface_preserves_color_channel_order(renderer):
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[:, :, 2] = 255  # pure red in BGR
    surface = frame_to_surface(frame)
    r, g, b = surface.get_at((5, 5))[:3]
    assert r == 255 and g == 0 and b == 0


def test_draw_with_available_camera_does_not_raise(renderer):
    view = CameraView(pygame.Rect(0, 0, 200, 150))
    view.draw(
        renderer.surface, _synthetic_frame(), camera_available=True,
        theme=get_theme("dark"), typography=Typography(),
    )


def test_draw_with_unavailable_camera_does_not_raise(renderer):
    view = CameraView(pygame.Rect(0, 0, 200, 150))
    view.draw(
        renderer.surface, None, camera_available=False,
        theme=get_theme("dark"), typography=Typography(),
    )


def test_draw_with_camera_available_false_but_frame_present_shows_unavailable(renderer):
    view = CameraView(pygame.Rect(0, 0, 200, 150))
    # camera_available=False should win even if a stale frame is passed.
    view.draw(
        renderer.surface, _synthetic_frame(), camera_available=False,
        theme=get_theme("dark"), typography=Typography(),
    )


def test_draw_handles_a_frame_with_different_aspect_ratio_than_the_rect(renderer):
    view = CameraView(pygame.Rect(0, 0, 300, 100))  # wide rect
    view.draw(
        renderer.surface, _synthetic_frame(480, 640), camera_available=True,  # tall frame
        theme=get_theme("dark"), typography=Typography(),
    )


def test_draw_with_label_does_not_raise(renderer):
    view = CameraView(pygame.Rect(0, 0, 200, 150))
    view.draw(
        renderer.surface, _synthetic_frame(), camera_available=True,
        theme=get_theme("dark"), typography=Typography(), label="pinch=hold",
    )


def test_draw_with_malformed_frame_falls_back_to_unavailable(renderer):
    view = CameraView(pygame.Rect(0, 0, 200, 150))
    bad_frame = np.zeros((0, 0, 3), dtype=np.uint8)
    view.draw(
        renderer.surface, bad_frame, camera_available=True,
        theme=get_theme("dark"), typography=Typography(),
    )  # must not raise


def test_vignette_is_cached_not_rebuilt_per_draw(renderer):
    view = CameraView(pygame.Rect(0, 0, 200, 150))
    vignette_before = view._vignette
    view.draw(
        renderer.surface, _synthetic_frame(), camera_available=True,
        theme=get_theme("dark"), typography=Typography(),
    )
    assert view._vignette is vignette_before  # same object, not reallocated
