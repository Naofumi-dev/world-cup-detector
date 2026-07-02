// Thin fetch wrapper around the FastAPI backend.
// In dev, VITE_API_URL is unset and requests hit /api (Vite proxies to the
// backend). In production, set VITE_API_URL to the backend's public URL.
const API_BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options) {
  const res = await fetch(`${API_BASE}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  teams: () => request("/teams"),
  rankings: (limit = 20) => request(`/rankings?limit=${limit}`),
  team: (name) => request(`/teams/${encodeURIComponent(name)}`),
  matches: (limit = 12) => request(`/matches?limit=${limit}`),
  predict: (body) => request("/predict", { method: "POST", body: JSON.stringify(body) }),
  addResult: (body) =>
    request("/matches", { method: "POST", body: JSON.stringify(body) }),
  model: () => request("/model"),
  retrain: () => request("/model/retrain", { method: "POST" }),
  simulate: (runs) =>
    request("/tournament/simulate", {
      method: "POST",
      body: JSON.stringify(runs ? { runs } : {}),
    }),
  fixtures: () => request("/fixtures"),
  accuracy: () => request("/accuracy"),
};
