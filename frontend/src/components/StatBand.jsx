// Compact scoreboard of headline numbers under the masthead.
export default function StatBand({ teamsCount, matchesCount, topTeam, model, liveAccuracy }) {
  // Once the model has called a few live WC matches, that beats the holdout
  // number as the headline stat — it's verifiable and current.
  const live = liveAccuracy && liveAccuracy.n >= 3;
  const tiles = [
    { k: "Teams tracked", v: teamsCount ? teamsCount.toLocaleString() : "—" },
    { k: "Matches analysed", v: matchesCount ? matchesCount.toLocaleString() : "—" },
    {
      k: "World #1",
      v: topTeam ? topTeam.name : "—",
      sub: topTeam ? `${Math.round(topTeam.elo_rating)} Elo` : null,
    },
    live
      ? {
          k: "Live WC accuracy",
          v: `${Math.round(liveAccuracy.accuracy * 100)}%`,
          sub: `${liveAccuracy.correct}/${liveAccuracy.n} matches called`,
          good: true,
        }
      : {
          k: "Model accuracy",
          v: model ? `${Math.round(model.accuracy * 100)}%` : "—",
          sub: model ? `vs ${Math.round(model.baseline_accuracy * 100)}% baseline` : null,
          good: true,
        },
  ];
  return (
    <div className="statband">
      {tiles.map((t) => (
        <div className="stat-tile" key={t.k}>
          <div className="k">{t.k}</div>
          <div className={`v ${t.good ? "good" : ""}`}>{t.v}</div>
          {t.sub && <div className="sub mono">{t.sub}</div>}
        </div>
      ))}
    </div>
  );
}
