"""Live tournament data: upcoming fixtures + running model accuracy."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import livedata
from ..db import get_db
from ..schemas import AccuracyOut, FixtureOut

router = APIRouter(tags=["live"])


@router.get("/fixtures", response_model=list[FixtureOut])
def fixtures(db: Session = Depends(get_db)):
    """Upcoming World Cup fixtures with model probabilities.

    Empty list when no data provider is configured — the frontend hides the
    section in that case.
    """
    return livedata.get_fixtures(db)


@router.get("/accuracy", response_model=AccuracyOut)
def accuracy(db: Session = Depends(get_db)):
    """How often the model's most-likely outcome matched auto-ingested results."""
    return livedata.get_accuracy(db)
