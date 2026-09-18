"""Tests for `visionarcade.persistence.storage`."""

from __future__ import annotations

from visionarcade.persistence.storage import atomic_write_json, read_json_or_none


def test_round_trip(tmp_path):
    path = tmp_path / "data.json"
    assert atomic_write_json(path, {"a": 1, "b": [1, 2, 3]}) is True
    assert read_json_or_none(path) == {"a": 1, "b": [1, 2, 3]}


def test_read_missing_file_returns_none(tmp_path):
    assert read_json_or_none(tmp_path / "missing.json") is None


def test_read_corrupted_file_returns_none_without_raising(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert read_json_or_none(path) is None  # must not raise


def test_write_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "data.json"
    assert atomic_write_json(path, {"x": 1}) is True
    assert path.exists()


def test_write_failure_returns_false_without_raising(tmp_path):
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("x", encoding="utf-8")
    bad_path = blocking_file / "data.json"
    assert atomic_write_json(bad_path, {"x": 1}) is False


def test_write_does_not_leave_a_temp_file_behind_on_success(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"a": 1})
    assert not (tmp_path / "data.json.tmp").exists()
