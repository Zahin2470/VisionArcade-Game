"""Tests for `visionarcade.arcade.scoring`."""

from __future__ import annotations

import pytest

from visionarcade.arcade.scoring import ComboTracker, ScoreTracker


# --- ScoreTracker --------------------------------------------------------

def test_score_starts_at_zero():
    tracker = ScoreTracker()
    assert tracker.score == 0


def test_add_increments_score():
    tracker = ScoreTracker()
    tracker.add(10)
    assert tracker.score == 10


def test_add_applies_multiplier_and_rounds():
    tracker = ScoreTracker()
    gained = tracker.add(10, multiplier=2.5)
    assert gained == 25
    assert tracker.score == 25


def test_add_returns_amount_gained():
    tracker = ScoreTracker()
    gained = tracker.add(7, multiplier=1.0)
    assert gained == 7


def test_reset_zeros_score():
    tracker = ScoreTracker()
    tracker.add(50)
    tracker.reset()
    assert tracker.score == 0


# --- ComboTracker ----------------------------------------------------------

def test_combo_starts_at_zero_streak_and_multiplier_one():
    combo = ComboTracker()
    assert combo.streak == 0
    assert combo.multiplier == pytest.approx(1.0)


def test_register_hit_increments_streak_and_multiplier():
    combo = ComboTracker(multiplier_step=0.5)
    combo.register_hit()
    assert combo.streak == 1
    assert combo.multiplier == pytest.approx(1.5)
    combo.register_hit()
    assert combo.streak == 2
    assert combo.multiplier == pytest.approx(2.0)


def test_multiplier_is_capped_at_max():
    combo = ComboTracker(max_multiplier=2.0, multiplier_step=1.0)
    for _ in range(10):
        combo.register_hit()
    assert combo.multiplier == pytest.approx(2.0)


def test_register_miss_resets_streak():
    combo = ComboTracker()
    combo.register_hit()
    combo.register_hit()
    combo.register_miss()
    assert combo.streak == 0
    assert combo.multiplier == pytest.approx(1.0)


def test_best_streak_tracks_the_highest_ever_reached():
    combo = ComboTracker()
    combo.register_hit()
    combo.register_hit()
    combo.register_hit()
    combo.register_miss()
    combo.register_hit()
    assert combo.streak == 1
    assert combo.best_streak == 3


def test_idle_timeout_breaks_the_streak():
    combo = ComboTracker(combo_timeout_seconds=1.0)
    combo.register_hit()
    combo.update(0.5)
    assert combo.streak == 1  # not yet timed out
    combo.update(0.6)
    assert combo.streak == 0  # timed out


def test_update_with_no_streak_does_nothing():
    combo = ComboTracker(combo_timeout_seconds=1.0)
    combo.update(5.0)  # must not raise with streak already at 0
    assert combo.streak == 0


def test_a_hit_before_timeout_resets_the_idle_clock():
    combo = ComboTracker(combo_timeout_seconds=1.0)
    combo.register_hit()
    combo.update(0.9)
    combo.register_hit()  # resets the idle timer
    combo.update(0.9)
    assert combo.streak == 2  # still under 1.0s since the second hit


def test_reset_clears_streak_and_best_streak():
    combo = ComboTracker()
    combo.register_hit()
    combo.register_hit()
    combo.reset()
    assert combo.streak == 0
    assert combo.best_streak == 0
