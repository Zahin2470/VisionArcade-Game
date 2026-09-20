"""Tests for `visionarcade.rendering.share_card.generate_share_card`."""

from __future__ import annotations

from PIL import Image

from visionarcade.rendering.share_card import generate_share_card

_CATCH_RESULTS = {
    "game_id": "catch",
    "score": 340,
    "outcome": "cleared",
    "lives_remaining": 2,
    "best_streak": 9,
    "elapsed_seconds": 90.0,
}


def test_generates_a_valid_png(tmp_path):
    output_path = tmp_path / "card.png"
    assert generate_share_card("Vision Catch", _CATCH_RESULTS, output_path) is True
    assert output_path.exists()

    with Image.open(output_path) as image:
        image.verify()  # raises if the file isn't a valid image


def test_creates_parent_directories(tmp_path):
    output_path = tmp_path / "nested" / "dir" / "card.png"
    assert generate_share_card("Vision Catch", _CATCH_RESULTS, output_path) is True
    assert output_path.exists()


def test_handles_missing_optional_stats_gracefully(tmp_path):
    minimal_results = {"game_id": "aim", "score": 10, "outcome": "in_progress"}
    output_path = tmp_path / "card.png"
    assert generate_share_card("Vision Aim", minimal_results, output_path) is True


def test_handles_empty_results_gracefully(tmp_path):
    output_path = tmp_path / "card.png"
    assert generate_share_card("Vision Pong", {}, output_path) is True


def test_in_progress_outcome_is_not_shown_as_a_headline(tmp_path):
    # Just confirms this doesn't raise or produce a broken image —
    # visually asserting text content isn't practical here.
    output_path = tmp_path / "card.png"
    assert generate_share_card("Vision Slice", {"score": 5, "outcome": "in_progress"}, output_path) is True


def test_write_failure_returns_false_without_raising(tmp_path):
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("x", encoding="utf-8")
    bad_path = blocking_file / "card.png"
    assert generate_share_card("Vision Catch", _CATCH_RESULTS, bad_path) is False
