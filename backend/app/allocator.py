"""Multiplicative-weights (Hedge) strategy allocator (Blueprint v2 §4.3).

The engine now runs multiple strategy FAMILIES (trend-continuation and range-fade; more later). The
Hedge algorithm keeps a weight per family proportional to exp(eta * decayed realized R) and allocates
capital proportionally. This has a provable regret bound: over time it performs nearly as well as the
single best family in hindsight for whatever market occurred — the honest version of "adapts to any
market". A per-family FLOOR keeps every family alive at a small allocation so it can be re-detected
when its regime returns.

A trade's family is inferred from its regime: range regimes are fades (the range-fade geometry only
fires in a range), everything else is trend-continuation — so no schema change is needed.
"""

from __future__ import annotations

import math
import time

from . import db
from .config import settings

FAMILIES = ("trend", "range-fade")
_TTL = 120.0
_cache: tuple[float, dict] | None = None


def _family_stats(window_days: int) -> dict[str, dict]:
    """Per-family decayed mean realized R over the window: {family: {n, r_mean_decayed}}."""
    out = {f: {"n": 0, "r_mean_decayed": 0.0} for f in FAMILIES}
    if not db.enabled():
        return out
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select case when coalesce(s.regime,'') = 'range' then 'range-fade' else 'trend' end fam,
                       o.pnl, s.entry, s.stop,
                       extract(epoch from (now() - o.resolved_at)) / 86400.0 as age
                from outcomes o join signals s on s.id = o.signal_id
                where o.pnl is not null and s.entry is not null and s.stop is not null
                  and s.entry <> 0 and s.stop <> s.entry and s.shadow = false
                  and o.resolved_at > now() - interval '{int(window_days)} days'
                """
            )
            rows = cur.fetchall()
    except Exception:
        return out

    lam = math.log(2.0) / max(1.0, settings.allocator_halflife_days)
    agg: dict[str, list[float]] = {f: [0.0, 0.0] for f in FAMILIES}  # [sum w*R, sum w], count sep
    counts = {f: 0 for f in FAMILIES}
    for fam, pnl, entry, stop, age in rows:
        risk = abs(float(entry) - float(stop)) / abs(float(entry))
        if risk <= 1e-9:
            continue
        r = float(pnl) / risk
        w = math.exp(-lam * max(0.0, float(age)))
        agg[fam][0] += w * r
        agg[fam][1] += w
        counts[fam] += 1
    for f in FAMILIES:
        sw = agg[f][1]
        out[f] = {"n": counts[f], "r_mean_decayed": (agg[f][0] / sw) if sw > 1e-9 else 0.0}
    return out


def weights() -> dict[str, float]:
    """Hedge weights per family (sum to 1), with a floor so no family is starved to zero."""
    stats = _family_stats(settings.allocator_window_days)
    eta = settings.allocator_eta
    floor = settings.allocator_floor
    # Thin families get a neutral score (0) so they don't tilt on noise.
    scores = {f: (stats[f]["r_mean_decayed"] if stats[f]["n"] >= settings.allocator_min_trades else 0.0)
              for f in FAMILIES}
    mx = max(scores.values())
    raw = {f: math.exp(eta * (scores[f] - mx)) for f in FAMILIES}
    tot = sum(raw.values()) or 1.0
    w = {f: raw[f] / tot for f in FAMILIES}
    w = {f: max(v, floor) for f, v in w.items()}       # floor
    tot2 = sum(w.values())
    return {f: v / tot2 for f, v in w.items()}


def state() -> dict:
    global _cache
    now = time.time()
    if _cache and now - _cache[0] < _TTL:
        return _cache[1]
    stats = _family_stats(settings.allocator_window_days)
    w = weights()
    st = {"weights": {f: round(v, 4) for f, v in w.items()},
          "stats": {f: {"n": stats[f]["n"], "r_mean": round(stats[f]["r_mean_decayed"], 4)} for f in FAMILIES}}
    _cache = (now, st)
    return st


def family_multiplier(family: str) -> float:
    """Capital multiplier for a family's size: 1.0 at parity, >1 favored, <1 disfavored (clamped)."""
    if not settings.allocator_enabled:
        return 1.0
    w = weights().get(family)
    if w is None:
        return 1.0
    mult = w * len(FAMILIES)                             # equal-weight -> 1.0
    return float(max(settings.allocator_floor * len(FAMILIES), min(settings.allocator_max_mult, mult)))


def refresh() -> None:
    global _cache
    _cache = None
