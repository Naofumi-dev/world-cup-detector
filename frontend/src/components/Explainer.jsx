// One-line "what is this" + disclaimer, shown to new visitors and dismissible.
import { useState } from "react";

const KEY = "wcd-explainer-dismissed";

export default function Explainer() {
  const [hidden, setHidden] = useState(() => {
    try {
      return localStorage.getItem(KEY) === "1";
    } catch {
      return false;
    }
  });
  if (hidden) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    setHidden(true);
  };

  return (
    <div className="explainer">
      <span className="explainer-text">
        A statistical model — Elo ratings + machine learning over 49,000 real
        internationals. For insight and fun, <b>not betting advice</b>.
      </span>
      <button className="explainer-x" onClick={dismiss} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}
