"""Drift detection + circuit breaker (Blueprint v2 §4.2, §4 safety rails).

Two survival mechanisms over the realized-outcome stream:

  * Page-Hinkley on the per-trade R sequence — detects a statistically significant DOWNWARD shift
    in mean expectancy within ~10-20 trades. On trigger the engine de-risks: raise the EV floor and
    cut size. Computed over a trailing window so it AUTO-RECOVERS as the bad run ages out.
  * Circuit breaker — if realized R over the last 24h falls below a floor (default -3R), halt all
    new signals for the cooldown window. Rolls off automatically.

R per trade = pnl_fraction / stop_fraction (the realized reward:risk multiple). Both are cached
briefly like the other performance gates so the live path stays cheap.
"""

from __future__ import annotations

import time

from . import db
from .config import settings

_TTL = 120.0
_state_cache: tuple[float, dict] | None = None


def _recent_r(limit: int = 80) -> list[float]:
    """Realized R multiples for the most recent resolved trades, oldest->newest."""
    if not db.enabled():
        return []
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select o.pnl, s.entry, s.stop, o.resolved_at
                from outcomes o join signals s on s.id = o.signal_id
                where o.pnl is not null and s.entry is not null and s.stop is not null
                  and s.entry <> 0 and s.stop <> s.entry and s.shadow = false
                  and o.resolved_at > now() - interval '{int(settings.drift_window_days)} days'
                order by o.resolved_at desc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    except Exception:
        return []
    out: list[float] = []
    for pnl, entry, stop, _ in reversed(rows):  # oldest -> newest
        risk_frac = abs(float(entry) - float(stop)) / abs(float(entry))
        if risk_frac > 1e-9:
            out.append(float(pnl) / risk_frac)
    return out


def page_hinkley(rs: list[float], delta: float, lam: float) -> tuple[bool, float]:
    """Page-Hinkley test for a DOWNWARD mean shift. Returns (drift_detected, final_PH_stat).

    Tracks a running mean; the cumulative negative deviation beyond the max flags a drop."""
    mean = 0.0
    m = 0.0
    M = 0.0
    drift = False
    ph = 0.0
    for i, x in enumerate(rs, 1):
        mean += (x - mean) / i
        # +delta so the cumulative sum RISES on a stable sequence (M tracks it, PH~0); it only
        # falls below its running max when the mean genuinely drops -> no false alarm over time.
        m += x - mean + delta
        M = max(M, m)
        ph = M - m
        if ph > lam:
            drift = True
    return drift, ph


def _daily_r(hours: float) -> tuple[float, int]:
    """(sum of R, trade count) over the last `hours` of resolved trades."""
    if not db.enabled():
        return 0.0, 0
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select coalesce(sum(o.pnl / (abs(s.entry - s.stop) / abs(s.entry))), 0), count(*)
                from outcomes o join signals s on s.id = o.signal_id
                where o.pnl is not null and s.entry is not null and s.stop is not null
                  and s.entry <> 0 and s.stop <> s.entry and s.shadow = false
                  and o.resolved_at > now() - interval '{int(hours)} hours'
                """
            )
            r_sum, n = cur.fetchone()
        return float(r_sum or 0.0), int(n or 0)
    except Exception:
        return 0.0, 0


def state() -> dict:
    """Current drift + circuit-breaker state with the de-risk multipliers. Cached."""
    global _state_cache
    now = time.time()
    if _state_cache and now - _state_cache[0] < _TTL:
        return _state_cache[1]

    rs = _recent_r(settings.drift_window_trades)
    drifting, ph = (False, 0.0)
    if settings.drift_enabled and len(rs) >= settings.drift_min_trades:
        drifting, ph = page_hinkley(rs, settings.drift_delta, settings.drift_lambda)

    day_r, day_n = _daily_r(settings.circuit_window_hours)
    halted = bool(settings.circuit_breaker_enabled and day_n >= settings.circuit_min_trades
                  and day_r < settings.circuit_breaker_r)

    st = {
        "drifting": drifting,
        "ph_stat": round(ph, 3),
        "recent_trades": len(rs),
        "recent_mean_r": round(sum(rs) / len(rs), 4) if rs else None,
        "ev_floor": settings.drift_ev_floor if drifting else 0.0,  # RAISE the EV floor TO this while drifting
        "size_mult": settings.drift_size_mult if drifting else 1.0,
        "circuit_halted": halted,
        "day_r": round(day_r, 3),
        "day_trades": day_n,
    }
    _state_cache = (now, st)
    return st


def refresh() -> None:
    global _state_cache
    _state_cache = None
