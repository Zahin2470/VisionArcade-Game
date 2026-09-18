"""Maps a stabilized `FrameIntent` into game-ready pointer/button state.

Every mini-game receives a `FrameIntent` via `ArcadeGame.handle_intent`
per the shared interface, but each one still needs the same few
things: a screen-space pointer position, and simple button-style edges
for pinch. Building that here once — rather than inside every game —
is what "never duplicate hand-tracking code inside individual games"
means in practice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import pygame

from visionarcade.vision.gestures import FrameIntent, PinchState
from visionarcade.vision.motion import SwipeDirection

Point = Tuple[float, float]


@dataclass(frozen=True)
class GameInput:
    """One frame's game-ready input, derived from a `FrameIntent`."""

    pointer: Optional[Point]  # primary hand position mapped into the play area's pixel space
    pinch_state: PinchState
    pinch_just_started: bool
    pinch_just_released: bool
    swipe: Optional[SwipeDirection]
    velocity: Point  # normalized units/second, same convention as HandIntent.velocity


def map_point_to_rect(point: Optional[Point], rect: pygame.Rect) -> Optional[Point]:
    """Map a normalized [0, 1] point into `rect`'s pixel space, or None
    if `point` is None. Shared by `build_game_input` (for the primary
    hand) and directly by two-hand games like Pong, which need to map
    each hand's position independently rather than just the primary one."""
    if point is None:
        return None
    return (rect.x + point[0] * rect.width, rect.y + point[1] * rect.height)


def build_game_input(intent: FrameIntent, play_area: pygame.Rect) -> GameInput:
    """Map the primary hand's intent into `play_area`'s pixel space."""
    hand = intent.primary()
    pointer = map_point_to_rect(hand.position, play_area) if hand.present else None

    return GameInput(
        pointer=pointer,
        pinch_state=hand.pinch_state,
        pinch_just_started=hand.pinch_state == PinchState.START,
        pinch_just_released=hand.pinch_state == PinchState.RELEASE,
        swipe=hand.swipe,
        velocity=hand.velocity,
    )
