"""Live-data tests: provider fully mocked, no network."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import livedata
from app.db import get_db
from app.main import app
from app.models import Match, PredictionLog

from .test_api import client  # noqa: F401  (shared fixture: seeded temp DB + model)


def _session():
    """A session bound to the test DB via the app's dependency override."""
    return next(app.dependency_overrides[get_db]())


def _fd_match(home, away, utc, status="FINISHED", hs=None, as_=None):
    return {
        "utcDate": utc,
        "status": status,
        "stage": "GROUP_STAGE",
        "homeTeam": {"name": home},
        "awayTeam": {"name": away},
        "score": {"fullTime": {"home": hs, "away": as_}},
    }


def test_alias_mapping():
    assert livedata.normalize_team({"name": "Korea Republic"}) == "South Korea"
    assert livedata.normalize_team({"name": "USA"}) == "United States"
    assert livedata.normalize_team({"name": "Côte d'Ivoire"}) == "Ivory Coast"
    assert livedata.normalize_team({"name": "Brazil"}) == "Brazil"
    assert livedata.normalize_team("Czechia") == "Czech Republic"


def test_ingest_records_result_and_prediction(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WCD_FOOTBALL_API_TOKEN", "test-token")
    payload = {
        "matches": [
            _fd_match("Ruritania", "Genovia", "2026-07-01T18:00:00Z", hs=2, as_=1),
            # Unknown team -> skipped, never crashes.
            _fd_match("Atlantis", "Genovia", "2026-07-01T21:00:00Z", hs=1, as_=0),
        ]
    }
    monkeypatch.setattr(livedata, "_get", lambda path, params=None: payload)

    with _session() as s:
        before = len(s.execute(select(Match)).scalars().all())
        summary = livedata.ingest_results(s)
        assert summary["ingested"] == 1
        assert summary["skipped"] == 1

        after = s.execute(select(Match)).scalars().all()
        assert len(after) == before + 1
        newest = max(after, key=lambda m: m.id)
        assert (newest.home_team, newest.away_team) == ("Ruritania", "Genovia")
        assert newest.tournament == "FIFA World Cup"

        logs = s.execute(select(PredictionLog)).scalars().all()
        assert len(logs) == 1
        lg = logs[0]
        assert abs(lg.p_home + lg.p_draw + lg.p_away - 1.0) < 0.02
        assert lg.actual == "home_win"
        assert lg.correct == (lg.predicted == "home_win")

        # Re-running with the same payload must not double-ingest.
        again = livedata.ingest_results(s)
        assert again["ingested"] == 0


def test_shootout_recorded_as_draw():
    # Provider reconstructs from regular/extra time when present.
    m = {"score": {"duration": "PENALTY_SHOOTOUT",
                   "fullTime": {"home": 5, "away": 3},
                   "regularTime": {"home": 1, "away": 1},
                   "extraTime": {"home": 0, "away": 0},
                   "penalties": {"home": 4, "away": 2}}}
    assert livedata._extract_score(m) == (1, 1)
    # No breakdown, but fullTime includes pens: subtract them.
    m2 = {"score": {"duration": "PENALTY_SHOOTOUT",
                    "fullTime": {"home": 5, "away": 3},
                    "penalties": {"home": 4, "away": 2}}}
    assert livedata._extract_score(m2) == (1, 1)
    # Regular-time match passes through untouched.
    m3 = {"score": {"duration": "REGULAR", "fullTime": {"home": 2, "away": 0}}}
    assert livedata._extract_score(m3) == (2, 0)


def test_ingest_dedup_reversed_orientation(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WCD_FOOTBALL_API_TOKEN", "test-token")
    with _session() as s:
        existing = s.execute(select(Match).order_by(Match.id.desc())).scalars().first()
        # Provider lists the same match with home/away swapped.
        payload = {"matches": [_fd_match(existing.away_team, existing.home_team,
                                         existing.date.isoformat() + "T18:00:00Z",
                                         hs=0, as_=2)]}
        monkeypatch.setattr(livedata, "_get", lambda path, params=None: payload)
        summary = livedata.ingest_results(s)
        assert summary["ingested"] == 0


def test_ingest_dedup_tolerates_date_offset(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WCD_FOOTBALL_API_TOKEN", "test-token")
    with _session() as s:
        existing = s.execute(select(Match).order_by(Match.id.desc())).scalars().first()
        # Provider reports the same pairing one day later (timezone skew).
        skewed = (existing.date + timedelta(days=1)).isoformat() + "T02:00:00Z"
        payload = {"matches": [_fd_match(existing.home_team, existing.away_team,
                                         skewed, hs=1, as_=1)]}
        monkeypatch.setattr(livedata, "_get", lambda path, params=None: payload)
        summary = livedata.ingest_results(s)
        assert summary["ingested"] == 0
        assert summary["skipped"] == 1


def test_fixtures_endpoint(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WCD_FOOTBALL_API_TOKEN", "test-token")
    livedata._fixtures_cache = None
    soon = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT18:00:00Z")
    payload = {
        "matches": [
            _fd_match("Ruritania", "Wakanda", soon, status="TIMED"),
            _fd_match("Latveria", "Elbonia", soon, status="SCHEDULED"),
            # Already played -> excluded.
            _fd_match("Genovia", "Qumar", "2026-06-20T18:00:00Z", hs=1, as_=0),
        ]
    }
    monkeypatch.setattr(livedata, "_get", lambda path, params=None: payload)

    r = client.get("/api/fixtures")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for fx in data:
        p = fx["probabilities"]
        assert abs(p["home_win"] + p["draw"] + p["away_win"] - 1.0) < 0.02
        assert fx["most_likely"] in {"home_win", "draw", "away_win"}
    livedata._fixtures_cache = None


def test_fixtures_degrade_on_malformed_payload(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WCD_FOOTBALL_API_TOKEN", "test-token")
    livedata._fixtures_cache = None
    bad = {"matches": [{"utcDate": "not-a-date", "status": "TIMED",
                        "homeTeam": {"name": "Ruritania"}, "awayTeam": {"name": "Genovia"},
                        "score": {"fullTime": {"home": None, "away": None}}}]}
    monkeypatch.setattr(livedata, "_get", lambda path, params=None: bad)
    r = client.get("/api/fixtures")
    assert r.status_code == 200
    assert r.json() == []
    livedata._fixtures_cache = None


def test_fixtures_empty_without_token(client, monkeypatch):  # noqa: F811
    monkeypatch.delenv("WCD_FOOTBALL_API_TOKEN", raising=False)
    livedata._fixtures_cache = None
    r = client.get("/api/fixtures")
    assert r.status_code == 200
    assert r.json() == []


def test_accuracy_endpoint(client):  # noqa: F811
    with _session() as s:
        s.add(PredictionLog(date=date(2026, 6, 30), home_team="Ruritania",
                            away_team="Genovia", home_score=2, away_score=0,
                            p_home=0.5, p_draw=0.3, p_away=0.2,
                            predicted="home_win", actual="home_win", correct=True))
        s.add(PredictionLog(date=date(2026, 6, 30), home_team="Wakanda",
                            away_team="Latveria", home_score=0, away_score=1,
                            p_home=0.5, p_draw=0.3, p_away=0.2,
                            predicted="home_win", actual="away_win", correct=False))
        s.commit()

    r = client.get("/api/accuracy")
    assert r.status_code == 200
    body = r.json()
    assert body["n"] >= 2
    assert 0.0 <= body["accuracy"] <= 1.0
