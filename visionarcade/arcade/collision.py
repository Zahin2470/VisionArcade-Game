"""Reusable geometric collision helpers shared across mini-games.

Kept as small, pure, easily-testable functions rather than duplicated
inline math in each game — the project's testing requirements call out
"collision helpers" as their own testable concern.
"""

from __future__ import annotations

import pygame


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
