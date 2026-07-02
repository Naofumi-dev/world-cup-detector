// Upcoming World Cup fixtures with live model probabilities.
// Rendered only when the backend has a live-data provider configured.
const pct = (x) => Math.round(x * 100);

function kickoff(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function favorite(fx) {
  const p = fx.probabilities;
  if (fx.most_likely === "home_win") return `${fx.home} ${pct(p.home_win)}%`;
  if (fx.most_likely === "away_win") return `${fx.away} ${pct(p.away_win)}%`;
  return `Draw ${pct(p.draw)}%`;
}

export default function UpcomingMatches({ fixtures, onSelect }) {
  if (!fixtures?.length) return null;
  return (
    <section className="card d3">
      <div className="card-head">
        <h2>Upcoming Matches</h2>
        <span className="tag">live predictions</span>
      </div>
      <div className="card-body">
        {fixtures.map((fx) => {
          const p = fx.probabilities;
          return (
            <div className="up-row" key={`${fx.utc_date}-${fx.home}`}>
              <div className="up-teams">
                <span className="t" style={{ cursor: "pointer" }} onClick={() => onSelect?.(fx.home)}>
                  {fx.home}
                </span>
                <span className="up-vs">v</span>
                <span className="t" style={{ cursor: "pointer" }} onClick={() => onSelect?.(fx.away)}>
                  {fx.away}
                </span>
              </div>
              <div className="up-bar" aria-hidden="true">
                <span className="h" style={{ width: `${p.home_win * 100}%` }} />
                <span className="d" style={{ width: `${p.draw * 100}%` }} />
                <span className="a" style={{ width: `${p.away_win * 100}%` }} />
              </div>
              <div className="up-meta">
                <span className="when">{kickoff(fx.utc_date)}</span>
                <span className="fav mono">{favorite(fx)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
