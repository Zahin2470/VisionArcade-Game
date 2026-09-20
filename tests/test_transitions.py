"""Tests for `visionarcade.rendering.transitions.FadeTransition`."""

from __future__ import annotations

from visionarcade.rendering.transitions import FadeTransition


def test_inactive_by_default():
    fade = FadeTransition(320, 240)
    assert fade.is_active is False


def test_start_activates_it():
    fade = FadeTransition(320, 240)
    fade.start()
    assert fade.is_active is True


def test_becomes_inactive_after_full_duration():
    fade = FadeTransition(320, 240, half_duration=0.1)
    fade.start()
    for _ in range(50):  # well past 2*0.1s
        fade.update(1 / 60)
    assert fade.is_active is False


def test_still_active_partway_through():
    fade = FadeTransition(320, 240, half_duration=0.2)
    fade.start()
    fade.update(0.1)
    assert fade.is_active is True


def test_draw_does_not_raise_when_inactive(renderer):
    fade = FadeTransition(renderer.surface.get_width(), renderer.surface.get_height())
    fade.draw(renderer.surface)  # must not raise, and should be a no-op


def test_draw_does_not_raise_when_active(renderer):
    fade = FadeTransition(renderer.surface.get_width(), renderer.surface.get_height(), half_duration=0.15)
    fade.start()
    fade.update(0.05)
    fade.draw(renderer.surface)


def test_restarting_mid_fade_resets_elapsed_time():
    fade = FadeTransition(320, 240, half_duration=0.2)
    fade.start()
    fade.update(0.3)
    fade.start()
    assert fade.is_active is True
    fade.update(0.05)
    assert fade.is_active is True  # not yet done again after a fresh start
