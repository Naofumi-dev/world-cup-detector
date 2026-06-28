"""FastAPI application entrypoint for the World Cup Detector."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import predictor
from .db import SessionLocal
from .ingest import ensure_seeded
from .models import Match
from .routers import matches, model, predict, teams, tournament


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed the database from the CSV on first run, then train a model if none
    # has been persisted yet. Both are no-ops on subsequent starts.
    ensure_seeded()
    if not predictor.MODEL_PATH.exists():
        with SessionLocal() as session:
            rows = session.execute(select(Match).order_by(Match.date, Match.id)).scalars().all()
            predictor.train(rows)
    yield


app = FastAPI(title="World Cup Detector API", version="1.0.0", lifespan=lifespan)

# Allow the local dev frontend plus any production origins supplied via
# WCD_CORS_ORIGINS (comma-separated). WCD_CORS_ORIGIN_REGEX additionally allows
# origins by pattern (e.g. "https://.*\.vercel\.app" to cover Vercel previews).
_allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_allowed_origins += [
    o.strip() for o in os.environ.get("WCD_CORS_ORIGINS", "").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=os.environ.get("WCD_CORS_ORIGIN_REGEX") or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(model.router, prefix="/api")
app.include_router(tournament.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
