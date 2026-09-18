"""Tests for `visionarcade.persistence.profiles`."""

from __future__ import annotations

from visionarcade.constants import DISPLAY_NAME_MAX_LENGTH
from visionarcade.persistence.profiles import PlayerProfile, load_profile, save_profile


def test_default_profile():
    profile = PlayerProfile()
    assert profile.display_name == "Player"
    assert profile.total_games_played == 0
    assert profile.last_played_game is None


def test_blank_display_name_falls_back_to_default():
    profile = PlayerProfile(display_name="   ").clamped()
    assert profile.display_name == "Player"


def test_display_name_is_truncated():
    profile = PlayerProfile(display_name="x" * 100).clamped()
    assert len(profile.display_name) == DISPLAY_NAME_MAX_LENGTH


def test_negative_games_played_is_clamped_to_zero():
    profile = PlayerProfile(total_games_played=-5).clamped()
    assert profile.total_games_played == 0


def test_record_game_played_increments_and_sets_last_game():
    profile = PlayerProfile()
    updated = profile.record_game_played("catch")
    assert updated.total_games_played == 1
    assert updated.last_played_game == "catch"
    assert profile.total_games_played == 0  # original unaffected


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "profiles.json"
    profile = PlayerProfile(display_name="Abrar", total_games_played=3, last_played_game="pong")
    assert save_profile(profile, path=path) is True
    loaded = load_profile(path=path)
    assert loaded == profile


def test_load_missing_file_returns_defaults(tmp_path):
    loaded = load_profile(path=tmp_path / "missing.json")
    assert loaded == PlayerProfile()


def test_load_corrupted_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{not valid", encoding="utf-8")
    loaded = load_profile(path=path)
    assert loaded == PlayerProfile()


def test_load_with_wrong_type_falls_back_to_defaults(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text('{"total_games_played": "a lot"}', encoding="utf-8")
    loaded = load_profile(path=path)
    assert loaded == PlayerProfile()
