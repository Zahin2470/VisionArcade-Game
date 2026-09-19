"""Reusable geometric collision helpers shared across mini-games.

Kept as small, pure, easily-testable functions rather than duplicated
inline math in each game — the project's testing requirements call out
"collision helpers" as their own testable concern.
"""

from __future__ import annotations

import math
from typing import Tuple

import pygame

Point = Tuple[float, float]


def circle_rect_overlap(cx: float, cy: float, radius: float, rect: pygame.Rect) -> bool:
    """Whether a circle centered at (cx, cy) overlaps an axis-aligned rect."""
    closest_x = max(rect.left, min(cx, rect.right))
    closest_y = max(rect.top, min(cy, rect.bottom))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx * dx + dy * dy) <= (radius * radius)


def distance_to_rect(cx: float, cy: float, rect: pygame.Rect) -> float:
    """Shortest distance from a point to the edge of a rect (0 if the
    point is inside) — used for "near miss" proximity feedback."""
    closest_x = max(rect.left, min(cx, rect.right))
    closest_y = max(rect.top, min(cy, rect.bottom))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx * dx + dy * dy) ** 0.5


def segment_circle_intersect(p1: Point, p2: Point, cx: float, cy: float, radius: float) -> bool:
    """Whether the line segment from `p1` to `p2` passes through a
    circle centered at (cx, cy). Used to approximate a fast swipe's
    "blade path" (Vision Slice) — checking only each frame's two
    endpoints for a plain point-in-circle overlap would let a fast
    motion pass straight through a target between two sampled frames
    without ever registering a hit; this catches that by testing the
    whole segment, not just its endpoints. A zero-length segment
    (p1 == p2) degrades to a plain point-in-circle check.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy

    if length_sq == 0:
        return math.hypot(cx - x1, cy - y1) <= radius

    t = ((cx - x1) * dx + (cy - y1) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return math.hypot(cx - closest_x, cy - closest_y) <= radius
