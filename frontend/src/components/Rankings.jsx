// Elo leaderboard. Each row links to the team detail drawer.
export default function Rankings({ teams, onSelect }) {
  const max = teams.length ? teams[0].elo_rating : 1;
  const floor = 1400;

  return (
    <section className="card d2">
      <div className="card-head">
        <h2>Elo Rankings</h2>
        <span className="tag">Top {teams.length}</span>
      </div>
      <div className="card-body">
        <div className="rank-list">
          {teams.map((t) => {
            const w = Math.max(6, ((t.elo_rating - floor) / (max - floor || 1)) * 100);
            return (
              <div className="rank-row" key={t.name} onClick={() => onSelect(t.name)}>
                <span className="pos">{t.rank}</span>
                <div>
                  <div className="name">{t.name}</div>
                  <div className="meta">
                    {t.matches_played} GP · {Math.round(t.win_pct * 100)}% win
                  </div>
                  <div className="elobar" style={{ width: `${w}%` }} />
                </div>
                <span className="elo">{Math.round(t.elo_rating)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
