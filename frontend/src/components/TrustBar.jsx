// Credibility strip under the wordmark: reframes the raw model stats as
// benefit-first trust signals for first-time (shared-link) visitors.
export default function TrustBar({ model, teamsCount, live }) {
  const badges = [];

  if (live) {
    badges.push({ key: "live", cls: "live", label: "Live", dot: true });
  }
  if (model) {
    badges.push({ key: "acc", cls: "good", label: `${Math.round(model.accuracy * 100)}% accurate` });
  }
  if (model?.n_samples) {
    badges.push({ key: "matches", label: `${model.n_samples.toLocaleString()} matches` });
  }
  if (teamsCount) {
    badges.push({ key: "teams", label: `${teamsCount} teams` });
  }

  if (!badges.length) return null;
  return (
    <div className="trustbar">
      {badges.map((b) => (
        <span key={b.key} className={`trust-pill ${b.cls || ""}`}>
          {b.dot && <span className="live-dot" />}
          {b.label}
        </span>
      ))}
    </div>
  );
}
