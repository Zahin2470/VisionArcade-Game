"""Tests for `visionarcade.utils.paths`."""

from __future__ import annotations

from visionarcade.utils.paths import get_asset_dir, get_package_root, get_user_data_dir


def test_get_user_data_dir_is_created_and_named_after_app():
    data_dir = get_user_data_dir(app_name="VisionArcadeTest")
    assert data_dir.exists()
    assert data_dir.is_dir()
    assert data_dir.name == "VisionArcadeTest"


def test_get_user_data_dir_is_idempotent():
    first = get_user_data_dir(app_name="VisionArcadeTest")
    second = get_user_data_dir(app_name="VisionArcadeTest")
    assert first == second


def test_get_package_root_points_at_visionarcade_package():
    root = get_package_root()
    assert root.name == "visionarcade"
    assert (root / "__init__.py").exists()


def test_get_asset_dir_is_under_package_root():
    assets = get_asset_dir()
    assert assets == get_package_root() / "assets"
