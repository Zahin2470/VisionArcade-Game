"""Tests for `visionarcade.persistence.settings`."""

from __future__ import annotations

from visionarcade.constants import SENSITIVITY_MAX, SENSITIVITY_MIN
from visionarcade.persistence.settings import Settings, load_settings, save_settings


def test_defaults_are_already_clamped():
    settings = Settings()
    assert settings == settings.clamped()


def test_clamped_fixes_out_of_range_values():
    settings = Settings(master_volume=5.0, sfx_volume=-1.0, sensitivity=99.0, theme="not-a-theme")
    clamped = settings.clamped()
    assert clamped.master_volume == 1.0
    assert clamped.sfx_volume == 0.0
    assert clamped.sensitivity == SENSITIVITY_MAX
    assert clamped.theme == "dark"


def test_sensitivity_floor_is_respected():
    settings = Settings(sensitivity=-10.0).clamped()
    assert settings.sensitivity == SENSITIVITY_MIN


def test_with_overrides_returns_a_clamped_copy():
    settings = Settings()
    updated = settings.with_overrides(master_volume=2.0, theme="neon")
    assert updated.master_volume == 1.0  # clamped
    assert updated.theme == "neon"
    assert settings.master_volume == 1.0  # original unaffected (already default 1.0)


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "config.json"
    settings = Settings(theme="light", master_volume=0.4, muted=True, sensitivity=1.3)
    assert save_settings(settings, path=path) is True
    loaded = load_settings(path=path)
    assert loaded == settings


def test_load_missing_file_returns_defaults(tmp_path):
    loaded = load_settings(path=tmp_path / "missing.json")
    assert loaded == Settings()


def test_load_corrupted_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")
    loaded = load_settings(path=path)
    assert loaded == Settings()


def test_load_ignores_unknown_keys_gracefully(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"theme": "neon", "totally_unknown_field": 123}', encoding="utf-8")
    loaded = load_settings(path=path)
    assert loaded.theme == "neon"


def test_load_with_wrong_type_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"master_volume": "loud"}', encoding="utf-8")
    loaded = load_settings(path=path)
    assert loaded == Settings()
