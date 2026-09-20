"""A processed camera preview: never a raw, unprocessed webcam
rectangle.

The feed is scaled and cropped to fill its target rect cleanly (cover
fit, no letterbox gaps, no distorted aspect ratio), with a cached
vignette and a live/no-signal status badge. Built so a player can see
and understand their own tracked hand movement while actually playing
— not just as a debug tool — since not being able to see the camera
feed makes gesture-based interaction hard to learn or trust.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import cv2
import numpy as np
import pygame

from visionarcade.rendering.themes import Theme
from visionarcade.rendering.typography import Typography


def frame_to_surface(frame_bgr: np.ndarray) -> pygame.Surface:
    """Convert an OpenCV BGR frame into a pygame Surface."""
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    frame_rgb = np.transpose(frame_rgb, (1, 0, 2))  # (h, w, c) -> (w, h, c) for pygame
    return pygame.surfarray.make_surface(frame_rgb)


def _fit_cover(frame_surface: pygame.Surface, target_size: Tuple[int, int]) -> pygame.Surface:
    """Scale and crop `frame_surface` to exactly fill `target_size`
    (cover fit) — the feed fills its rect cleanly with no letterbox
    gaps, cropping any excess rather than distorting aspect ratio."""
    src_w, src_h = frame_surface.get_size()
    target_w, target_h = target_size
    if src_w <= 0 or src_h <= 0 or target_w <= 0 or target_h <= 0:
        return pygame.Surface((max(1, target_w), max(1, target_h)))

    scale = max(target_w / src_w, target_h / src_h)
    scaled_w, scaled_h = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    scaled = pygame.transform.smoothscale(frame_surface, (scaled_w, scaled_h))

    crop_x = max(0, (scaled_w - target_w) // 2)
    crop_y = max(0, (scaled_h - target_h) // 2)
    cropped = pygame.Surface((target_w, target_h))
    cropped.blit(scaled, (0, 0), pygame.Rect(crop_x, crop_y, target_w, target_h))
    return cropped


def _build_vignette(size: Tuple[int, int]) -> pygame.Surface:
    """A smooth radial-darkening overlay toward the edges, computed
    once via numpy (vectorized, so a real per-pixel gradient is cheap
    even though it only ever runs once) and cached by `CameraView`,
    never recomputed per frame."""
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    if width <= 0 or height <= 0:
        return surface

    center_x, center_y = width / 2.0, height / 2.0
    max_dist = math.hypot(center_x, center_y) or 1.0
    ys, xs = np.mgrid[0:height, 0:width]
    normalized_dist = np.sqrt((xs - center_x) ** 2 + (ys - center_y) ** 2) / max_dist
    # Stay fully clear until ~45% out from center, then darken toward the edges.
    alpha = np.clip((normalized_dist - 0.45) / 0.55, 0.0, 1.0) * 150
    alpha_by_column = alpha.astype(np.uint8).T  # surfarray is (width, height)
    pygame.surfarray.pixels_alpha(surface)[:, :] = alpha_by_column
    return surface


class CameraView:
    """Renders a webcam frame into `rect`: cover-fit scaled/cropped,
    vignetted, with a status badge — never an unprocessed rectangle."""

    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = rect
        self._vignette = _build_vignette(rect.size)

    def draw(
        self,
        surface: pygame.Surface,
        frame_bgr: Optional[np.ndarray],
        *,
        camera_available: bool,
        theme: Theme,
        typography: Typography,
        label: Optional[str] = None,
    ) -> None:
        if frame_bgr is None or not camera_available:
            self._draw_unavailable(surface, theme, typography)
            return

        try:
            frame_surface = frame_to_surface(frame_bgr)
            fitted = _fit_cover(frame_surface, self.rect.size)
        except Exception:  # noqa: BLE001 - a bad frame must not crash rendering
            self._draw_unavailable(surface, theme, typography)
            return

        surface.blit(fitted, self.rect.topleft)
        surface.blit(self._vignette, self.rect.topleft)
        pygame.draw.rect(surface, theme.border, self.rect, width=2, border_radius=8)
        self._draw_status_badge(surface, theme, typography, live=True)
        if label:
            typography.render(
                surface, label, "small", theme.text_primary, topleft=(self.rect.x + 8, self.rect.bottom - 22)
            )

    def _draw_unavailable(self, surface: pygame.Surface, theme: Theme, typography: Typography) -> None:
        pygame.draw.rect(surface, theme.surface, self.rect, border_radius=8)
        pygame.draw.rect(surface, theme.border, self.rect, width=2, border_radius=8)
        typography.render(
            surface, "Camera unavailable", "small", theme.text_secondary, center=self.rect.center
        )
        self._draw_status_badge(surface, theme, typography, live=False)

    def _draw_status_badge(self, surface: pygame.Surface, theme: Theme, typography: Typography, live: bool) -> None:
        color = theme.success if live else theme.danger
        center = (self.rect.x + 14, self.rect.y + 14)
        pygame.draw.circle(surface, color, center, 5)
        typography.render(
            surface,
            "LIVE" if live else "NO SIGNAL",
            "small",
            theme.text_primary,
            topleft=(self.rect.x + 24, self.rect.y + 6),
        )
