"""Trade geometry — stop, laddered targets, reward:risk (Confluence L5 + Blueprint v2 §2.2).

Shared by the LIVE scorer (signal_service) and the BACKTEST harness so both plan a trade the same
way — otherwise the champion/challenger gate would measure a different strategy than what trades.

Two families:
  * trend  (strong_trend / weak_trend / high_vol / squeeze): ATR stop + R-multiple laddered targets
    that extend to a structure level if one sits further out (continuation).
  * range  (§2.2): FADE geometry — target the mean (mid band) then the opposite band, stop beyond
    the band being faded. A range fade reverts to the mean; it does NOT extend 1.8R, so an
    R-multiple target would never fill.

Pure functions over primitives (floats) — no DataFrame, no app imports — so it is trivially
unit-testable and cannot create an import cycle.
"""

from __future__ import annotations

import math

_TREND_ATR_K = 1.2
_RANGE_REGIME = "range"


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(xf) else xf


def _flat() -> dict:
    return {"direction": "flat", "entry": None, "stop": None, "target": None,
            "targets": None, "reward_risk": None, "size_pct": None, "invalidation": None}


def _round_price(x: float | None) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    ax = abs(x)
    return round(x, 2) if ax >= 100 else round(x, 4) if ax >= 1 else round(x, 6)


def _range_fade(direction: str, price: float, atr: float,
                bb_mid: float | None, bb_upper: float | None, bb_lower: float | None):
    """Return (stop, t1, t2, t3) for a range fade, or None if the bands don't support it."""
    if bb_mid is None or bb_upper is None or bb_lower is None or bb_upper <= bb_lower:
        return None
    if direction == "long":                        # fade oversold: price should be below the mean
        if not price < bb_mid:
            return None
        stop = min(price - 1.0 * atr, bb_lower - 0.25 * atr)
        t1, t2, t3 = bb_mid, bb_upper, bb_upper
        if not (stop < price < t1):
            return None
    else:                                          # fade overbought: price above the mean
        if not price > bb_mid:
            return None
        stop = max(price + 1.0 * atr, bb_upper + 0.25 * atr)
        t1, t2, t3 = bb_mid, bb_lower, bb_lower
        if not (t1 < price < stop):
            return None
    return stop, t1, t2, t3


def trade_levels(
    price: float | None, atr: float | None, direction: str, interval: str, regime: str | None,
    *, swing_high=None, swing_low=None, pivot_r1=None, pivot_s1=None,
    bb_mid=None, bb_upper=None, bb_lower=None, risk_per_trade_pct: float = 0.75,
) -> dict:
    """Plan a trade. Returns entry/stop/laddered targets/reward_risk/size/invalidation, or flat."""
    price = _num(price)
    atr = _num(atr)
    if direction not in ("long", "short") or price is None or atr is None or atr <= 0:
        return _flat()

    size_pct = risk_per_trade_pct
    is_range = regime == _RANGE_REGIME
    fade = _range_fade(direction, price, atr,
                       _num(bb_mid), _num(bb_upper), _num(bb_lower)) if is_range else None

    # In a range we ONLY take a fade at a band extreme; if there's no valid fade setup, stand down
    # rather than planning a trend-extension target the mean-reverting price will never reach.
    if is_range and fade is None:
        return _flat()

    if fade is not None:
        stop, t1, t2, t3 = fade
        risk = abs(price - stop)
        rr = (t1 - price) / risk if direction == "long" else (price - t1) / risk
        invalidation = f"{interval} close {'below' if direction == 'long' else 'above'} {_round_price(stop)} (range breaks)"
    else:
        # Trend / continuation geometry.
        atr_k = _TREND_ATR_K
        if regime == "high_vol":
            atr_k, size_pct = 1.8, size_pct * 0.5
        sh, sl = _num(swing_high) or price, _num(swing_low) or price
        pr1, ps1 = _num(pivot_r1), _num(pivot_s1)
        if direction == "long":
            stop = price - atr_k * atr
            risk = price - stop
            t1 = price + 1.8 * risk
            res = [v for v in (sh, pr1) if v is not None and t1 < v < price + 3.0 * risk]
            if res:
                t1 = min(res)
            t2, t3 = price + 2.8 * risk, price + 4.5 * risk
            rr = (t1 - price) / risk if risk > 0 else None
            invalidation = f"{interval} close below {_round_price(stop)}"
        else:
            stop = price + atr_k * atr
            risk = stop - price
            t1 = price - 1.8 * risk
            sup = [v for v in (sl, ps1) if v is not None and price - 3.0 * risk < v < t1]
            if sup:
                t1 = max(sup)
            t2, t3 = price - 2.8 * risk, price - 4.5 * risk
            rr = (price - t1) / risk if risk > 0 else None
            invalidation = f"{interval} close above {_round_price(stop)}"

    targets = [_round_price(t1), _round_price(t2), _round_price(t3)]
    return {
        "direction": direction, "entry": _round_price(price), "stop": _round_price(stop),
        "target": targets[0], "targets": targets,
        "reward_risk": round(rr, 2) if rr is not None else None,
        "size_pct": round(size_pct, 2), "invalidation": invalidation,
        "is_fade": fade is not None,
    }
