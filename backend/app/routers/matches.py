"""Recent results feed and add-result endpoint (instant Elo update)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import service
from ..db import get_db
from ..models import Match
from ..schemas import AddResultResponse, MatchCreate, MatchOut

router = APIRouter(tags=["matches"])


@router.get("/matches", response_model=list[MatchOut])
def list_matches(limit: int = 20, team: str | None = None, db: Session = Depends(get_db)):
    """Most recent matches first; optionally filter to one team."""
    q = select(Match).order_by(Match.date.desc(), Match.id.desc())
    if team:
        q = q.where(or_(Match.home_team == team, Match.away_team == team))
    return db.execute(q.limit(limit)).scalars().all()


@router.post("/matches", response_model=AddResultResponse, status_code=201)
def create_match(payload: MatchCreate, db: Session = Depends(get_db)):
    """Record a played match. Both teams' Elo and stats update immediately."""
    match, changes = service.add_result(db, payload)
    return AddResultResponse(match=MatchOut.model_validate(match), changes=changes)
