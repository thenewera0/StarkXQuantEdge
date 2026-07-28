"""Probability calibration (Blueprint v2 §2.6) — turn the raw composite into an honest P(win).

The composite score is NOT a probability. `|composite| >= 60` does not mean "60% chance", and our
own audit found higher conviction was often WORSE. So we fit isotonic regression per regime mapping
|composite| -> P(target before stop) from the real signals x outcomes table. Isotonic enforces a
monotone (non-decreasing) fit; if conviction genuinely doesn't predict wins, it flattens toward the
base rate — which is the honest answer, and exactly what the EV gate then needs.

Pure-numpy Pool-Adjacent-Violators (PAVA) — no scikit-learn dependency. Thin regimes shrink toward
the global curve so a 5-sample regime can't invent a probability.
"""

from __future__ import annotations

import time

import numpy as np

from . import db

_TTL = 300.0
_MIN_REGIME = 30      # need this many resolved outcomes to fit a regime-specific curve
_SHRINK = 25.0        # shrink a regime curve toward global by n/(n+_SHRINK)
_cache: tuple[float, dict] | None = None


def _pava(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Isotonic (non-decreasing) fit via PAVA. Returns (x_knots, fitted) for np.interp lookup.

    x need not be sorted; y in {0,1}. Aggregates duplicate x, then pools adjacent violators.
    """
    order = np.argsort(x, kind="mergesort")
    xs, ys = x[order].astype(float), y[order].astype(float)
    ux, inv = np.unique(xs, return_inverse=True)
    w = np.bincount(inv).astype(float)
    ymean = np.bincount(inv, weights=ys) / np.maximum(w, 1e-9)

    # Stack-based PAVA: each block = [value, weight, right_edge_x].
    stack: list[list[float]] = []
    for xv, v, wt in zip(ux, ymean, w):
        cur = [v, wt, xv]
        while stack and stack[-1][0] >= cur[0]:   # monotonicity violated -> merge blocks
            pv, pw, _ = stack.pop()
            nw = pw + cur[1]
            cur = [(pv * pw + cur[0] * cur[1]) / nw, nw, cur[2]]
        stack.append(cur)

    knots = np.array([b[2] for b in stack], dtype=float)
    fitted = np.clip(np.array([b[0] for b in stack], dtype=float), 0.0, 1.0)
    return knots, fitted


def _load() -> dict:
    """Fit calibration curves CONDITIONED on the segment actually being traded.

    CRITICAL: a single pooled curve is wrong here. Our own record shows the hit rate depends
    overwhelmingly on market x direction:

        crypto/long 70.2%   forex/long 30.1%   forex/short 22.1%   crypto/short 4.4%

    Pooling them produced a ~38% base rate, so a crypto LONG (really ~70%) was being told it had a
    ~17-38% chance. EV = p*R-(1-p)-cost, so understating p made EV spuriously negative and the gate
    rejected genuinely good trades. We therefore key curves by (market, direction, regime) and fall
    back through (market, direction) -> global as data thins.
    """
    curves: dict = {"segments": {}, "regimes": {}, "global": None, "base": 0.5, "n": 0}
    if not db.enabled():
        return curves
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select coalesce(s.regime,'unknown') regime, abs(s.composite) absc,
                       case when o.pnl > 0 then 1 else 0 end win,
                       case when coalesce(s.market,'crypto') = 'crypto' then 'crypto' else 'forex' end mkt,
                       case when s.label in ('Buy','Strong Buy') then 'long' else 'short' end dir
                from outcomes o join signals s on s.id = o.signal_id
                where o.pnl is not null and s.composite is not null and s.shadow = false
                """
            )
            rows = cur.fetchall()
    except Exception:
        return curves
    if not rows:
        return curves

    absc = np.array([float(r[1]) for r in rows], dtype=float)
    win = np.array([int(r[2]) for r in rows], dtype=float)
    curves["n"] = int(len(rows))
    curves["base"] = float(win.mean())
    kg, fg = _pava(absc, win)
    curves["global"] = (kg, fg)

    def fit(idx: list[int]) -> dict | None:
        if len(idx) < _MIN_REGIME:
            return None
        ii = np.array(idx)
        k, f = _pava(absc[ii], win[ii])
        return {"knots": k, "fitted": f, "n": len(idx), "base": float(win[ii].mean())}

    seg_idx: dict[str, list[int]] = {}
    reg_idx: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        regime, mkt, direction = r[0], r[3], r[4]
        seg_idx.setdefault(f"{mkt}|{direction}", []).append(i)
        seg_idx.setdefault(f"{mkt}|{direction}|{regime}", []).append(i)
        reg_idx.setdefault(regime, []).append(i)

    for key, idx in seg_idx.items():
        c = fit(idx)
        if c:
            curves["segments"][key] = c
    for regime, idx in reg_idx.items():
        c = fit(idx)
        if c:
            curves["regimes"][regime] = c
    return curves


def _curves() -> dict:
    global _cache
    now = time.time()
    if _cache and now - _cache[0] < _TTL:
        return _cache[1]
    c = _load()
    _cache = (now, c)
    return c


def refresh() -> None:
    global _cache
    _cache = None


def win_prob(regime: str | None, abs_composite: float,
             market: str | None = None, direction: str | None = None) -> float:
    """Calibrated P(target before stop) for a setup, in [0.02, 0.98].

    Walks from the most specific curve to the least — (market,direction,regime) ->
    (market,direction) -> regime -> global — shrinking each toward the broader one by sample count.
    Conditioning on market x direction matters enormously here: crypto longs hit ~70% while crypto
    shorts hit ~4%, so one pooled number misprices both.
    """
    c = _curves()
    if c.get("global") is None:
        return 0.5  # no data yet -> non-committal
    kg, fg = c["global"]
    p = float(np.interp(abs_composite, kg, fg))

    def blend(prior: float, curve: dict | None) -> float:
        if not curve:
            return prior
        p_c = float(np.interp(abs_composite, curve["knots"], curve["fitted"]))
        a = curve["n"] / (curve["n"] + _SHRINK)
        return a * p_c + (1 - a) * prior

    # broad -> specific, each level refining the one above it
    p = blend(p, c["regimes"].get(regime or ""))
    if market and direction:
        mkt = "crypto" if market == "crypto" else "forex"
        p = blend(p, c["segments"].get(f"{mkt}|{direction}"))
        p = blend(p, c["segments"].get(f"{mkt}|{direction}|{regime}"))
    return float(min(0.98, max(0.02, p)))


_health_cache: tuple[float, dict] | None = None
_HEALTH_TTL = 120.0


def calibration_health(window: int = 80) -> dict:
    """Self-calibration monitor (§4.6): rolling Brier score of the stored win_prob vs realized wins.

    Brier = mean((p - y)^2); the reference is the base-rate Brier (predicting the constant win
    frequency). ratio = brier / base_brier: <1 means the probabilities add skill, >1 means they're
    worse than a coin weighted by the base rate -> the model is mis-calibrated and we should distrust
    it. Returns a size multiplier that shrinks as calibration degrades.
    """
    global _health_cache
    now = time.time()
    if _health_cache and now - _health_cache[0] < _HEALTH_TTL:
        return _health_cache[1]

    from .config import settings
    out = {"n": 0, "brier": None, "base_brier": None, "ratio": None, "size_mult": 1.0}
    if db.enabled():
        try:
            with db.get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    select s.win_prob, case when o.pnl > 0 then 1.0 else 0.0 end
                    from outcomes o join signals s on s.id = o.signal_id
                    where o.pnl is not null and s.win_prob is not null and s.shadow = false
                    order by o.resolved_at desc limit %s
                    """,
                    (window,),
                )
                rows = cur.fetchall()
        except Exception:
            rows = []
        if len(rows) >= settings.calibration_min_trades:
            ps = np.array([float(p) for p, _ in rows])
            ys = np.array([float(y) for _, y in rows])
            brier = float(np.mean((ps - ys) ** 2))
            base = float(ys.mean())
            base_brier = float(np.mean((base - ys) ** 2))
            ratio = (brier / base_brier) if base_brier > 1e-9 else 1.0
            mult = min(1.0, base_brier / brier) if brier > 1e-9 else 1.0
            mult = max(settings.calibration_size_floor, mult)
            out = {"n": len(rows), "brier": round(brier, 4), "base_brier": round(base_brier, 4),
                   "ratio": round(ratio, 3), "size_mult": round(mult, 3)}
    _health_cache = (now, out)
    return out


def size_multiplier() -> float:
    """Calibration-error size multiplier (1.0 healthy, down to the floor when mis-calibrated)."""
    from .config import settings
    if not settings.calibration_monitor_enabled:
        return 1.0
    return float(calibration_health().get("size_mult", 1.0))


def calibration_status() -> dict:
    c = _curves()
    return {
        "samples": c.get("n", 0),
        "base_rate": round(c.get("base", 0.5), 4),
        "regimes_fitted": sorted(c.get("regimes", {}).keys()),
        # a few readable points on the global curve for a sanity glance
        "global_curve": (
            [{"composite": round(float(x), 1), "p_win": round(float(p), 3)}
             for x, p in zip(*c["global"])][:12]
            if c.get("global") is not None else []
        ),
    }
