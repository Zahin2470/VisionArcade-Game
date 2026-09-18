"""Tests for `visionarcade.arcade.collision`."""

from __future__ import annotations

import pygame

from visionarcade.arcade.collision import circle_rect_overlap, distance_to_rect


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
