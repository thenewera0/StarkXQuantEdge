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
    limit_offset_atr: float | None = None, limit_expiry_bars: int | None = None,
    partial_book_at_r: float | None = None, partial_book_fraction: float | None = None,
) -> dict:
    """Plan a trade. Returns entry/stop/laddered targets/reward_risk/size/invalidation, or flat.

    `limit_offset_atr` turns the entry into a RESTING LIMIT price that many ATR away from the
    close (None = market entry at the close). Passed in rather than read from settings so this
    module stays pure and gives identical geometry in live and backtest.
    """
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
        # Realistic Target Calibration:
        # Prevents wide ATR or daily candles from projecting unrealistic +15% to +80% targets.
        # T1 is the high-probability milestone to bank profits / trigger breakeven protection.
        # T2 and T3 capture multi-week trend extensions.
        atr_pct = (atr / price) if price > 0 else 0.03
        is_daily = interval in ("1d", "1w")
        is_crypto = atr_pct > 0.065
        cap_pct = (0.10 if is_daily else 0.065) if is_crypto else (0.060 if is_daily else 0.038)

        if direction == "long":
            stop = price - atr_k * atr
            risk = price - stop
            t1_dist = min(1.35 * risk, max(1.1 * atr, cap_pct * price))
            t1_dist = min(t1_dist, 1.40 * risk)
            t1 = price + t1_dist
            res = [v for v in (sh, pr1) if v is not None and t1 < v < price + min(2.5 * risk, 2.0 * t1_dist)]
            if res:
                t1 = min(res)
            t2 = price + min(2.0 * risk, 2.0 * t1_dist)
            t3 = price + min(3.5 * risk, 3.5 * t1_dist)
            rr = (t1 - price) / risk if risk > 0 else None
            invalidation = f"{interval} close below {_round_price(stop)}"
        else:
            stop = price + atr_k * atr
            risk = stop - price
            t1_dist = min(1.35 * risk, max(1.1 * atr, cap_pct * price))
            t1_dist = min(t1_dist, 1.40 * risk)
            t1 = price - t1_dist
            sup = [v for v in (sl, ps1) if v is not None and price - min(2.5 * risk, 2.0 * t1_dist) < v < t1]
            if sup:
                t1 = max(sup)
            t2 = price - min(2.0 * risk, 2.0 * t1_dist)
            t3 = price - min(3.5 * risk, 3.5 * t1_dist)
            rr = (price - t1) / risk if risk > 0 else None
            invalidation = f"{interval} close above {_round_price(stop)}"

    targets = [_round_price(t1), _round_price(t2), _round_price(t3)]

    # ENTRY = a RESTING LIMIT PRICE, not the close. Measured on 14,047 signals, resting the entry
    # 0.20 ATR away and cancelling after 2 bars beat market entry by +0.39 percentage points per
    # signal — and that figure already counts every order that never filled as a zero. It wins on
    # two fronts: the maker fee replaces spread-crossing (0.04% vs 0.16-0.28% round trip), and the
    # fill itself is 0.20 ATR better than the close.
    #
    # The stop and targets stay anchored to the LIMIT price, so the risk geometry the operator
    # sees is the geometry they actually get. Levels are not re-derived from the close.
    entry_px = price
    if limit_offset_atr and atr and atr > 0:
        dist = float(limit_offset_atr) * float(atr)
        entry_px = price - dist if direction == "long" else price + dist
        shift = entry_px - price
        stop += shift
        targets = [None if t is None else _round_price(t + shift) for t in
                   (t1, t2, t3)]
        risk_now = abs(entry_px - stop)
        rr = (abs(targets[0] - entry_px) / risk_now) if targets[0] and risk_now > 0 else rr

    # PARTIAL BOOK level: where half the position comes off. Measured as the single most
    # effective exit change (+0.242pp/signal at 0.20R); see config.partial_book_at_r.
    partial_target = None
    if partial_book_at_r:
        risk_now = abs(entry_px - stop)
        if risk_now > 0:
            partial_target = _round_price(
                entry_px + partial_book_at_r * risk_now if direction == "long"
                else entry_px - partial_book_at_r * risk_now)

    return {
        "direction": direction, "entry": _round_price(entry_px), "stop": _round_price(stop),
        "target": targets[0], "targets": targets,
        "partial_target": partial_target,
        "partial_fraction": partial_book_fraction if partial_target else None,
        "reward_risk": round(rr, 2) if rr is not None else None,
        "size_pct": round(size_pct, 2), "invalidation": invalidation,
        "is_fade": fade is not None,
        "order_type": "limit" if limit_offset_atr else "market",
        "limit_expiry_bars": limit_expiry_bars if limit_offset_atr else None,
    }
