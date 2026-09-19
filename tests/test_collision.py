"""Tests for `visionarcade.arcade.collision`."""

from __future__ import annotations

import math

import pygame

from visionarcade.arcade.collision import circle_rect_overlap, distance_to_rect, segment_circle_intersect


def test_circle_inside_rect_overlaps():
    rect = pygame.Rect(0, 0, 100, 100)
    assert circle_rect_overlap(50, 50, 5, rect) is True


def test_circle_far_from_rect_does_not_overlap():
    rect = pygame.Rect(0, 0, 100, 100)
    assert circle_rect_overlap(500, 500, 5, rect) is False


def test_circle_touching_rect_edge_overlaps():
    rect = pygame.Rect(0, 0, 100, 100)
    # Center 10px to the right of the rect's right edge, radius 10 -> just touches.
    assert circle_rect_overlap(110, 50, 10, rect) is True


def test_circle_just_past_touching_does_not_overlap():
    rect = pygame.Rect(0, 0, 100, 100)
    assert circle_rect_overlap(111, 50, 10, rect) is False


def test_distance_to_rect_is_zero_when_inside():
    rect = pygame.Rect(0, 0, 100, 100)
    assert distance_to_rect(50, 50, rect) == 0.0


def test_distance_to_rect_measures_from_nearest_edge():
    rect = pygame.Rect(0, 0, 100, 100)
    assert distance_to_rect(130, 50, rect) == 30.0


def test_distance_to_rect_diagonal_from_corner():
    rect = pygame.Rect(0, 0, 100, 100)
    # 3-4-5 triangle from the (100, 100) corner.
    assert distance_to_rect(103, 104, rect) == 5.0


# --- segment_circle_intersect (Vision Slice blade path) -----------------------

def test_segment_passing_through_circle_center_intersects():
    assert segment_circle_intersect((0, 50), (100, 50), 50, 50, 10) is True


def test_segment_far_from_circle_does_not_intersect():
    assert segment_circle_intersect((0, 0), (100, 0), 50, 500, 10) is False


def test_segment_grazing_circle_edge_intersects():
    # Horizontal segment at y=50; circle centered at (50, 60) radius 10 -> tangent.
    assert segment_circle_intersect((0, 50), (100, 50), 50, 60, 10) is True


def test_segment_just_missing_circle_edge():
    assert segment_circle_intersect((0, 50), (100, 50), 50, 61, 10) is False


def test_segment_endpoint_inside_circle_intersects():
    assert segment_circle_intersect((45, 45), (200, 200), 50, 50, 10) is True


def test_zero_length_segment_degrades_to_point_in_circle():
    assert segment_circle_intersect((50, 50), (50, 50), 50, 50, 10) is True
    assert segment_circle_intersect((0, 0), (0, 0), 50, 50, 10) is False


def test_fast_swipe_catches_a_target_it_would_skip_past_pointwise():
    # A target sitting between two sampled frame positions: neither
    # endpoint is inside the circle, but the segment passes through it.
    p1, p2 = (0, 50), (100, 50)
    cx, cy, radius = 50, 50, 15
    assert math.hypot(cx - p1[0], cy - p1[1]) > radius
    assert math.hypot(cx - p2[0], cy - p2[1]) > radius
    assert segment_circle_intersect(p1, p2, cx, cy, radius) is True
