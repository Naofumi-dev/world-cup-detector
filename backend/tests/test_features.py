"""Tests for point-in-time feature engineering (no lookahead leakage)."""
from datetime import date
from types import SimpleNamespace

from app.features import (
    FEATURE_NAMES,
    TeamState,
    build_training_frame,
    match_features,
    replay,
    result_label,
)


def m(home, away, hs, as_, tournament="Friendly", neutral=True, day=1):
    return SimpleNamespace(
        date=date(2000, 1, day),
        home_team=home,
        away_team=away,
        home_score=hs,
        away_score=as_,
        tournament=tournament,
        neutral=neutral,
    )


def test_result_label():
    assert result_label(2, 0) == "H"
    assert result_label(0, 1) == "A"
    assert result_label(1, 1) == "D"


def test_teamstate_defaults_and_record():
    s = TeamState()
    assert s.form() == 1.5  # neutral prior with no games
    assert s.avg_gd() == 0.0
    s.record(3, 2)
    s.record(0, -1)
    assert s.form() == 1.5  # (3 + 0) / 2
    assert s.avg_gd() == 0.5  # (2 + -1) / 2
    assert s.n == 2


def test_match_features_keys_and_values():
    home = TeamState(elo=1600)
    away = TeamState(elo=1500)
    f = match_features(home, away, neutral=False, tournament="FIFA World Cup")
    assert list(f.keys()) == FEATURE_NAMES
    assert f["elo_diff"] == 100
    assert f["home_advantage"] == 1.0
    assert f["tournament_importance"] == 1.0  # 60/60


def test_replay_is_point_in_time():
    # Team A thrashes B in match 1, so A's form must be the prior (1.5) for
    # match 1 and only reflect the win from match 2 onward.
    matches = [
        m("A", "B", 4, 0, day=1),
        m("A", "C", 0, 0, day=2),
    ]
    steps = list(replay(matches))
    assert steps[0].features["home_form"] == 1.5  # no history yet
    assert steps[0].home_history == 0
    # Match 2: A now has one prior result (a win = 3 pts) in the window.
    assert steps[1].features["home_form"] == 3.0
    assert steps[1].home_history == 1
    # Elo carried forward: A's pre-match Elo in match 2 == its post-match-1 Elo.
    assert steps[1].home_elo_before == steps[0].home_elo_after


def test_build_training_frame_shape_and_min_history():
    # Two teams alternating so both accumulate history quickly.
    matches = [m("A", "B", 1, 0, day=d) for d in range(1, 12)]
    X, y = build_training_frame(matches, min_history=3)
    assert list(X.columns) == FEATURE_NAMES
    assert len(X) == len(y)
    # First 3 matches (history 0,1,2 for the home side) are dropped.
    assert len(X) == 11 - 3
