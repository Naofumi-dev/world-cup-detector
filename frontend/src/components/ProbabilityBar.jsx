// Animated stacked Win / Draw / Loss bar. Segment widths transition via CSS
// whenever the prediction changes, so probability shifts are visible.
const pct = (x) => Math.round(x * 100);

export default function ProbabilityBar({ prediction }) {
  const { probabilities: p, home, away, most_likely } = prediction;
  const segs = [
    { key: "home", cls: "home", val: p.home_win, label: home },
    { key: "draw", cls: "draw", val: p.draw, label: "Draw" },
    { key: "away", cls: "away", val: p.away_win, label: away },
  ];
  const topLabel =
    most_likely === "home_win" ? `${home} win` : most_likely === "away_win" ? `${away} win` : "Draw";
  const topPct = pct(Math.max(p.home_win, p.draw, p.away_win));

  return (
    <div className="verdict">
      <div className="headline">
        Most likely&nbsp;·&nbsp;{topLabel} <span className="pct">{topPct}%</span>
      </div>
      <div className="prob-bar">
        {segs.map((s) => (
          <div key={s.key} className={`prob-seg ${s.cls}`} style={{ "--w": `${s.val * 100}%` }}>
            {s.val > 0.07 && (
              <>
                <span className="p">{pct(s.val)}%</span>
                <span className="l">{s.label}</span>
              </>
            )}
          </div>
        ))}
      </div>
      <div className="prob-legend">
        <span className="item"><span className="dot home" />{home} · {pct(p.home_win)}%</span>
        <span className="item"><span className="dot draw" />Draw · {pct(p.draw)}%</span>
        <span className="item"><span className="dot away" />{away} · {pct(p.away_win)}%</span>
      </div>
    </div>
  );
}
