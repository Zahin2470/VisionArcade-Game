"""Tests for `visionarcade.persistence.scores`."""

from __future__ import annotations

from visionarcade.persistence.scores import ScoresStore, load_scores, save_scores


def test_best_score_is_none_for_unknown_game():
    store = ScoresStore()
    assert store.best_score("catch") is None


def test_record_and_best_score():
    store = ScoresStore()
    store.record_score("catch", 10, timestamp=1.0)
    store.record_score("catch", 25, timestamp=2.0)
    store.record_score("catch", 5, timestamp=3.0)
    assert store.best_score("catch") == 25


def test_recent_is_newest_first():
    store = ScoresStore()
    store.record_score("catch", 10, timestamp=1.0)
    store.record_score("catch", 20, timestamp=2.0)
    recent = store.recent("catch")
    assert [e.score for e in recent] == [20, 10]


def test_recent_respects_limit():
    store = ScoresStore()
    for i in range(5):
        store.record_score("catch", i, timestamp=float(i))
    assert len(store.recent("catch", limit=2)) == 2


def test_history_is_capped_per_game():
    store = ScoresStore()
    from visionarcade.constants import MAX_SCORE_HISTORY_PER_GAME

    for i in range(MAX_SCORE_HISTORY_PER_GAME + 10):
        store.record_score("catch", i, timestamp=float(i))
    assert len(store.recent("catch", limit=1000)) == MAX_SCORE_HISTORY_PER_GAME


def test_recent_across_games_merges_and_sorts_by_time():
    store = ScoresStore()
    store.record_score("catch", 1, timestamp=1.0)
    store.record_score("pong", 2, timestamp=3.0)
    store.record_score("catch", 3, timestamp=2.0)
    merged = store.recent_across_games(limit=10)
    assert [e.score for e in merged] == [2, 3, 1]


def test_reset_one_game_leaves_others_intact():
    store = ScoresStore()
    store.record_score("catch", 10, timestamp=1.0)
    store.record_score("pong", 20, timestamp=1.0)
    store.reset("catch")
    assert store.best_score("catch") is None
    assert store.best_score("pong") == 20


def test_reset_all_games():
    store = ScoresStore()
    store.record_score("catch", 10, timestamp=1.0)
    store.record_score("pong", 20, timestamp=1.0)
    store.reset()
    assert store.known_games() == []


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "scores.json"
    store = ScoresStore()
    store.record_score("catch", 42, timestamp=100.0, difficulty="hard")
    assert save_scores(store, path=path) is True

    loaded = load_scores(path=path)
    assert loaded.best_score("catch") == 42
    assert loaded.recent("catch")[0].difficulty == "hard"


def test_load_missing_file_returns_empty_store(tmp_path):
    store = load_scores(path=tmp_path / "missing.json")
    assert store.known_games() == []


def test_load_skips_malformed_entries_but_keeps_valid_ones(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text(
        '{"catch": ['
        '{"game_id": "catch", "score": 10, "timestamp": 1.0}, '
        '{"score": "not-an-int"}, '
        '{"game_id": "catch", "score": 20, "timestamp": 2.0}'
        "]}",
        encoding="utf-8",
    )
    store = load_scores(path=path)
    scores = sorted(e.score for e in store.recent("catch"))
    assert scores == [10, 20]


def test_load_skips_non_list_game_entries(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text('{"catch": "not-a-list"}', encoding="utf-8")
    store = load_scores(path=path)
    assert store.known_games() == []


def test_load_corrupted_json_returns_empty_store(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text("{not valid", encoding="utf-8")
    store = load_scores(path=path)
    assert store.known_games() == []
