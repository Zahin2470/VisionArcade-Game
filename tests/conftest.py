"""Shared pytest fixtures and headless-environment setup.

This module runs before any test module imports pygame, so it sets the
SDL video/audio drivers to "dummy" here — the entire suite then runs
without a real display or audio device, which is what lets the base
renderer and asset manager be tested with genuine (non-mocked) pygame
calls instead of mocks.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402 - must follow the environment setup above
import pytest

from visionarcade.rendering.renderer import Renderer


@pytest.fixture
def renderer():
    """A `Renderer` opened against the dummy driver, closed afterward."""
    r = Renderer(width=320, height=240, title="VisionArcade Test")
    r.open()
    yield r
    r.close()


@pytest.fixture(autouse=True)
def _quiet_pygame_mixer():
    """Ensure the mixer is initialized (dummy audio) for sound-related tests."""
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init()
        except Exception:
            # Some environments truly have no audio backend at all; tests
            # that need the mixer will skip/fail informatively on their own.
            pass
    yield
