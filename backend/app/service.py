"""Service layer: bridge the DB to the rating/feature/prediction logic."""
from __future__ import annotations

from datetime import date as date_type, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .features import FORM_WINDOW, TeamState, result_label
from .models import Match, Team
from .ratings import BASE_RATING, update_ratings


def get_team(session: Session, name: str) -> Team | None:
    return session.execute(select(Team).where(Team.name == name)).scalar_one_or_none()


def team_state(session: Session, name: str) -> TeamState | None:
    """Rebuild a team's current state (Elo + recent form) from the DB."""
    team = get_team(session, name)
    if team is None:
        return None
    state = TeamState(elo=team.elo_rating)
    recent = (
        session.execute(
            select(Match)
            .where(or_(Match.home_team == name, Match.away_team == name))
            .order_by(Match.date.desc(), Match.id.desc())
            .limit(FORM_WINDOW)
        )
        .scalars()
        .all()
    )
    for m in reversed(recent):  # oldest -> newest
        gd = (m.home_score - m.away_score) if m.home_team == name else (
            m.away_score - m.home_score
        )
        points = 3 if gd > 0 else (1 if gd == 0 else 0)
        state.record(points, gd)
    return state


def recent_form(session: Session, name: str, n: int = 5) -> list[str]:
    """Last n results for a team as 'W'/'D'/'L' letters, newest first."""
    rows = (
        session.execute(
            select(Match)
            .where(or_(Match.home_team == name, Match.away_team == name))
            .order_by(Match.date.desc(), Match.id.desc())
            .limit(n)
        )
        .scalars()
        .all()
    )
    out = []
    for m in rows:
        gd = (m.home_score - m.away_score) if m.home_team == name else (
            m.away_score - m.home_score
        )
        out.append("W" if gd > 0 else "D" if gd == 0 else "L")
    return out


def _ensure_team(session: Session, name: str) -> Team:
    team = get_team(session, name)
    if team is None:
        team = Team(name=name, elo_rating=BASE_RATING)
        session.add(team)
        session.flush()
    return team


def add_result(session: Session, payload) -> tuple[Match, list[dict]]:
    """Insert a played match and update both teams' Elo + stats immediately.

    Applied to each side's *current* rating, so any later prediction involving
    these teams reflects the new result right away. Returns (match, changes).
    """
    home = _ensure_team(session, payload.home_team)
    away = _ensure_team(session, payload.away_team)

    home_before, away_before = home.elo_rating, away.elo_rating
    new_home, new_away = update_ratings(
        home_before, away_before,
        payload.home_score, payload.away_score,
        payload.tournament, payload.neutral,
    )

    match = Match(
        date=payload.date or datetime.now(timezone.utc).date(),
        home_team=home.name,
        away_team=away.name,
        home_score=payload.home_score,
        away_score=payload.away_score,
        tournament=payload.tournament,
        neutral=payload.neutral,
        home_elo_before=home_before,
        away_elo_before=away_before,
        home_elo_after=new_home,
        away_elo_after=new_away,
    )
    session.add(match)

    label = result_label(payload.home_score, payload.away_score)
    for team, gf, ga, new_elo, outcome in (
        (home, payload.home_score, payload.away_score, new_home, label),
        (away, payload.away_score, payload.home_score, new_away,
         {"H": "A", "A": "H", "D": "D"}[label]),
    ):
        team.elo_rating = new_elo
        team.matches_played += 1
        team.goals_for += gf
        team.goals_against += ga
        team.wins += outcome == "H"
        team.draws += outcome == "D"
        team.losses += outcome == "A"
        team.updated_at = datetime.now(timezone.utc)

    session.commit()
    session.refresh(match)

    changes = [
        {"team": home.name, "elo_before": round(home_before, 1),
         "elo_after": round(new_home, 1), "delta": round(new_home - home_before, 1)},
        {"team": away.name, "elo_before": round(away_before, 1),
         "elo_after": round(new_away, 1), "delta": round(new_away - away_before, 1)},
    ]
    return match, changes


def rating_history(session: Session, name: str) -> list[dict]:
    """Per-match Elo trajectory for a team (for the detail chart)."""
    rows = (
        session.execute(
            select(Match)
            .where(or_(Match.home_team == name, Match.away_team == name))
            .order_by(Match.date, Match.id)
        )
        .scalars()
        .all()
    )
    history = []
    for m in rows:
        elo = m.home_elo_after if m.home_team == name else m.away_elo_after
        history.append({"date": m.date, "elo": round(elo, 1)})
    return history
