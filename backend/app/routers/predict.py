"""Fixture prediction endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import predictor, service
from ..db import get_db
from ..schemas import PredictRequest, PredictResponse

router = APIRouter(tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, db: Session = Depends(get_db)):
    """Predict Win/Draw/Loss probabilities from each team's current state."""
    home_state = service.team_state(db, req.home)
    away_state = service.team_state(db, req.away)
    if home_state is None:
        raise HTTPException(status_code=404, detail=f"Unknown team: {req.home}")
    if away_state is None:
        raise HTTPException(status_code=404, detail=f"Unknown team: {req.away}")

    try:
        model = predictor.load_model()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Model not trained yet.")

    probs = predictor.predict_fixture(
        model, home_state, away_state, req.neutral, req.tournament
    )
    most_likely = max(probs, key=probs.get)
    return PredictResponse(
        home=req.home,
        away=req.away,
        neutral=req.neutral,
        tournament=req.tournament,
        home_elo=round(home_state.elo, 1),
        away_elo=round(away_state.elo, 1),
        home_recent=service.recent_form(db, req.home),
        away_recent=service.recent_form(db, req.away),
        probabilities=probs,
        most_likely=most_likely,
    )
