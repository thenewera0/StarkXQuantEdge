"""Score one indicator row into an 8-category composite signal.

Each category is scored on [-100, +100] (negative = bearish, positive = bullish). The
composite is a weighted average over the categories that have data; weights for missing
categories (e.g. sentiment in a pure historical backtest) are renormalized away rather than
counted as neutral. Confidence blends signal magnitude, cross-category agreement, and coverage.

All math is deterministic. The LLM (Phase 1b) only narrates these numbers — it never alters them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .weights import CATEGORIES, weights_for_interval

LABELS = ("Strong Sell", "Sell", "Neutral", "Buy", "Strong Buy")


@dataclass
class SignalResult:
    label: str
    composite: float           # -100..100 (agreement-adjusted)
    confidence: float          # 0..100
    tier: str                  # no_trade | watch | standard | high
    agreement: float           # 0..1 fraction of families agreeing with the sign
    categories: dict[str, float | None]  # per-category score or None if unavailable
    bucket_interval: str
    price: float
    atr: float


def _tier_for(abs_composite: float) -> str:
    # Confluence Engine L3 conviction tiers (spec uses 0.25/0.45/0.65 on a 0..1 scale).
    if abs_composite < 25:
        return "no_trade"
    if abs_composite < 45:
        return "watch"
    if abs_composite < 65:
        return "standard"
    return "high"


def _clip100(x: float) -> float:
    return float(max(-100.0, min(100.0, x)))


def _tanh100(x: float) -> float:
    return 100.0 * math.tanh(x)


def _label_for(composite: float) -> str:
    if composite >= 60:
        return "Strong Buy"
    if composite >= 20:
        return "Buy"
    if composite > -20:
        return "Neutral"
    if composite > -60:
        return "Sell"
    return "Strong Sell"


# --- Per-category scorers (each returns float in [-100,100] or None) --------


def _trend(row: pd.Series) -> float | None:
    needed = ("ema9", "ema21", "ema50", "ema200", "close", "macd_hist", "atr")
    if any(pd.isna(row.get(k)) for k in needed):
        return None
    emas = [row["ema9"], row["ema21"], row["ema50"], row["ema200"]]
    stack = 0
    for a, b in zip(emas, emas[1:]):
        stack += 1 if a > b else (-1 if a < b else 0)
    stack_score = stack / 3.0 * 100.0
    price_score = 100.0 if row["close"] > row["ema200"] else -100.0
    atr = row["atr"] or 1e-9
    macd_score = _tanh100(row["macd_hist"] / (0.5 * atr))

    # UT Bot trailing-stop state (+1 long / -1 short) as a real trend component.
    ut = row.get("ut_pos")
    ut_score = (ut * 100.0) if (ut is not None and not pd.isna(ut)) else 0.0

    base = 0.45 * stack_score + 0.15 * price_score + 0.15 * macd_score + 0.25 * ut_score

    # LuxAlgo MA Sabres reversal: a fresh flip nudges the trend in its direction.
    sabre = row.get("sabre")
    if sabre is not None and not pd.isna(sabre) and sabre != 0:
        base += float(sabre) * 25.0

    return _clip100(base)


def _momentum(row: pd.Series, regime: str | None = None) -> float | None:
    if pd.isna(row.get("rsi")) or pd.isna(row.get("stoch_k")):
        return None
    rsi_score = (row["rsi"] - 50.0) / 50.0 * 100.0
    stoch_score = (row["stoch_k"] - 50.0) / 50.0 * 100.0
    score = 0.6 * rsi_score + 0.4 * stoch_score
    # §2.2: momentum is CONTINUATION in trends but MEAN-REVERSION in ranges. Overbought in a range
    # is bearish (fade), not bullish. Flip the sign so the range family fades extremes.
    if regime == "range":
        score = -score
    return _clip100(score)


def _volatility(row: pd.Series, regime: str | None = None) -> float | None:
    if pd.isna(row.get("bb_pctb")):
        return None
    # %B position within the band: above mid = bullish pressure (trend) / overextended (range).
    score = (row["bb_pctb"] - 0.5) * 200.0
    if regime == "range":
        score = -score  # fade the band edges in a range
    return _clip100(score)


def _structure(row: pd.Series) -> float | None:
    if any(pd.isna(row.get(k)) for k in ("close", "pivot", "fib_pos", "atr")):
        return None
    atr = row["atr"] or 1e-9
    pivot_score = _tanh100((row["close"] - row["pivot"]) / (0.5 * atr))
    fib_score = (row["fib_pos"] - 0.5) * 200.0
    return _clip100(0.6 * pivot_score + 0.4 * fib_score)


def _flow(row: pd.Series, extras: dict | None) -> float | None:
    """F5 — Derivatives / order flow. VWAP pressure + funding (contrarian) + OI/basis + L/S."""
    if pd.isna(row.get("vwap_dist")):
        return None
    vwap_score = _tanh100(row["vwap_dist"] / 0.005)
    parts = [vwap_score]
    weights = [1.0]
    if extras:
        imb = extras.get("imbalance")
        if imb is not None:
            parts.append(_clip100(imb * 100.0))
            weights.append(0.7)
        lsr = extras.get("long_short_ratio")
        if lsr is not None and lsr > 0:
            parts.append(_tanh100(math.log(lsr)))
            weights.append(0.4)
        funding = extras.get("funding_rate")
        if funding is not None:
            # Extreme positive funding = longs overcrowded -> contrarian BEARISH for flow.
            parts.append(_tanh100(-funding / 0.0005))
            weights.append(0.9)
        basis = extras.get("basis")
        if basis is not None:
            # Premium (perp > spot) = leveraged longs leaning -> mildly contrarian bearish.
            parts.append(_tanh100(-basis / 0.002))
            weights.append(0.4)
        oi = extras.get("oi_change")
        if oi is not None:
            # Rising OI confirms the vwap direction; combine sign of vwap with OI growth.
            parts.append(_clip100(math.copysign(min(abs(oi) / 0.05, 1.0) * 60.0, vwap_score)))
            weights.append(0.4)
    wsum = sum(weights)
    return _clip100(sum(p * w for p, w in zip(parts, weights)) / wsum)


# --- Public entry point -----------------------------------------------------


def score_row(
    row: pd.Series,
    interval: str,
    *,
    regime: str | None = None,
    flow_extras: dict | None = None,
    sentiment: float | None = None,
    macro: float | None = None,
    consensus: float | None = None,
    weights: dict[str, float] | None = None,
) -> SignalResult:
    """Score a single indicator row. External categories default to None (unavailable).

    `regime` makes momentum/volatility regime-conditional (continuation in trends, fade in ranges).
    `weights` overrides the fixed per-timeframe profile (used by the adaptive learning loop and
    the champion/challenger backtest). When None, the fixed profile for the interval is used.
    """
    cats: dict[str, float | None] = {
        "trend": _trend(row),
        "momentum": _momentum(row, regime),
        "volatility": _volatility(row, regime),
        "structure": _structure(row),
        "flow": _flow(row, flow_extras),
        "sentiment": sentiment,
        "macro": macro,
        "consensus": consensus,
    }

    weights = weights or weights_for_interval(interval)
    available = {k: v for k, v in cats.items() if v is not None}
    # Normalize by sum(|w|): identical to sum(w) for the fixed all-positive profiles, but correct
    # when the learning loop promotes a SIGNED weight (a factor learned to be contrarian). Without
    # this, a negative weight would distort the denominator and blow up the composite scale.
    wsum = sum(abs(weights[k]) for k in available)
    raw = sum(weights[k] * v for k, v in available.items()) / wsum if wsum > 0 else 0.0
    raw = _clip100(raw)

    # Agreement multiplier (Confluence Engine L3 Step D) — breadth of agreement beats one loud
    # indicator. agree = fraction of available families sharing the composite's sign.
    if available:
        comp_sign = 1 if raw >= 0 else -1
        agree_n = sum(1 for v in available.values() if (1 if v >= 0 else -1) == comp_sign)
        agreement = agree_n / len(available)
        coverage = 100.0 * len(available) / len(CATEGORIES)
    else:
        agreement = 0.0
        coverage = 0.0

    composite = _clip100(raw * (0.5 + 0.5 * agreement))
    label = _label_for(composite)
    confidence = _clip_conf(0.5 * abs(composite) + 0.3 * (agreement * 100.0) + 0.2 * coverage)

    return SignalResult(
        label=label,
        composite=round(composite, 2),
        confidence=round(confidence, 1),
        tier=_tier_for(abs(composite)),
        agreement=round(agreement, 3),
        categories={k: (round(v, 2) if v is not None else None) for k, v in cats.items()},
        bucket_interval=interval,
        price=float(row["close"]),
        atr=float(row["atr"]) if not pd.isna(row.get("atr")) else float("nan"),
    )


def _clip_conf(x: float) -> float:
    return float(max(0.0, min(100.0, x)))


def label_for(composite: float) -> str:
    return _label_for(composite)


def tier_for(abs_composite: float) -> str:
    return _tier_for(abs_composite)
