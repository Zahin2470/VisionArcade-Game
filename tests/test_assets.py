"""Tests for `visionarcade.utils.assets.AssetManager`."""

from __future__ import annotations

import pygame
import pytest

from visionarcade.constants import PLACEHOLDER_IMAGE_SIZE
from visionarcade.utils.assets import AssetManager


@pytest.fixture
def real_image_path(tmp_path):
    """Write a tiny real PNG to a temp asset directory and return its dir."""
    surface = pygame.Surface((8, 8))
    surface.fill((200, 100, 50))
    image_path = tmp_path / "sprite.png"
    pygame.image.save(surface, str(image_path))
    return tmp_path


def test_load_image_success(renderer, real_image_path):
    manager = AssetManager(asset_dir=real_image_path)
    image = manager.load_image("sprite.png")
    assert image.get_size() == (8, 8)


def test_load_image_is_cached(renderer, real_image_path):
    manager = AssetManager(asset_dir=real_image_path)
    first = manager.load_image("sprite.png")
    second = manager.load_image("sprite.png")
    assert first is second


def test_load_missing_image_returns_placeholder(renderer, tmp_path):
    manager = AssetManager(asset_dir=tmp_path)
    image = manager.load_image("does_not_exist.png")
    assert image.get_size() == (PLACEHOLDER_IMAGE_SIZE, PLACEHOLDER_IMAGE_SIZE)


def test_load_missing_sound_returns_none_without_raising(tmp_path):
    manager = AssetManager(asset_dir=tmp_path)
    sound = manager.load_sound("does_not_exist.wav")
    assert sound is None


def test_load_missing_sound_is_cached_as_none(tmp_path):
    manager = AssetManager(asset_dir=tmp_path)
    first = manager.load_sound("missing.wav")
    second = manager.load_sound("missing.wav")
    assert first is None and second is None


def test_clear_cache_empties_both_caches(renderer, real_image_path):
    manager = AssetManager(asset_dir=real_image_path)
    manager.load_image("sprite.png")
    manager.load_sound("missing.wav")
    manager.clear_cache()
    assert manager._image_cache == {}
    assert manager._sound_cache == {}
