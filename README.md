# ⚽ World Cup Detector

A match-outcome prediction dashboard for international football. It predicts
**Win / Draw / Loss** probabilities for any fixture, tracks every team's
**Elo rating and form**, and **updates probabilities the instant a new result
is recorded** — built around the live 2026 FIFA World Cup.

- **Backend:** Python · FastAPI · scikit-learn · SQLite
- **Frontend:** React · Vite (hand-crafted CSS, custom SVG charts)
- **Data:** ~49,000 international matches, 1872 → 2026

The dashboard is fully interactive and responsive: a type-to-search team
picker, auto-updating predictions, a swap-teams button, featured matchups, a
head-to-head form guide, a live stats band, toast notifications, loading
skeletons, and a team-detail drawer with an Elo trajectory chart.

---

## How it works

```
results.csv ──► Elo replay ──► SQLite (teams + matches)
                    │                     │
                    ▼                     ▼
            point-in-time          current ratings
              features        ┌──────────┴───────────┐
                    │          ▼                      ▼
                    ▼     POST /predict ──► logistic model ──► W/D/L probs
        scikit-learn model         ▲                            
         (logistic regression)     │
                    ▲              POST /matches  (instant Elo update)
                    └──────── POST /model/retrain
```

1. **Elo engine** (`backend/app/ratings.py`) — a World-Football-style Elo
   system with tournament-importance weighting, margin-of-victory scaling, and
   home advantage. Every match updates both teams in O(1).
2. **Point-in-time features** (`backend/app/features.py`) — for each fixture:
   Elo difference, home advantage, recent form, recent goal difference, and
   tournament importance. Computed from each team's state *before* the match,
   so training has no lookahead leakage.
3. **Model** (`backend/app/predictor.py`) — a scaled multinomial
   **logistic regression** predicting home win / draw / away win. Because the
   features (especially Elo difference) are roughly linear in the outcome
   log-odds, this matches gradient boosting on accuracy while training in ~1.5s.
4. **Live updates** — recording a result instantly shifts both teams' Elo, so
   any subsequent prediction reflects it immediately. The classifier itself is
   retrained **on demand** via a button.

### Model performance (chronological holdout)

| Metric | Model | Baseline (majority class) |
| --- | --- | --- |
| Accuracy | **~60.7%** | 47.9% |
| Log loss | **~0.862** | 1.05 |

Trained on ~48k matches (those with enough prior history for stable features).

---

## Quickstart

Two processes: the API (port 8137) and the dev frontend (port 5173).

### 1. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --port 8137
```

On first start the app **auto-seeds** the database from `data/results.csv` and
**auto-trains** the model (a few seconds). API docs live at
`http://127.0.0.1:8137/docs`.

> To re-seed from scratch at any time: `.venv/bin/python -m app.ingest`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend, so no CORS
setup is needed in development.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET`  | `/api/teams` | All teams (+ Elo, stats); `?search=` filter |
| `GET`  | `/api/rankings?limit=20` | Elo leaderboard |
| `GET`  | `/api/teams/{name}` | Team detail: stats, recent matches, Elo history |
| `GET`  | `/api/matches?limit=12` | Recent results feed |
| `POST` | `/api/matches` | Record a result → **instant Elo update** + deltas |
| `POST` | `/api/predict` | `{home, away, neutral}` → W/D/L probabilities |
| `GET`  | `/api/model` | Current model metrics |
| `POST` | `/api/model/retrain` | Retrain the classifier on all matches |

Example:

```bash
curl -X POST http://127.0.0.1:8137/api/predict \
  -H 'Content-Type: application/json' \
  -d '{"home":"Brazil","away":"Argentina","neutral":true}'
```

---

## Tests

```bash
cd backend
.venv/bin/python -m pytest
```

Covers the Elo math, point-in-time feature correctness (no leakage), model
train/persist/predict, and every API endpoint (against an isolated temp DB).

---

## Project structure

```
backend/
  app/
    ratings.py     Elo engine
    features.py    point-in-time feature builder + replay
    predictor.py   train / persist / predict
    ingest.py      CSV → SQLite seeder
    service.py     DB ↔ rating/feature glue
    models.py      SQLAlchemy ORM (Team, Match)
    schemas.py     Pydantic request/response models
    routers/       teams, matches, predict, model
    main.py        FastAPI app (auto-seed + auto-train on startup)
  data/results.csv seed dataset
  tests/           pytest suite
frontend/
  src/
    App.jsx        dashboard orchestration + data flow
    api.js         fetch client
    index.css      design system ("stadium broadcast terminal")
    components/    Predictor, TeamCombobox, ProbabilityBar, Rankings,
                   RecentMatches, AddResult, ModelStatus, TeamDetail,
                   StatBand, Toasts
```

---

## Data

International results dataset (`home/away teams, scores, tournament, venue`),
1872–present, from the public
[martj42/international_results](https://github.com/martj42/international_results)
project. Unplayed fixtures (blank scores) are skipped on ingest.

## Notes & possible extensions

- Recorded results apply to each team's *current* rating (treated as the latest
  match), which suits live in-tournament use.
- Out of scope today: live API ingestion, authentication, exact-scoreline
  (Poisson) predictions, and deployment — all natural next steps.
