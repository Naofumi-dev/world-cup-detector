// World Cup tournament simulator: runs the backend Monte-Carlo sim and shows
// each nation's odds to win the title / reach the final / reach the semis.
import { useState } from "react";
import { api } from "../api.js";
import { drawSimCard, shareCanvas } from "../share.js";

const pct = (x) => (x >= 0.0995 ? Math.round(x * 100) : (x * 100).toFixed(1));

export default function TournamentSimulator({ onSelect }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.simulate());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const maxTitle = data?.teams?.[0]?.win_title || 1;

  return (
    <section className="card sim d1" id="simulator">
      <div className="card-head">
        <h2>World Cup Simulator</h2>
        <span className="tag">Monte-Carlo · 2026</span>
      </div>
      <div className="card-body">
        <div className="sim-controls">
          <p className="muted sim-intro">
            Plays the 2026 World Cup thousands of times using the model’s match
            probabilities to estimate every nation’s odds of going all the way.
          </p>
          <div className="sim-actions">
            <button className="btn btn-primary" onClick={run} disabled={loading}>
              {loading ? (
                <>
                  <span className="spin" />&nbsp; Simulating…
                </>
              ) : data ? (
                "Re-run"
              ) : (
                "Simulate tournament"
              )}
            </button>
            {data && (
              <button
                className="btn btn-ghost"
                onClick={async () => {
                  const canvas = await drawSimCard(data.teams, data.runs);
                  await shareCanvas(
                    canvas,
                    "wcd-2026-title-odds.png",
                    "Who wins the 2026 World Cup? Simulated odds from World Cup Detector"
                  );
                }}
              >
                📤 Share
              </button>
            )}
          </div>
        </div>

        {error && <div className="banner" style={{ marginTop: 14 }}>{error}</div>}

        {!data && !error && (
          <p className="predict-empty">
            Run the simulation to see championship odds for all 48 teams.
          </p>
        )}

        {data && (
          <>
            <div className="sim-meta">
              {data.runs.toLocaleString()} simulations
              {data.unknown_teams?.length
                ? ` · ${data.unknown_teams.length} team(s) not in dataset (default rating)`
                : ""}
            </div>
            <div className="sim-list">
              <div className="sim-row sim-head">
                <span className="sim-pos">#</span>
                <span>Team</span>
                <span className="r">Champion</span>
                <span className="r c-final">Final</span>
                <span className="r c-semi">Semis</span>
              </div>
              {data.teams.map((t, i) => (
                <div
                  className="sim-row"
                  key={t.team}
                  onClick={() => onSelect?.(t.team)}
                  title={`Advance group ${pct(t.advance_group)}% · reach QF ${pct(
                    t.reach_quarterfinal
                  )}%`}
                >
                  <span className="sim-pos">{i + 1}</span>
                  <span className="sim-team">
                    <span className="sim-name">{t.team}</span>
                    <span className="sim-grp">
                      Group {t.group}
                      {t.known ? "" : " · n/a"}
                    </span>
                  </span>
                  <span className="sim-title r">
                    <span
                      className="sim-bar"
                      style={{ width: `${(t.win_title / maxTitle) * 100}%` }}
                    />
                    <b>{pct(t.win_title)}%</b>
                  </span>
                  <span className="sim-num r c-final">{pct(t.reach_final)}%</span>
                  <span className="sim-num r c-semi">{pct(t.reach_semifinal)}%</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
