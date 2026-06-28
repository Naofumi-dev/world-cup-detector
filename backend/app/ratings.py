"""Football Elo rating engine.

A World-Football-Elo style system: expected score from the logistic curve,
a K-factor weighted by how important the match is, a margin-of-victory
multiplier, and a home-advantage bonus applied to the home side's effective
rating (skipped for matches on neutral ground).

Updating a single match is O(1), which is what lets the API shift ratings —
and therefore predicted probabilities — the instant a new result is added.
"""
from __future__ import annotations

BASE_RATING = 1500.0
HOME_ADVANTAGE = 65.0  # rating points added to the home side unless neutral


def tournament_weight(tournament: str) -> float:
    """Map a tournament name to its base K-factor (importance).

    Bigger competitions move ratings more. Keyword matching keeps this robust
    to the long tail of tournament names in the dataset.
    """
    t = (tournament or "").lower()
    if "friendly" in t:
        return 20.0
    if "qualification" in t or "qualifier" in t:
        return 35.0
    if "nations league" in t:
        return 40.0
    if "confederations cup" in t:
        return 45.0
    if "fifa world cup" in t:
        return 60.0
    # Continental finals: Euro, Copa America, Africa Cup, Asian Cup, Gold Cup...
    if any(k in t for k in ("uefa euro", "copa am", "african cup", "afc asian",
                            "gold cup", "championship", "cup of nations")):
        return 50.0
    return 30.0


def mov_multiplier(goal_diff: int) -> float:
    """Margin-of-victory multiplier (World Football Elo index)."""
    g = abs(goal_diff)
    if g <= 1:
        return 1.0
    if g == 2:
        return 1.5
    if g == 3:
        return 1.75
    return 1.75 + (g - 3) / 8.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability-like expected score for A against B on the logistic curve."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_ratings(
    home_elo: float,
    away_elo: float,
    home_score: int,
    away_score: int,
    tournament: str,
    neutral: bool,
) -> tuple[float, float]:
    """Return (new_home_elo, new_away_elo) after one played match."""
    ha = 0.0 if neutral else HOME_ADVANTAGE
    exp_home = expected_score(home_elo + ha, away_elo)
    exp_away = 1.0 - exp_home

    if home_score > away_score:
        act_home = 1.0
    elif home_score < away_score:
        act_home = 0.0
    else:
        act_home = 0.5
    act_away = 1.0 - act_home

    k = tournament_weight(tournament) * mov_multiplier(home_score - away_score)
    new_home = home_elo + k * (act_home - exp_home)
    new_away = away_elo + k * (act_away - exp_away)
    return new_home, new_away
