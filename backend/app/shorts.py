"""Bear-regime short qualification — the missing test that made every short lose.

WHAT THE DATA SAID (321 live outcomes). Same engine, same regimes, opposite direction:

    regime        SHORT hit / P&L        LONG hit / P&L
    range          8%  / -$527           66% / +$834
    weak_trend    23%  / -$225           51% / +$1,147
    trending       0%  / -$150           40% /   -$5
    strong_trend  15%  /  -$37           25% /  -$51

Shorts were not badly *sized* or badly *timed* — they were taken COUNTER-TREND in a tape where
every dip got bought. The engine never asked "is this actually a downtrend?" before shorting.

Professional short books answer that first. This module is that gate, and only that gate:

  1. TREND ALIGNMENT   price below the 200EMA *and* below a falling 50EMA on the signal timeframe,
                       confirmed by the higher timeframe (no counter-trend shorts, ever).
  2. STRUCTURE         lower highs — the last swing high must be below the prior one (distribution),
                       not a V-bottom bounce.
  3. CONVICTION FLOOR  shorts require |composite| >= short_min_conviction. In our record the only
                       winning shorts scored 52-69; every loser sat at 31-49.
  4. CROWDING FUEL     positive funding = crowded longs whose stops are the fuel for a flush. A
                       short into NEGATIVE funding is shorting an already-short crowd (squeeze risk).

Any single failure disqualifies the short. This is deliberately hard to pass: in the record above,
a filter this strict would have removed nearly every losing short while keeping the winners.
"""

from __future__ import annotations

import pandas as pd

from .config import settings


def _f(row: pd.Series, key: str) -> float | None:
    v = row.get(key)
    if v is None or pd.isna(v):
        return None
    return float(v)


def qualify_short(ind: pd.DataFrame, composite: float, htf_trend: int,
                  funding: float | None = None) -> dict:
    """Decide whether a SHORT is allowed. Returns {ok, reasons, checks}.

    ind        — indicator frame (last row = the closed signal bar)
    composite  — the engine's signed composite score (negative = bearish)
    htf_trend  — +1/0/-1 higher-timeframe trend state
    funding    — current perp funding rate, if available
    """
    if not settings.short_gate_enabled:
        return {"ok": True, "reasons": [], "checks": {"gate": "disabled"}}

    last = ind.iloc[-1]
    checks: dict[str, bool | str | float | None] = {}
    fails: list[str] = []

    close = _f(last, "close")
    ema50 = _f(last, "ema50")
    ema200 = _f(last, "ema200")
    ema200_slope = _f(last, "ema200_slope")

    # --- 1. trend alignment: below both key MAs, and the long MA must not be rising ---
    below = bool(close and ema200 and close < ema200 and (ema50 is None or close < ema50))
    checks["below_key_mas"] = below
    if not below:
        fails.append("not in a downtrend (price is not below its 200/50 EMA)")

    slope_ok = bool(ema200_slope is not None and ema200_slope <= 0.0)
    checks["ema200_falling"] = slope_ok
    if not slope_ok:
        fails.append("the 200EMA is still rising")

    # --- 2. higher-timeframe agreement: never short into an up HTF ---
    htf_ok = htf_trend <= 0
    checks["htf_aligned"] = htf_ok
    if not htf_ok:
        fails.append("higher timeframe is trending up")

    # --- 3. structure: lower highs (distribution), not a bounce ---
    lower_high = None
    try:
        sh = ind["swing_high"].dropna()
        if len(sh) > 30:
            lower_high = bool(float(sh.iloc[-1]) <= float(sh.iloc[-25]))
    except Exception:
        lower_high = None
    checks["lower_highs"] = lower_high
    if lower_high is False:
        fails.append("structure still making higher highs")

    # --- 4. conviction floor (winners scored 52-69; losers 31-49) ---
    conv_ok = abs(composite) >= settings.short_min_conviction
    checks["conviction"] = round(abs(composite), 1)
    if not conv_ok:
        fails.append(f"conviction {abs(composite):.0f} below the {settings.short_min_conviction:.0f} short floor")

    # --- 5. crowding fuel: prefer shorting a crowded-long book ---
    if funding is not None:
        crowd_ok = funding >= settings.short_min_funding
        checks["funding"] = round(funding, 6)
        if not crowd_ok:
            fails.append("funding is negative — the crowd is already short (squeeze risk)")

    return {"ok": not fails, "reasons": fails, "checks": checks}
