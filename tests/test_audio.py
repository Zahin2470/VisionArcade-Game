"""Tests for `visionarcade.audio.manager.AudioManager`.

These run against the real pygame mixer, backed by the dummy SDL audio
driver configured in conftest.py — no real audio device is needed.
"""

from __future__ import annotations

import pygame
import pytest

from visionarcade.audio.manager import AudioManager
from visionarcade.utils.assets import AssetManager


def test_audio_manager_initializes_available_on_dummy_driver():
    manager = AudioManager()
    assert manager.available is True


def test_apply_settings_updates_music_volume():
    manager = AudioManager()
    manager.apply_settings(master_volume=0.5, sfx_volume=1.0, music_volume=0.8, muted=False)
    # SDL_mixer stores volume at 8-bit resolution, so expect a small
    # quantization difference rather than exact floating-point equality.
    assert pygame.mixer.music.get_volume() == pytest.approx(0.4, abs=0.01)


def test_muted_sets_music_volume_to_zero():
    manager = AudioManager()
    manager.apply_settings(master_volume=1.0, sfx_volume=1.0, music_volume=1.0, muted=True)
    assert pygame.mixer.music.get_volume() == pytest.approx(0.0)


def test_apply_settings_clamps_out_of_range_values():
    manager = AudioManager()
    manager.apply_settings(master_volume=5.0, sfx_volume=-2.0, music_volume=2.0, muted=False)
    assert pygame.mixer.music.get_volume() == pytest.approx(1.0)  # clamped 1.0 * 1.0


def test_play_music_with_missing_file_does_not_raise(tmp_path):
    manager = AudioManager(assets=AssetManager(asset_dir=tmp_path))
    manager.play_music("does_not_exist.ogg")  # must not raise
    assert True


def test_play_sfx_with_missing_file_does_not_raise(tmp_path):
    manager = AudioManager(assets=AssetManager(asset_dir=tmp_path))
    manager.play_sfx("does_not_exist.wav")  # must not raise
    assert True


def test_play_sfx_while_muted_is_a_no_op(tmp_path):
    manager = AudioManager(assets=AssetManager(asset_dir=tmp_path))
    manager.apply_settings(master_volume=1.0, sfx_volume=1.0, music_volume=1.0, muted=True)
    manager.play_sfx("does_not_exist.wav")  # must not raise even while muted
    assert True


def test_stop_music_without_playing_does_not_raise():
    manager = AudioManager()
    manager.stop_music()  # must not raise
    assert True
