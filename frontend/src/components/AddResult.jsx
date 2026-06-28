import { useEffect, useState } from "react";
import TeamCombobox from "./TeamCombobox.jsx";

// Record a played match. On submit the backend updates both teams' Elo
// instantly; we surface the rating deltas as confirmation.
export default function AddResult({ teams, onSubmit, submitting, lastChanges }) {
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  const [hs, setHs] = useState("");
  const [as_, setAs] = useState("");
  const [neutral, setNeutral] = useState(true);
  const [tournament, setTournament] = useState("FIFA World Cup");

  useEffect(() => {
    if (!teams.length) return;
    setHome((h) => h || teams[0].name);
    setAway((a) => a || (teams[1] || teams[0]).name);
  }, [teams]);

  const sameTeam = home === away;
  const onlyDigits = (v) => v.replace(/\D/g, "").slice(0, 2);

  const submit = (e) => {
    e.preventDefault();
    if (sameTeam) return;
    onSubmit({
      home_team: home,
      away_team: away,
      home_score: Number(hs || 0),
      away_score: Number(as_ || 0),
      neutral,
      tournament: tournament.trim() || "Friendly",
    });
  };

  return (
    <section className="card flow d4">
      <div className="card-head">
        <h2>Add Result</h2>
        <span className="tag">Updates ratings live</span>
      </div>
      <div className="card-body">
        <form onSubmit={submit}>
          <div className="form-grid">
            <div className="field">
              <label>Home</label>
              <TeamCombobox teams={teams} value={home} onChange={setHome} accent="home" />
            </div>
            <div className="field">
              <label>Score</label>
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  className="score-input"
                  inputMode="numeric"
                  value={hs}
                  onChange={(e) => setHs(onlyDigits(e.target.value))}
                  placeholder="0"
                />
                <input
                  className="score-input"
                  inputMode="numeric"
                  value={as_}
                  onChange={(e) => setAs(onlyDigits(e.target.value))}
                  placeholder="0"
                />
              </div>
            </div>
            <div className="field">
              <label>Away</label>
              <TeamCombobox teams={teams} value={away} onChange={setAway} accent="away" />
            </div>
          </div>

          <div className="form-row2">
            <label className="toggle">
              <input type="checkbox" checked={neutral} onChange={(e) => setNeutral(e.target.checked)} />
              <span className="track" />
              <span className="label">Neutral venue</span>
            </label>
            <input
              className="input"
              style={{ maxWidth: 190 }}
              value={tournament}
              onChange={(e) => setTournament(e.target.value)}
              placeholder="Tournament"
            />
            <button className="btn btn-ghost" disabled={submitting || sameTeam}>
              {submitting ? "Saving…" : "Record result"}
            </button>
          </div>
        </form>

        {lastChanges && (
          <div className="delta-toast">
            {lastChanges.map((c) => (
              <div className="row" key={c.team}>
                <span className="name">{c.team}</span>
                <span className={`d ${c.delta >= 0 ? "up" : "down"}`}>
                  {c.delta >= 0 ? "▲" : "▼"} {c.elo_before} → {c.elo_after} ({c.delta >= 0 ? "+" : ""}
                  {c.delta})
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
