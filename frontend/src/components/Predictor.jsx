import { useEffect, useMemo, useState } from "react";
import TeamCombobox from "./TeamCombobox.jsx";
import ProbabilityBar from "./ProbabilityBar.jsx";

const FEATURED = [
  ["Brazil", "Argentina"],
  ["France", "England"],
  ["Spain", "Germany"],
  ["Portugal", "Netherlands"],
];

function pick(teams, preferred) {
  const found = teams.find((t) => t.name === preferred);
  return found ? found.name : teams[0]?.name || "";
}

function FormChips({ form }) {
  // form is newest-first; show oldest→newest for natural reading.
  if (!form?.length) return <span className="muted" style={{ fontSize: 12 }}>—</span>;
  return (
    <span className="fg-chips">
      {[...form].reverse().map((r, i) => (
        <span className={`chip sm ${r}`} key={i}>
          {r}
        </span>
      ))}
    </span>
  );
}

function FormGuide({ prediction, rankOf }) {
  const { home, away, home_elo, away_elo, home_recent, away_recent } = prediction;
  const gap = Math.round(home_elo - away_elo);
  return (
    <div className="formguide">
      <div className="fg-side">
        <div className="fg-top">
          {rankOf(home) && <span className="fg-rank">#{rankOf(home)}</span>}
          <span className="fg-name">{home}</span>
        </div>
        <div className="fg-elo mono">{Math.round(home_elo)}</div>
        <FormChips form={home_recent} />
      </div>
      <div className="fg-gap">
        <span className="k">Elo gap</span>
        <span className="v mono">{gap >= 0 ? "+" : ""}{gap}</span>
      </div>
      <div className="fg-side right">
        <div className="fg-top">
          <span className="fg-name">{away}</span>
          {rankOf(away) && <span className="fg-rank">#{rankOf(away)}</span>}
        </div>
        <div className="fg-elo mono">{Math.round(away_elo)}</div>
        <FormChips form={away_recent} />
      </div>
    </div>
  );
}

// Hero card: searchable team pickers, swap, featured matchups, auto-prediction.
export default function Predictor({ teams, eloMap, prediction, loading, onPredict }) {
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  const [neutral, setNeutral] = useState(true);

  const names = useMemo(() => new Set(teams.map((t) => t.name)), [teams]);
  const rankOf = (name) => teams.find((t) => t.name === name)?.rank || null;

  useEffect(() => {
    if (!teams.length) return;
    setHome((h) => h || pick(teams, "Brazil"));
    setAway((a) => a || pick(teams, "Argentina"));
  }, [teams]);

  const sameTeam = home === away;

  // Auto-predict (debounced) whenever the fixture changes — feels live.
  useEffect(() => {
    if (!home || !away || sameTeam) return;
    const id = setTimeout(() => onPredict({ home, away, neutral }), 220);
    return () => clearTimeout(id);
  }, [home, away, neutral, sameTeam, onPredict]);

  const swap = () => {
    setHome(away);
    setAway(home);
  };

  const featured = FEATURED.filter(([a, b]) => names.has(a) && names.has(b));
  const elo = (name) => (eloMap[name] != null ? eloMap[name] : "—");

  return (
    <section className="card predictor flow d1">
      <div className="card-head">
        <h2>Match Predictor</h2>
        <span className="tag">{loading ? <><span className="spin" /> updating</> : "live · auto-updates"}</span>
      </div>
      <div className="card-body">
        <div className="matchup">
          <div className="side home">
            <span className="role">Home</span>
            <TeamCombobox teams={teams} value={home} onChange={setHome} accent="home" />
            <span className="elo">ELO <b>{elo(home)}</b></span>
          </div>

          <button className="swap" onClick={swap} title="Swap home & away" aria-label="Swap teams">
            <span className="swap-icon">⇄</span>
            <span className="swap-vs">VS</span>
          </button>

          <div className="side away">
            <span className="role">Away</span>
            <TeamCombobox teams={teams} value={away} onChange={setAway} accent="away" />
            <span className="elo">ELO <b>{elo(away)}</b></span>
          </div>
        </div>

        <div className="controls">
          <label className="toggle">
            <input type="checkbox" checked={neutral} onChange={(e) => setNeutral(e.target.checked)} />
            <span className="track" />
            <span className="label">Neutral venue {neutral ? "(World Cup)" : "(home advantage)"}</span>
          </label>
          <div className="featured">
            {featured.map(([a, b]) => (
              <button
                key={`${a}-${b}`}
                className="feat-chip"
                onClick={() => {
                  setHome(a);
                  setAway(b);
                }}
              >
                {a} <span className="muted">v</span> {b}
              </button>
            ))}
          </div>
        </div>

        {sameTeam ? (
          <p className="predict-empty">Pick two different teams to see a prediction.</p>
        ) : prediction && prediction.home === home && prediction.away === away ? (
          <>
            <ProbabilityBar prediction={prediction} />
            <FormGuide prediction={prediction} rankOf={rankOf} />
          </>
        ) : (
          <p className="predict-empty">
            <span className="spin" />&nbsp; Calculating live Win / Draw / Loss probabilities…
          </p>
        )}
      </div>
    </section>
  );
}
