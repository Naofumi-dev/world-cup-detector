"""Seed the database from the historical results CSV.

Reads `data/results.csv`, drops not-yet-played fixtures (NA scores), replays
every match in date order to compute point-in-time Elo, and bulk-loads the
`matches` and `teams` tables. Run directly to (re)seed:

    python -m app.ingest
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .db import Base, SessionLocal, engine, DATA_DIR
from .features import replay
from .models import Match, Team

CSV_PATH = DATA_DIR / "results.csv"


def load_matches_df(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    """Load and clean the results CSV into a chronologically sorted frame."""
    df = pd.read_csv(csv_path)
    # "NA" scores are unplayed fixtures (pandas reads them as NaN); drop them.
    df = df.dropna(subset=["home_score", "away_score"]).copy()
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    df["neutral"] = (
        df["neutral"].astype(str).str.upper().map({"TRUE": True, "FALSE": False}).fillna(False)
    )
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    return df


def seed_database(csv_path: Path = CSV_PATH, reset: bool = True) -> dict:
    """(Re)create tables and load them from the CSV. Returns a summary."""
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    df = load_matches_df(csv_path)

    match_rows: list[dict] = []
    teams: dict[str, dict] = {}

    def team(name: str) -> dict:
        return teams.setdefault(
            name,
            {"elo": 1500.0, "mp": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0},
        )

    for step in replay(df.itertuples(index=False)):
        m = step.match
        match_rows.append(
            {
                "date": m.date,
                "home_team": m.home_team,
                "away_team": m.away_team,
                "home_score": int(m.home_score),
                "away_score": int(m.away_score),
                "tournament": m.tournament,
                "neutral": bool(m.neutral),
                "home_elo_before": step.home_elo_before,
                "away_elo_before": step.away_elo_before,
                "home_elo_after": step.home_elo_after,
                "away_elo_after": step.away_elo_after,
            }
        )

        h, a = team(m.home_team), team(m.away_team)
        h["mp"] += 1
        a["mp"] += 1
        h["gf"] += m.home_score
        h["ga"] += m.away_score
        a["gf"] += m.away_score
        a["ga"] += m.home_score
        h["elo"], a["elo"] = step.home_elo_after, step.away_elo_after
        if step.label == "H":
            h["w"] += 1
            a["l"] += 1
        elif step.label == "A":
            h["l"] += 1
            a["w"] += 1
        else:
            h["d"] += 1
            a["d"] += 1

    now = datetime.now(timezone.utc)
    team_rows = [
        {
            "name": name,
            "elo_rating": s["elo"],
            "matches_played": s["mp"],
            "wins": s["w"],
            "draws": s["d"],
            "losses": s["l"],
            "goals_for": s["gf"],
            "goals_against": s["ga"],
            "updated_at": now,
        }
        for name, s in teams.items()
    ]

    with SessionLocal() as session:
        session.bulk_insert_mappings(Match, match_rows)
        session.bulk_insert_mappings(Team, team_rows)
        session.commit()

    return {"matches": len(match_rows), "teams": len(team_rows)}


def ensure_seeded() -> None:
    """Seed only if the database has no matches yet (used at app startup)."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.query(Match).first() is None:
            seed_database(reset=False)


if __name__ == "__main__":
    summary = seed_database(reset=True)
    print(f"Seeded {summary['matches']} matches across {summary['teams']} teams.")
