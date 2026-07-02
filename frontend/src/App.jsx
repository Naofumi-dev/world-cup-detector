import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import Predictor from "./components/Predictor.jsx";
import Rankings from "./components/Rankings.jsx";
import RecentMatches from "./components/RecentMatches.jsx";
import AddResult from "./components/AddResult.jsx";
import ModelStatus from "./components/ModelStatus.jsx";
import TeamDetail from "./components/TeamDetail.jsx";
import StatBand from "./components/StatBand.jsx";
import TournamentSimulator from "./components/TournamentSimulator.jsx";
import Toasts from "./components/Toasts.jsx";

export default function App() {
  const [teams, setTeams] = useState([]);
  const [rankings, setRankings] = useState([]);
  const [matches, setMatches] = useState([]);
  const [model, setModel] = useState(null);

  const [prediction, setPrediction] = useState(null);
  const [lastFixture, setLastFixture] = useState(null);
  const [predicting, setPredicting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [lastChanges, setLastChanges] = useState(null);
  const [retraining, setRetraining] = useState(false);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [toasts, setToasts] = useState([]);

  const loaded = teams.length > 0;

  // Teams enriched with Elo + rank, ranked teams first (used by the comboboxes).
  const teamIndex = useMemo(() => {
    const rankMap = Object.fromEntries(rankings.map((r) => [r.name, r.rank]));
    return teams
      .map((t) => ({ name: t.name, elo: t.elo_rating, rank: rankMap[t.name] || null }))
      .sort((a, b) => {
        if (a.rank && b.rank) return a.rank - b.rank;
        if (a.rank) return -1;
        if (b.rank) return 1;
        return a.name.localeCompare(b.name);
      });
  }, [teams, rankings]);

  const eloMap = useMemo(
    () => Object.fromEntries(teams.map((t) => [t.name, Math.round(t.elo_rating)])),
    [teams]
  );

  const pushToast = useCallback((msg, kind = "ok") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);

  const loadCore = useCallback(async () => {
    const [tm, rk, mt, md] = await Promise.all([
      api.teams(),
      api.rankings(20),
      api.matches(12),
      api.model().catch(() => null),
    ]);
    setTeams(tm);
    setRankings(rk);
    setMatches(mt);
    setModel(md);
  }, []);

  useEffect(() => {
    loadCore().catch((e) => setError(e.message));
  }, [loadCore]);

  const runPredict = useCallback(async (fixture) => {
    setPredicting(true);
    setError(null);
    try {
      const r = await api.predict(fixture);
      setPrediction(r);
      setLastFixture(fixture);
    } catch (e) {
      setError(e.message);
    } finally {
      setPredicting(false);
    }
  }, []);

  const submitResult = async (payload) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.addResult(payload);
      setLastChanges(res.changes);
      const [tm, rk, mt] = await Promise.all([api.teams(), api.rankings(20), api.matches(12)]);
      setTeams(tm);
      setRankings(rk);
      setMatches(mt);
      if (lastFixture) setPrediction(await api.predict(lastFixture));
      pushToast(`${payload.home_team} ${payload.home_score}–${payload.away_score} ${payload.away_team} recorded · ratings updated`);
    } catch (e) {
      setError(e.message);
      pushToast(e.message, "info");
    } finally {
      setSubmitting(false);
    }
  };

  const retrain = async () => {
    setRetraining(true);
    setError(null);
    try {
      const m = await api.retrain();
      setModel(m);
      if (lastFixture) setPrediction(await api.predict(lastFixture));
      pushToast(`Model retrained · ${Math.round(m.accuracy * 100)}% accuracy on ${m.n_samples.toLocaleString()} matches`);
    } catch (e) {
      setError(e.message);
      pushToast(e.message, "info");
    } finally {
      setRetraining(false);
    }
  };

  const openDetail = async (name) => {
    setError(null);
    try {
      setDetail(await api.team(name));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <>
      <div className="grain" />
      <Toasts toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />

      <div className="shell">
        <header className="masthead">
          <div className="wordmark">
            <div className="crest">W</div>
            <div>
              <h1>World <b>Cup</b> Detector</h1>
              <div className="sub">Live match-outcome intelligence · 2026</div>
            </div>
          </div>
          {model && (
            <div className="model-strip">
              <div className="stat-mini">
                <span className="k">Accuracy</span>
                <span className="v good">{Math.round(model.accuracy * 100)}%</span>
              </div>
              <div className="stat-mini">
                <span className="k">Log loss</span>
                <span className="v">{model.log_loss}</span>
              </div>
              <div className="stat-mini">
                <span className="k">Matches</span>
                <span className="v">{model.n_samples.toLocaleString()}</span>
              </div>
            </div>
          )}
        </header>

        <StatBand
          teamsCount={teams.length}
          matchesCount={model?.n_samples}
          topTeam={rankings[0]}
          model={model}
        />

        {error && <div className="banner">{error}</div>}

        {!loaded ? (
          <div className="content">
            <div className="card" style={{ padding: 22 }}>
              <div className="skel" style={{ height: 24, width: 200, marginBottom: 18 }} />
              <div className="skel" style={{ height: 58 }} />
            </div>
            <div className="grid">
              <div className="card" style={{ padding: 18 }}>
                {Array.from({ length: 6 }).map((_, i) => <div className="skel skel-row" key={i} />)}
              </div>
              <div className="card" style={{ padding: 18 }}>
                {Array.from({ length: 4 }).map((_, i) => <div className="skel skel-row" key={i} />)}
              </div>
            </div>
          </div>
        ) : (
          <div className="content">
            <Predictor
              teams={teamIndex}
              eloMap={eloMap}
              prediction={prediction}
              loading={predicting}
              onPredict={runPredict}
            />

            <div className="grid">
              <div className="col">
                <Rankings teams={rankings} onSelect={openDetail} />
              </div>
              <div className="col">
                <AddResult
                  teams={teamIndex}
                  onSubmit={submitResult}
                  submitting={submitting}
                  lastChanges={lastChanges}
                />
                <ModelStatus model={model} onRetrain={retrain} retraining={retraining} />
                <RecentMatches matches={matches} onSelect={openDetail} />
              </div>
            </div>

            <TournamentSimulator onSelect={openDetail} />
          </div>
        )}

        <footer className="footer">
          <p className="foot-note">
            Predictions are the output of a statistical model, for entertainment
            and educational purposes only — not betting advice.
          </p>
          <nav className="foot-links">
            {import.meta.env.VITE_KOFI_URL && (
              <a
                className="btn btn-ghost btn-sm"
                href={import.meta.env.VITE_KOFI_URL}
                target="_blank"
                rel="noopener noreferrer"
              >
                ☕ Support this project
              </a>
            )}
            <a href="/privacy.html">Privacy</a>
            <a
              href="https://github.com/Naofumi-dev/world-cup-detector"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
          </nav>
        </footer>
      </div>

      {detail && (
        <TeamDetail
          detail={detail}
          rank={rankings.find((r) => r.name === detail.team.name)?.rank}
          onClose={() => setDetail(null)}
        />
      )}
    </>
  );
}
