function fmtDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// Recent results feed. Team names open the detail drawer; winner is highlighted.
export default function RecentMatches({ matches, onSelect }) {
  return (
    <section className="card d3">
      <div className="card-head">
        <h2>Recent Results</h2>
        <span className="tag">Latest {matches.length}</span>
      </div>
      <div className="card-body">
        {matches.length === 0 ? (
          <p className="empty">No matches recorded yet.</p>
        ) : (
          matches.map((m) => {
            const homeWin = m.home_score > m.away_score;
            const awayWin = m.away_score > m.home_score;
            return (
              <div className="match-row" key={m.id}>
                <span
                  className={`t h ${homeWin ? "win" : ""}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => onSelect(m.home_team)}
                >
                  {m.home_team}
                </span>
                <span className="score">{m.home_score}–{m.away_score}</span>
                <span
                  className={`t a ${awayWin ? "win" : ""}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => onSelect(m.away_team)}
                >
                  {m.away_team}
                </span>
                <span className="when">
                  {fmtDate(m.date)} · {m.tournament}
                  {m.neutral ? " · Neutral" : ""}
                </span>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
