// Slide-over drawer: team stats, recent form, and a custom SVG Elo trend.
import { useEffect } from "react";

function Trend({ history }) {
  if (!history || history.length < 2) return <p className="empty">Not enough history to chart.</p>;
  const W = 420;
  const H = 130;
  const pad = 6;
  const elos = history.map((h) => h.elo);
  const min = Math.min(...elos);
  const max = Math.max(...elos);
  const span = max - min || 1;
  const pts = history.map((h, i) => [
    pad + (i / (history.length - 1)) * (W - 2 * pad),
    pad + (1 - (h.elo - min) / span) * (H - 2 * pad),
  ]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)} ${H - pad} L${pts[0][0].toFixed(1)} ${H - pad} Z`;

  return (
    <div className="trend">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="trendfill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--grass)" stopOpacity="0.32" />
            <stop offset="100%" stopColor="var(--grass)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#trendfill)" />
        <path d={line} fill="none" stroke="var(--grass)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}

function formChips(recentMatches, teamName) {
  // recent_matches is newest-first → reverse for left-to-right oldest→newest, last 8.
  return [...recentMatches]
    .reverse()
    .slice(-8)
    .map((m, i) => {
      const gd = m.home_team === teamName ? m.home_score - m.away_score : m.away_score - m.home_score;
      const r = gd > 0 ? "W" : gd === 0 ? "D" : "L";
      return (
        <span className={`chip ${r}`} key={m.id ?? i}>
          {r}
        </span>
      );
    });
}

export default function TeamDetail({ detail, rank, onClose }) {
  const t = detail.team;

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  const peak = detail.rating_history.length
    ? Math.round(Math.max(...detail.rating_history.map((h) => h.elo)))
    : Math.round(t.elo_rating);

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="drawer">
        <button className="close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3>{t.name}</h3>
        <div className="rank-badge">
          {rank ? `#${rank} by Elo` : "Unranked"} · {Math.round(t.elo_rating)} now · peak {peak}
        </div>

        <div className="detail-stats">
          <div className="s"><div className="k">Played</div><div className="v">{t.matches_played}</div></div>
          <div className="s"><div className="k">Win %</div><div className="v">{Math.round(t.win_pct * 100)}</div></div>
          <div className="s"><div className="k">Goal Diff</div><div className="v">{t.goals_for - t.goals_against >= 0 ? "+" : ""}{t.goals_for - t.goals_against}</div></div>
          <div className="s"><div className="k">Wins</div><div className="v">{t.wins}</div></div>
          <div className="s"><div className="k">Draws</div><div className="v">{t.draws}</div></div>
          <div className="s"><div className="k">Losses</div><div className="v">{t.losses}</div></div>
        </div>

        <div className="eyebrow">Recent form</div>
        <div className="form-chips">{formChips(detail.recent_matches, t.name)}</div>

        <div className="eyebrow">Elo trajectory</div>
        <Trend history={detail.rating_history} />
      </aside>
    </>
  );
}
