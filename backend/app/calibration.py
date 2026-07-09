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
    """Fit global + per-regime calibration curves from resolved outcomes."""
    curves: dict = {"regimes": {}, "global": None, "base": 0.5, "n": 0}
    if not db.enabled():
        return curves
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select coalesce(s.regime,'unknown') regime, abs(s.composite) absc,
                       case when o.pnl > 0 then 1 else 0 end win
                from outcomes o join signals s on s.id = o.signal_id
                where o.pnl is not null and s.composite is not null
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

    by: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        by.setdefault(r[0], []).append(i)
    for regime, idx in by.items():
        if len(idx) < _MIN_REGIME:
            continue
        ii = np.array(idx)
        k, f = _pava(absc[ii], win[ii])
        curves["regimes"][regime] = {"knots": k, "fitted": f, "n": len(idx), "base": float(win[ii].mean())}
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


def win_prob(regime: str | None, abs_composite: float) -> float:
    """Calibrated P(target before stop) for a setup, in [0.02, 0.98].

    Uses the regime curve shrunk toward the global curve by sample count; falls back to the global
    curve, then the global base rate, when data is thin.
    """
    c = _curves()
    if c.get("global") is None:
        return 0.5  # no data yet -> non-committal
    kg, fg = c["global"]
    p_global = float(np.interp(abs_composite, kg, fg))

    reg = c["regimes"].get(regime or "")
    if reg is None:
        p = p_global
    else:
        p_reg = float(np.interp(abs_composite, reg["knots"], reg["fitted"]))
        alpha = reg["n"] / (reg["n"] + _SHRINK)
        p = alpha * p_reg + (1 - alpha) * p_global
    return float(min(0.98, max(0.02, p)))


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
