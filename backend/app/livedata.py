"""Live World Cup data: auto-ingest finished results + upcoming fixtures.

Pulls the 2026 World Cup schedule from football-data.org (free tier). Finished
matches are recorded through the existing ``service.add_result`` path (instant
Elo update); just before each insert the model's pre-match prediction is logged
to ``prediction_log`` so live accuracy can be reported honestly.

Everything is dormant unless ``WCD_FOOTBALL_API_TOKEN`` is set, and every
public function degrades to a no-op/empty result on provider errors — the rest
of the API must never break because the data provider is down.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import predictor, service
from .features import result_label
from .models import Match, PredictionLog
from .schemas import MatchCreate

log = logging.getLogger("wcd.livedata")

DEFAULT_BASE = "https://api.football-data.org/v4"
COMPETITION = os.environ.get("WCD_FOOTBALL_COMPETITION", "WC")
TOURNAMENT = "FIFA World Cup"

# 2026 host nations get true home advantage; everyone else plays neutral.
HOSTS = {"United States", "Canada", "Mexico"}

# Provider team names -> names used by the historical dataset.
ALIASES = {
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "USA": "United States",
    "IR Iran": "Iran",
    "Iran": "Iran",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
    "China PR": "China",
    "Cabo Verde": "Cape Verde",
    "Congo DR": "DR Congo",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "St. Kitts and Nevis": "Saint Kitts and Nevis",
    "Trinidad & Tobago": "Trinidad and Tobago",
}

_FIXTURES_TTL = 900  # seconds
_FIXTURES_ERROR_TTL = 120  # cache empty results after provider errors too
_fixtures_cache: tuple[float, float, list[dict]] | None = None  # (ts, ttl, data)
_fixtures_lock = threading.Lock()  # single-flight: one provider call at a time
_shutdown = threading.Event()


def _token() -> str:
    return os.environ.get("WCD_FOOTBALL_API_TOKEN", "").strip()


def _base() -> str:
    return os.environ.get("WCD_FOOTBALL_API_BASE", DEFAULT_BASE).rstrip("/")


def _get(path: str, params: dict | None = None) -> dict:
    """GET a provider endpoint. Tests monkeypatch this function."""
    resp = httpx.get(
        f"{_base()}{path}",
        params=params,
        headers={"X-Auth-Token": _token()},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def normalize_team(raw: dict | str) -> str:
    """Map a provider team payload/name to the dataset's team name."""
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("shortName") or ""
    else:
        name = raw
    return ALIASES.get(name, name)


def _parse_date(utc: str) -> datetime:
    return datetime.fromisoformat(utc.replace("Z", "+00:00"))


def _is_duplicate(session: Session, d, home: str, away: str) -> bool:
    """Same pairing (either orientation) within ±2 days counts as recorded.

    Guards against a manually-added result whose date differs from the
    provider's by timezone, or whose home/away sides were entered reversed —
    either would otherwise apply the Elo update twice.
    """
    from sqlalchemy import and_, or_

    lo, hi = d - timedelta(days=2), d + timedelta(days=2)
    row = session.execute(
        select(Match).where(
            or_(
                and_(Match.home_team == home, Match.away_team == away),
                and_(Match.home_team == away, Match.away_team == home),
            ),
            Match.date >= lo,
            Match.date <= hi,
        )
    ).scalars().first()
    return row is not None


def _extract_score(m: dict) -> tuple[int | None, int | None]:
    """Final score by the dataset's convention: goals through extra time,
    shootout excluded (shootout matches are draws in the dataset).

    football-data's ``fullTime`` may or may not include shootout goals
    depending on API version quirks, so for PENALTY_SHOOTOUT matches we
    reconstruct from regular/extra time when available, else subtract the
    shootout, else fall back to a level score.
    """
    score = m.get("score") or {}
    ft = score.get("fullTime") or {}
    h, a = ft.get("home"), ft.get("away")
    if (score.get("duration") or "REGULAR") != "PENALTY_SHOOTOUT":
        return h, a

    reg = score.get("regularTime") or {}
    ext = score.get("extraTime") or {}
    if reg.get("home") is not None:
        return (
            reg["home"] + (ext.get("home") or 0),
            (reg.get("away") or 0) + (ext.get("away") or 0),
        )
    pens = score.get("penalties") or {}
    if h is not None and a is not None and pens.get("home") is not None:
        rh, ra = h - pens["home"], a - pens["away"]
        if rh == ra and rh >= 0:  # subtracting pens must leave a level score
            return rh, ra
    if h is not None and a is not None:
        level = min(h, a)  # went to pens => level after ET
        return level, level
    return None, None


def ingest_results(session: Session) -> dict:
    """Fetch FINISHED WC matches and record any that are new.

    Returns a summary dict; never raises on provider/data problems.
    """
    if not _token():
        return {"ingested": 0, "skipped": 0, "reason": "no token"}
    try:
        payload = _get(f"/competitions/{COMPETITION}/matches", {"status": "FINISHED"})
    except Exception as exc:  # provider down / rate limited / bad token
        log.warning("livedata: fetch failed: %s", exc)
        return {"ingested": 0, "skipped": 0, "reason": str(exc)}

    try:
        model = predictor.load_model()
    except FileNotFoundError:
        model = None

    ingested = skipped = 0
    # Chronological order matters: Elo updates are path-dependent.
    matches = sorted(payload.get("matches", []), key=lambda m: m.get("utcDate", ""))
    for m in matches:
        if _shutdown.is_set():
            break
        # One bad match must never abort the rest of the batch.
        try:
            home = normalize_team(m.get("homeTeam") or {})
            away = normalize_team(m.get("awayTeam") or {})
            hs, as_ = _extract_score(m)
            if not home or not away or hs is None or as_ is None:
                skipped += 1
                continue
            if service.get_team(session, home) is None or service.get_team(session, away) is None:
                log.warning("livedata: unknown team %r or %r — skipping", home, away)
                skipped += 1
                continue

            d = _parse_date(m["utcDate"]).date()
            if _is_duplicate(session, d, home, away):
                skipped += 1
                continue

            neutral = home not in HOSTS
            if model is not None:
                probs = predictor.predict_fixture(
                    model,
                    service.team_state(session, home),
                    service.team_state(session, away),
                    neutral,
                    TOURNAMENT,
                )
                predicted = max(probs, key=probs.get)
                actual = {"H": "home_win", "D": "draw", "A": "away_win"}[result_label(hs, as_)]
                session.add(PredictionLog(
                    date=d, home_team=home, away_team=away,
                    home_score=hs, away_score=as_,
                    p_home=probs["home_win"], p_draw=probs["draw"], p_away=probs["away_win"],
                    predicted=predicted, actual=actual, correct=predicted == actual,
                ))

            service.add_result(session, MatchCreate(
                home_team=home, away_team=away, home_score=hs, away_score=as_,
                tournament=TOURNAMENT, neutral=neutral, date=d,
            ))
            ingested += 1
        except Exception as exc:
            session.rollback()
            skipped += 1
            log.warning("livedata: failed to ingest %s vs %s: %s",
                        m.get("homeTeam"), m.get("awayTeam"), exc)

    if ingested:
        log.info("livedata: ingested %d new result(s), skipped %d", ingested, skipped)
    return {"ingested": ingested, "skipped": skipped}


def get_fixtures(session: Session, limit: int = 10) -> list[dict]:
    """Upcoming WC fixtures with model probabilities (cached ~15 min).

    Single-flight with negative caching: only one thread ever talks to the
    provider, and failures are cached briefly, so a slow/down provider can
    never pile blocking calls onto the shared request threadpool.
    """
    global _fixtures_cache
    if not _token():
        return []

    def _fresh():
        return _fixtures_cache and time.time() - _fixtures_cache[0] < _fixtures_cache[1]

    if _fresh():
        return _fixtures_cache[2]
    with _fixtures_lock:
        if _fresh():  # another thread refreshed while we waited
            return _fixtures_cache[2]
        try:
            payload = _get(f"/competitions/{COMPETITION}/matches")
            model = predictor.load_model()

            cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
            upcoming = sorted(
                (m for m in payload.get("matches", [])
                 if m.get("status") in {"SCHEDULED", "TIMED"}
                 and _parse_date(m["utcDate"]) >= cutoff),
                key=lambda m: m["utcDate"],
            )

            out = []
            for m in upcoming:
                home = normalize_team(m.get("homeTeam") or {})
                away = normalize_team(m.get("awayTeam") or {})
                hs_state = service.team_state(session, home) if home else None
                as_state = service.team_state(session, away) if away else None
                if hs_state is None or as_state is None:
                    continue  # placeholder pairings ("Winner of match 74") or unknown names
                neutral = home not in HOSTS
                probs = predictor.predict_fixture(model, hs_state, as_state, neutral, TOURNAMENT)
                out.append({
                    "utc_date": m["utcDate"],
                    "home": home,
                    "away": away,
                    "stage": m.get("stage"),
                    "probabilities": probs,
                    "most_likely": max(probs, key=probs.get),
                })
                if len(out) >= limit:
                    break
        except Exception as exc:
            # Any provider/data problem degrades to an empty (briefly cached)
            # list — this endpoint must never 500 or hammer the provider.
            log.warning("livedata: fixtures unavailable: %s", exc)
            _fixtures_cache = (time.time(), _FIXTURES_ERROR_TTL, [])
            return []

        _fixtures_cache = (time.time(), _FIXTURES_TTL, out)
        return out


def get_accuracy(session: Session) -> dict:
    """Running live accuracy from the prediction log."""
    rows = session.execute(select(PredictionLog)).scalars().all()
    n = len(rows)
    correct = sum(1 for r in rows if r.correct)
    return {"n": n, "correct": correct, "accuracy": round(correct / n, 4) if n else None}


async def poll_forever(interval_seconds: int = 6 * 3600) -> None:
    """Background loop: ingest new results every few hours (lifespan task).

    ``_shutdown`` lets an in-flight ingest batch stop between matches so the
    worker thread can't hold up process shutdown for a whole batch.
    """
    from .db import SessionLocal

    _shutdown.clear()
    while not _shutdown.is_set():
        try:
            def _run():
                with SessionLocal() as s:
                    return ingest_results(s)
            await asyncio.to_thread(_run)
        except Exception as exc:  # never let the loop die
            log.warning("livedata: poll iteration failed: %s", exc)
        await asyncio.sleep(interval_seconds)
