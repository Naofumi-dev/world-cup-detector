"""Model status and retrain endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import predictor
from ..db import get_db
from ..models import Match

router = APIRouter(tags=["model"])


@router.get("/model")
def model_info():
    """Current model metrics (accuracy, log-loss, last trained, ...)."""
    metrics = predictor.get_metrics()
    if metrics is None:
        raise HTTPException(status_code=404, detail="No model trained yet.")
    return metrics


@router.post("/model/retrain")
def retrain(db: Session = Depends(get_db)):
    """Retrain the classifier on all matches and return fresh metrics."""
    matches = db.execute(select(Match).order_by(Match.date, Match.id)).scalars().all()
    return predictor.train(matches)
