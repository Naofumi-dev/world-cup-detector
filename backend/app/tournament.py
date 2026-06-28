"""Monte-Carlo simulation of a World Cup-style tournament.

Reuses the trained Win/Draw/Loss model (``predictor``) and each team's current
state (``service.team_state``) to estimate how often every nation reaches each
stage. Pairwise neutral-venue probabilities are computed once per run and cached,
then sampled across many simulated tournaments — so 10k tournaments cost ~1k
model calls, not millions.

Bracket: 12 groups of 4 → top 2 per group + 8 best third-placed = 32 → a single
elimination knockout (R32 → R16 → QF → SF → Final). Group/best-third selection
follows the 2026 format; the knockout seeds the 32 qualifiers by Elo (a
simplification of FIFA's fixed cross-group bracket).
"""
from __future__ import annotations

import json
import random
from itertools import combinations
from pathlib import Path

from . import predictor, service
from .features import TeamState, match_features

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_BRACKET = DATA_DIR / "wc2026.json"

_TOURNAMENT = "FIFA World Cup"

# Field size going into a knockout round -> stage code recorded for its losers.
#   1 = last 32 (advanced from group, out in R32)   4 = last 4  (semifinal)
#   2 = last 16                                      5 = last 2  (final)
#   3 = last 8  (quarterfinal)                       6 = champion
_SIZE_TO_STAGE = {32: 1, 16: 2, 8: 3, 4: 4, 2: 5}


def load_bracket(path: Path = DEFAULT_BRACKET) -> dict:
    return json.loads(Path(path).read_text())


def _seed_positions(n: int) -> list[int]:
    """Standard single-elimination seeding order for a power-of-two field.

    Returns the seed index (0 = strongest) for each bracket slot, so the top
    seeds only meet in the later rounds.
    """
    order = [0]
    while len(order) < n:
        m = len(order) * 2
        order = [v for x in order for v in (x, m - 1 - x)]
    return order


def _build_table(model, states, teams: list[str]) -> dict:
    """Precompute symmetric neutral-venue (P(a), P(draw), P(b)) for every pair.

    Both home/away orientations are scored so the arbitrary "home" slot doesn't
    bias a neutral fixture, then averaged and renormalised. All fixtures are
    predicted in a single vectorised batch.
    """
    pairs = list(combinations(teams, 2))
    feats = []
    for a, b in pairs:
        feats.append(match_features(states[a], states[b], neutral=True, tournament=_TOURNAMENT))
        feats.append(match_features(states[b], states[a], neutral=True, tournament=_TOURNAMENT))
    probs = predictor.predict_many(model, feats)

    table = {}
    for i, (a, b) in enumerate(pairs):
        pa, pb = probs[2 * i], probs[2 * i + 1]
        win_a = (pa["home_win"] + pb["away_win"]) / 2
        draw = (pa["draw"] + pb["draw"]) / 2
        win_b = (pa["away_win"] + pb["home_win"]) / 2
        total = win_a + draw + win_b or 1.0
        table[(a, b)] = (win_a / total, draw / total, win_b / total)
    return table


def _match(table: dict, a: str, b: str) -> tuple[float, float, float]:
    """(P(a wins), P(draw), P(b wins)) regardless of stored pair order."""
    if (a, b) in table:
        return table[(a, b)]
    win_b, draw, win_a = table[(b, a)]
    return win_a, draw, win_b


def _group_standings(group, table, states, rng):
    """Round-robin one group; return teams ranked 1st→4th and their points."""
    pts = {t: 0 for t in group}
    for a, b in combinations(group, 2):
        win_a, draw, _ = _match(table, a, b)
        r = rng.random()
        if r < win_a:
            pts[a] += 3
        elif r < win_a + draw:
            pts[a] += 1
            pts[b] += 1
        else:
            pts[b] += 3
    ranked = sorted(group, key=lambda t: (pts[t], states[t].elo, rng.random()), reverse=True)
    return ranked, pts


def _knockout(seeded, table, rng, stage_of):
    """Single elimination over a power-of-two seeded field; records stages."""
    order = _seed_positions(len(seeded))
    field = [seeded[i] for i in order]
    while len(field) > 1:
        size = len(field)
        winners = []
        for i in range(0, size, 2):
            a, b = field[i], field[i + 1]
            win_a, draw, win_b = _match(table, a, b)
            base = win_a + win_b or 1.0
            # No draws in knockouts: split the draw mass by relative strength.
            p_a = win_a + draw * (win_a / base)
            winner, loser = (a, b) if rng.random() < p_a else (b, a)
            stage_of[loser] = _SIZE_TO_STAGE[size]
            winners.append(winner)
        field = winners
    stage_of[field[0]] = 6  # champion


def _simulate_once(groups, table, states, rng) -> dict:
    """One full tournament; return {team: furthest stage code reached}."""
    stage_of = {}
    winners, seconds, thirds = [], [], []
    for gteams in groups.values():
        ranked, pts = _group_standings(gteams, table, states, rng)
        winners.append(ranked[0])
        seconds.append(ranked[1])
        thirds.append((ranked[2], pts[ranked[2]]))
        for t in ranked:
            stage_of[t] = 0  # group exit unless they qualify below

    best_thirds = [
        t for t, _ in sorted(
            thirds, key=lambda x: (x[1], states[x[0]].elo, rng.random()), reverse=True
        )[:8]
    ]
    qualifiers = winners + seconds + best_thirds  # 32
    for t in qualifiers:
        stage_of[t] = 1  # at least last 32

    seeded = sorted(qualifiers, key=lambda t: (states[t].elo, rng.random()), reverse=True)
    _knockout(seeded, table, rng, stage_of)
    return stage_of


def simulate(session, runs: int = 3000, bracket: dict | None = None, seed: int | None = None) -> dict:
    """Run ``runs`` tournaments and return per-team stage probabilities.

    Result shape matches ``schemas.TournamentResponse``.
    """
    data = bracket or load_bracket()
    groups = {g["name"]: list(g["teams"]) for g in data["groups"]}
    group_of = {t: gname for gname, ts in groups.items() for t in ts}
    all_teams = list(group_of)

    model = predictor.load_model()
    states, unknown = {}, []
    for t in all_teams:
        st = service.team_state(session, t)
        if st is None:
            unknown.append(t)
            st = TeamState()
        states[t] = st

    table = _build_table(model, states, all_teams)
    counts = {t: [0, 0, 0, 0, 0] for t in all_teams}  # advance, qf, sf, final, title
    rng = random.Random(seed)

    for _ in range(runs):
        for t, s in _simulate_once(groups, table, states, rng).items():
            c = counts[t]
            if s >= 1:
                c[0] += 1
            if s >= 3:
                c[1] += 1
            if s >= 4:
                c[2] += 1
            if s >= 5:
                c[3] += 1
            if s >= 6:
                c[4] += 1

    teams_out = [
        {
            "team": t,
            "group": group_of[t],
            "elo": round(states[t].elo, 1),
            "advance_group": round(counts[t][0] / runs, 4),
            "reach_quarterfinal": round(counts[t][1] / runs, 4),
            "reach_semifinal": round(counts[t][2] / runs, 4),
            "reach_final": round(counts[t][3] / runs, 4),
            "win_title": round(counts[t][4] / runs, 4),
            "known": t not in unknown,
        }
        for t in all_teams
    ]
    teams_out.sort(key=lambda x: x["win_title"], reverse=True)
    return {"runs": runs, "teams": teams_out, "unknown_teams": unknown}
