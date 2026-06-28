"""Team listing, leaderboard, and per-team detail endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import service
from ..db import get_db
from ..models import Match, Team
from ..schemas import MatchOut, RankedTeam, TeamDetail, TeamOut

router = APIRouter(tags=["teams"])


@router.get("/teams", response_model=list[TeamOut])
def list_teams(search: str | None = None, db: Session = Depends(get_db)):
    """All teams, strongest first. Optional name search (for dropdowns)."""
    q = select(Team).order_by(Team.elo_rating.desc())
    if search:
        q = q.where(Team.name.ilike(f"%{search}%"))
    return db.execute(q).scalars().all()


@router.get("/rankings", response_model=list[RankedTeam])
def rankings(limit: int = 20, db: Session = Depends(get_db)):
    """Top teams by Elo with explicit rank numbers (leaderboard)."""
    teams = (
        db.execute(select(Team).order_by(Team.elo_rating.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        RankedTeam(
            rank=i + 1,
            name=t.name,
            elo_rating=t.elo_rating,
            matches_played=t.matches_played,
            wins=t.wins,
            draws=t.draws,
            losses=t.losses,
            goals_for=t.goals_for,
            goals_against=t.goals_against,
        )
        for i, t in enumerate(teams)
    ]


@router.get("/teams/{name}", response_model=TeamDetail)
def team_detail(name: str, db: Session = Depends(get_db)):
    """Stats, recent matches, and full Elo trajectory for one team."""
    team = service.get_team(db, name)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team not found: {name}")
    recent = (
        db.execute(
            select(Match)
            .where(or_(Match.home_team == name, Match.away_team == name))
            .order_by(Match.date.desc(), Match.id.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    return TeamDetail(
        team=TeamOut.model_validate(team),
        recent_matches=[MatchOut.model_validate(m) for m in recent],
        rating_history=service.rating_history(db, name),
    )
