"""World Cup tournament simulation endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import predictor, tournament
from ..db import get_db
from ..schemas import TournamentRequest, TournamentResponse

router = APIRouter(tags=["tournament"])


@router.post("/tournament/simulate", response_model=TournamentResponse)
def simulate(req: TournamentRequest, db: Session = Depends(get_db)):
    """Monte-Carlo simulate the 2026 World Cup and return per-team stage odds."""
    try:
        predictor.load_model()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Model not trained yet.")
    return tournament.simulate(db, runs=req.runs)
