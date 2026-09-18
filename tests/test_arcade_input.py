"""Tests for `visionarcade.arcade.input.build_game_input`."""

from __future__ import annotations

import pygame

from visionarcade.arcade.input import build_game_input, map_point_to_rect
from visionarcade.vision.gestures import FrameIntent, HandIntent, PinchState
from visionarcade.vision.motion import SwipeDirection


def _absent(handedness="Left") -> HandIntent:
    return HandIntent.absent(handedness)


def test_no_hand_present_yields_no_pointer():
    intent = FrameIntent(left=_absent("Left"), right=_absent("Right"))
    play_area = pygame.Rect(0, 0, 200, 100)
    game_input = build_game_input(intent, play_area)
    assert game_input.pointer is None


def test_hand_position_maps_into_play_area_pixel_space():
    right = HandIntent(handedness="Right", present=True, position=(0.5, 0.5))
    intent = FrameIntent(left=_absent("Left"), right=right)
    play_area = pygame.Rect(100, 50, 200, 100)  # x:100-300, y:50-150
    game_input = build_game_input(intent, play_area)
    assert game_input.pointer == (200.0, 100.0)  # center of the play area


def test_pointer_at_play_area_origin():
    right = HandIntent(handedness="Right", present=True, position=(0.0, 0.0))
    intent = FrameIntent(left=_absent("Left"), right=right)
    play_area = pygame.Rect(50, 20, 400, 300)
    game_input = build_game_input(intent, play_area)
    assert game_input.pointer == (50.0, 20.0)


def test_pinch_state_and_edges_pass_through():
    right = HandIntent(handedness="Right", present=True, position=(0.5, 0.5), pinch_state=PinchState.START)
    intent = FrameIntent(left=_absent("Left"), right=right)
    game_input = build_game_input(intent, pygame.Rect(0, 0, 100, 100))
    assert game_input.pinch_state == PinchState.START
    assert game_input.pinch_just_started is True
    assert game_input.pinch_just_released is False


def test_pinch_release_edge():
    right = HandIntent(handedness="Right", present=True, position=(0.5, 0.5), pinch_state=PinchState.RELEASE)
    intent = FrameIntent(left=_absent("Left"), right=right)
    game_input = build_game_input(intent, pygame.Rect(0, 0, 100, 100))
    assert game_input.pinch_just_released is True
    assert game_input.pinch_just_started is False


def test_swipe_and_velocity_pass_through():
    right = HandIntent(
        handedness="Right",
        present=True,
        position=(0.5, 0.5),
        velocity=(1.2, -0.3),
        swipe=SwipeDirection.LEFT,
    )
    intent = FrameIntent(left=_absent("Left"), right=right)
    game_input = build_game_input(intent, pygame.Rect(0, 0, 100, 100))
    assert game_input.swipe == SwipeDirection.LEFT
    assert game_input.velocity == (1.2, -0.3)


def test_prefers_right_hand_over_left():
    left = HandIntent(handedness="Left", present=True, position=(0.0, 0.0))
    right = HandIntent(handedness="Right", present=True, position=(1.0, 1.0))
    intent = FrameIntent(left=left, right=right)
    play_area = pygame.Rect(0, 0, 100, 100)
    game_input = build_game_input(intent, play_area)
    assert game_input.pointer == (100.0, 100.0)  # right hand's mapped position


def test_falls_back_to_left_hand_when_right_absent():
    left = HandIntent(handedness="Left", present=True, position=(0.25, 0.25))
    intent = FrameIntent(left=left, right=_absent("Right"))
    play_area = pygame.Rect(0, 0, 100, 100)
    game_input = build_game_input(intent, play_area)
    assert game_input.pointer == (25.0, 25.0)


# --- map_point_to_rect (used directly by two-hand games like Pong) -----------

def test_map_point_to_rect_none_returns_none():
    assert map_point_to_rect(None, pygame.Rect(0, 0, 100, 100)) is None


def test_map_point_to_rect_maps_into_pixel_space():
    rect = pygame.Rect(50, 20, 200, 100)
    assert map_point_to_rect((0.5, 0.5), rect) == (150.0, 70.0)


def test_map_point_to_rect_origin_and_corner():
    rect = pygame.Rect(10, 10, 100, 50)
    assert map_point_to_rect((0.0, 0.0), rect) == (10.0, 10.0)
    assert map_point_to_rect((1.0, 1.0), rect) == (110.0, 60.0)
