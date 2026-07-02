"""API tests against an isolated temp database (real DB untouched)."""
import random
import types
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import predictor
from app.db import Base, get_db
from app.features import replay
from app.main import app
from app.models import Match, Team

TEAMS = ["Ruritania", "Genovia", "Wakanda", "Latveria",
         "Elbonia", "Qumar", "Zubrowka", "Kolechia"]


def build_matches(n=500, seed=1):
    rng = random.Random(seed)
    strength = {name: i for i, name in enumerate(TEAMS)}  # 0..7
    start = date(2005, 1, 1)
    out = []
    for k in range(n):
        h, a = rng.sample(TEAMS, 2)
        out.append(types.SimpleNamespace(
            date=start + timedelta(days=k), home_team=h, away_team=a,
            home_score=rng.randint(0, 1 + strength[h] // 2),
            away_score=rng.randint(0, 1 + strength[a] // 2),
            tournament="Friendly", neutral=True,
        ))
    return out


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Never let a token exported in the dev/CI shell start a real live-data
    # poller (network + real DB) inside the app lifespan during tests.
    monkeypatch.delenv("WCD_FOOTBALL_API_TOKEN", raising=False)
    engine = create_engine(
        f"sqlite:///{tmp_path / 't.db'}", connect_args={"check_same_thread": False}
    )
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    teams: dict[str, dict] = {}

    def acc(name):
        return teams.setdefault(
            name, {"elo": 1500.0, "mp": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}
        )

    with TestSession() as s:
        for step in replay(build_matches()):
            m = step.match
            s.add(Match(
                date=m.date, home_team=m.home_team, away_team=m.away_team,
                home_score=m.home_score, away_score=m.away_score,
                tournament=m.tournament, neutral=m.neutral,
                home_elo_before=step.home_elo_before, away_elo_before=step.away_elo_before,
                home_elo_after=step.home_elo_after, away_elo_after=step.away_elo_after,
            ))
            h, a = acc(m.home_team), acc(m.away_team)
            h["mp"] += 1; a["mp"] += 1
            h["gf"] += m.home_score; h["ga"] += m.away_score
            a["gf"] += m.away_score; a["ga"] += m.home_score
            h["elo"], a["elo"] = step.home_elo_after, step.away_elo_after
            if step.label == "H":
                h["w"] += 1; a["l"] += 1
            elif step.label == "A":
                h["l"] += 1; a["w"] += 1
            else:
                h["d"] += 1; a["d"] += 1
        for name, st in teams.items():
            s.add(Team(name=name, elo_rating=st["elo"], matches_played=st["mp"],
                       wins=st["w"], draws=st["d"], losses=st["l"],
                       goals_for=st["gf"], goals_against=st["ga"]))
        s.commit()

    monkeypatch.setattr(predictor, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(predictor, "MODEL_PATH", tmp_path / "model.joblib")
    monkeypatch.setattr(predictor, "METRICS_PATH", tmp_path / "metrics.json")
    predictor._MODEL = None
    with TestSession() as s:
        rows = s.execute(select(Match).order_by(Match.date, Match.id)).scalars().all()
        predictor.train(rows, min_history=3)

    def _get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    predictor._MODEL = None


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_rankings_are_ranked_and_sorted(client):
    r = client.get("/api/rankings?limit=5").json()
    assert [t["rank"] for t in r] == [1, 2, 3, 4, 5]
    elos = [t["elo_rating"] for t in r]
    assert elos == sorted(elos, reverse=True)


def test_team_detail(client):
    teams = client.get("/api/teams").json()
    name = teams[0]["name"]
    d = client.get(f"/api/teams/{name}").json()
    assert d["team"]["name"] == name
    assert len(d["rating_history"]) > 0
    assert "win_pct" in d["team"]


def test_predict_probabilities_sum_to_one(client):
    teams = client.get("/api/teams").json()
    home, away = teams[0]["name"], teams[-1]["name"]
    r = client.post("/api/predict", json={"home": home, "away": away, "neutral": True}).json()
    p = r["probabilities"]
    assert abs(p["home_win"] + p["draw"] + p["away_win"] - 1.0) < 0.02
    assert r["most_likely"] in {"home_win", "draw", "away_win"}


def test_predict_unknown_team_404(client):
    r = client.post("/api/predict", json={"home": "Nowhere", "away": "Genovia"})
    assert r.status_code == 404


def test_add_result_updates_elo_and_probabilities(client):
    teams = client.get("/api/teams").json()
    strong, weak = teams[0]["name"], teams[-1]["name"]
    before = client.post("/api/predict", json={"home": weak, "away": strong, "neutral": True}).json()
    elo_before = client.get(f"/api/teams/{weak}").json()["team"]["elo_rating"]

    res = client.post("/api/matches", json={
        "home_team": weak, "away_team": strong, "home_score": 5, "away_score": 0,
        "tournament": "FIFA World Cup", "neutral": True,
    })
    assert res.status_code == 201
    changes = {c["team"]: c for c in res.json()["changes"]}
    assert changes[weak]["delta"] > 0
    assert changes[strong]["delta"] < 0

    elo_after = client.get(f"/api/teams/{weak}").json()["team"]["elo_rating"]
    assert elo_after > elo_before

    # Instant update: the weaker side's win probability should not drop.
    after = client.post("/api/predict", json={"home": weak, "away": strong, "neutral": True}).json()
    assert after["probabilities"]["home_win"] >= before["probabilities"]["home_win"]


def test_model_info_and_retrain(client):
    info = client.get("/api/model").json()
    assert "accuracy" in info
    retrained = client.post("/api/model/retrain").json()
    assert "accuracy" in retrained
    assert retrained["n_samples"] > 0


def test_tournament_simulate(client):
    r = client.post("/api/tournament/simulate", json={"runs": 200})
    assert r.status_code == 200
    data = r.json()
    assert data["runs"] == 200

    teams = data["teams"]
    assert len(teams) == 48  # 12 groups of 4 in the default 2026 bracket

    for t in teams:
        for k in ("advance_group", "reach_quarterfinal", "reach_semifinal",
                  "reach_final", "win_title"):
            assert 0.0 <= t[k] <= 1.0
        # Each stage is a subset of the previous one.
        assert (t["advance_group"] >= t["reach_quarterfinal"] >= t["reach_semifinal"]
                >= t["reach_final"] >= t["win_title"])

    # Exactly one champion per simulated tournament.
    assert abs(sum(t["win_title"] for t in teams) - 1.0) < 0.02
    # Results are returned sorted by title odds.
    titles = [t["win_title"] for t in teams]
    assert titles == sorted(titles, reverse=True)
