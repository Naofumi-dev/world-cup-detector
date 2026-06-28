"""Point-in-time feature engineering.

Every feature for a match is computed from each team's state *before* that
match is played. The same `TeamState` accumulator drives two things:

* training — `replay()` walks matches in date order, emitting features then
  applying the result, so there is no lookahead leakage; and
* live prediction — the API rebuilds a team's state from its current Elo and
  most recent results, then calls `match_features()` with the same code path.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd

from .ratings import BASE_RATING, tournament_weight, update_ratings

FORM_WINDOW = 10
MAX_TOURNAMENT_WEIGHT = 60.0  # for normalising tournament_importance to ~[0,1]

# Order matters: this is the column order the model is trained and queried with.
FEATURE_NAMES = [
    "elo_diff",
    "home_advantage",
    "home_form",
    "away_form",
    "home_gd",
    "away_gd",
    "tournament_importance",
]


@dataclass
class TeamState:
    """Rolling state for one team: current Elo + recent form window."""

    elo: float = BASE_RATING
    n: int = 0
    points: deque = field(default_factory=lambda: deque(maxlen=FORM_WINDOW))
    gds: deque = field(default_factory=lambda: deque(maxlen=FORM_WINDOW))

    def form(self) -> float:
        """Average points per game over the window (0..3), or 1.5 if no data."""
        return sum(self.points) / len(self.points) if self.points else 1.5

    def avg_gd(self) -> float:
        """Average goal difference over the window."""
        return sum(self.gds) / len(self.gds) if self.gds else 0.0

    def record(self, points: int, goal_diff: int) -> None:
        self.points.append(points)
        self.gds.append(goal_diff)
        self.n += 1


def result_label(home_score: int, away_score: int) -> str:
    """Outcome from the home team's perspective: 'H', 'D', or 'A'."""
    if home_score > away_score:
        return "H"
    if home_score < away_score:
        return "A"
    return "D"


def match_features(
    home: TeamState, away: TeamState, neutral: bool, tournament: str
) -> dict[str, float]:
    """Build the feature dict for a fixture from pre-match team states."""
    return {
        "elo_diff": home.elo - away.elo,
        "home_advantage": 0.0 if neutral else 1.0,
        "home_form": home.form(),
        "away_form": away.form(),
        "home_gd": home.avg_gd(),
        "away_gd": away.avg_gd(),
        "tournament_importance": tournament_weight(tournament) / MAX_TOURNAMENT_WEIGHT,
    }


@dataclass
class ReplayStep:
    match: object
    features: dict[str, float]
    label: str
    home_elo_before: float
    away_elo_before: float
    home_elo_after: float
    away_elo_after: float
    home_history: int
    away_history: int


def replay(matches):
    """Yield a ReplayStep per match, updating per-team state as it goes.

    `matches` is any iterable of objects exposing home_team, away_team,
    home_score, away_score, tournament and neutral. Must be in chronological
    order for the point-in-time guarantee to hold.
    """
    states: dict[str, TeamState] = {}
    for m in matches:
        home = states.setdefault(m.home_team, TeamState())
        away = states.setdefault(m.away_team, TeamState())

        feats = match_features(home, away, bool(m.neutral), m.tournament)
        label = result_label(m.home_score, m.away_score)
        new_home, new_away = update_ratings(
            home.elo, away.elo, m.home_score, m.away_score, m.tournament, bool(m.neutral)
        )

        yield ReplayStep(
            match=m,
            features=feats,
            label=label,
            home_elo_before=home.elo,
            away_elo_before=away.elo,
            home_elo_after=new_home,
            away_elo_after=new_away,
            home_history=home.n,
            away_history=away.n,
        )

        # Apply the result to advance state for subsequent matches.
        gd = m.home_score - m.away_score
        home.elo, away.elo = new_home, new_away
        if label == "H":
            home.record(3, gd)
            away.record(0, -gd)
        elif label == "A":
            home.record(0, gd)
            away.record(3, -gd)
        else:
            home.record(1, gd)
            away.record(1, -gd)


def build_training_frame(matches, min_history: int = 5):
    """Replay matches and return (X DataFrame, y Series) for model training.

    Rows where either side has fewer than `min_history` prior matches are
    dropped to avoid noisy cold-start features.
    """
    rows, labels = [], []
    for step in replay(matches):
        if step.home_history < min_history or step.away_history < min_history:
            continue
        rows.append(step.features)
        labels.append(step.label)
    X = pd.DataFrame(rows, columns=FEATURE_NAMES)
    y = pd.Series(labels, name="result")
    return X, y
