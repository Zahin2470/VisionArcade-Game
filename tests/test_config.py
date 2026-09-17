"""Tests for `visionarcade.config`."""

from __future__ import annotations

import pytest

from visionarcade.config import AppConfig, config_from_args
from visionarcade.constants import (
    DEFAULT_CAMERA_INDEX,
    DEFAULT_FPS_TARGET,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)


def test_default_config_matches_constants():
    config = AppConfig()
    assert config.camera_index == DEFAULT_CAMERA_INDEX
    assert config.window_width == DEFAULT_WINDOW_WIDTH
    assert config.window_height == DEFAULT_WINDOW_HEIGHT
    assert config.fps_target == DEFAULT_FPS_TARGET
    assert config.debug is False
    assert config.selected_game is None


def test_config_is_immutable():
    config = AppConfig()
    with pytest.raises(Exception):
        config.debug = True  # type: ignore[misc]


def test_with_overrides_returns_new_instance():
    original = AppConfig()
    updated = original.with_overrides(debug=True, camera_index=2)

    assert original.debug is False
    assert original.camera_index == DEFAULT_CAMERA_INDEX
    assert updated.debug is True
    assert updated.camera_index == 2


def test_config_from_args_defaults():
    config = config_from_args([])
    assert config.debug is False
    assert config.selected_game is None
    assert config.camera_index == DEFAULT_CAMERA_INDEX


def test_config_from_args_parses_all_flags():
    config = config_from_args(["--debug", "--game", "pong", "--camera", "3"])
    assert config.debug is True
    assert config.selected_game == "pong"
    assert config.camera_index == 3
    assert config.simulate is False


def test_config_from_args_parses_simulate_flag():
    config = config_from_args(["--simulate"])
    assert config.simulate is True


def test_config_from_args_rejects_unknown_game(capsys):
    with pytest.raises(SystemExit):
        config_from_args(["--game", "not-a-real-game"])
