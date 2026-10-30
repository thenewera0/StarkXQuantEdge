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
    pillars: dict[str, float] = field(default_factory=dict)  # Phase 1: 5 Orthogonal Pillars


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

    # Phase 1: Purged lagging retail bloat (UT Bot and MA Sabres zero-weighted)
    base = 0.60 * stack_score + 0.20 * price_score + 0.20 * macd_score
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
    if any(pd.isna(row.get(k)) for k in ("close", "pivot", "atr")):
        return None
    atr = row["atr"] or 1e-9
    pivot_score = _tanh100((row["close"] - row["pivot"]) / (0.5 * atr))
    # Static Fibonacci retracement purged; structure relies on causal pivots, swing levels, and VWAP
    return _clip100(pivot_score)


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
        funding_z = extras.get("funding_z")
        funding = extras.get("funding_rate")
        if funding_z is not None:
            parts.append(_clip100(max(-20.0, min(20.0, -8.0 * funding_z)) * 5.0))
            weights.append(0.9)
        elif funding is not None:
            parts.append(_tanh100(-funding / 0.0005))
            weights.append(0.9)
        basis = extras.get("basis")
        if basis is not None:
            parts.append(_tanh100(-basis / 0.002))
            weights.append(0.4)
        oi = extras.get("oi_change")
        if oi is not None:
            parts.append(_clip100(math.copysign(min(abs(oi) / 0.05, 1.0) * 60.0, vwap_score)))
            weights.append(0.4)
    wsum = sum(weights)
    return _clip100(sum(p * w for p, w in zip(parts, weights)) / wsum)


# --- Phase 1: 5 Orthogonal Pillars ---


def pillar_relative_strength(row: pd.Series, extras: dict | None = None) -> float:
    """Pillar 1: Cross-Sectional Relative Strength (weight: 0.25).
    Residual return epsilon_i = R_i - beta_{i,BTC} * R_{BTC} over 20 and 50 bars,
    normalized into a cross-sectional Z-score across the scanned universe.
    """
    if extras and "rs_z" in extras and extras["rs_z"] is not None:
        return _clip100(float(extras["rs_z"]) * 35.0)

    if extras and "residual_ret_20" in extras and extras["residual_ret_20"] is not None:
        r20 = float(extras["residual_ret_20"])
        r50 = float(extras.get("residual_ret_50", r20))
        res_blend = 0.6 * r20 + 0.4 * r50
        return _tanh100(res_blend / 0.05)

    close = row.get("close")
    ema50 = row.get("ema50")
    ks = row.get("kalman_slope")
    if close and ema50 and not pd.isna(close) and not pd.isna(ema50):
        c_dist = (close - ema50) / ema50
        score = _tanh100(c_dist / 0.03) * 0.7
        if ks is not None and not pd.isna(ks):
            score += _tanh100(float(ks) * 1.5) * 0.3
        return _clip100(score)
    return 0.0


def pillar_derivatives_matrix(row: pd.Series, extras: dict | None = None) -> float:
    """Pillar 2: Derivatives OI & CVD Matrix (weight: 0.30).
    Bullish Accumulation (+100): Price Delta > 0, Delta OI > +1.0 sigma, CVD_spot slope > 0, Funding Z-score < +1.5.
    Bearish Distribution (-100): Price Delta < 0 (or stalling at highs), Delta OI > +1.0 sigma,
                                  CVD_perp diverging negatively from CVD_spot, or Funding Z-score > +2.2.
    """
    cvd_z = row.get("cvd_z")
    vwap_dist = row.get("vwap_dist")

    oi_z = None
    funding_z = None
    perp_cvd_div = False
    spot_cvd_pos = False

    if extras:
        oi_z = extras.get("oi_z")
        funding_z = extras.get("funding_z")
        perp_cvd_div = bool(extras.get("perp_cvd_divergence", False))
        spot_cvd_pos = bool(extras.get("spot_cvd_positive", (cvd_z or 0) > 0))

    if oi_z is None:
        oi_z = row.get("oi_z")
    if funding_z is None:
        funding_z = row.get("funding_z")

    oi_z = float(oi_z) if (oi_z is not None and not pd.isna(oi_z)) else 0.0
    funding_z = float(funding_z) if (funding_z is not None and not pd.isna(funding_z)) else 0.0
    cvd_val = float(cvd_z) if (cvd_z is not None and not pd.isna(cvd_z)) else 0.0
    px_delta = float(vwap_dist) if (vwap_dist is not None and not pd.isna(vwap_dist)) else 0.0

    if px_delta > 0 and oi_z > 1.0 and (spot_cvd_pos or cvd_val > 0) and funding_z < 1.5:
        return 100.0

    if (px_delta <= 0 and oi_z > 1.0 and (perp_cvd_div or cvd_val < 0)) or funding_z > 2.2:
        return -100.0

    base = cvd_val * 25.0
    if oi_z > 0.5:
        base += 20.0 if px_delta > 0 else -20.0
    if funding_z > 1.8:
        base -= (funding_z - 1.8) * 40.0
    elif funding_z < -1.8:
        base += (-funding_z - 1.8) * 30.0

    return _clip100(base)


def pillar_vol_compression(row: pd.Series, regime: str | None = None) -> float:
    """Pillar 3: Volatility Compression / Regime Structure (weight: 0.20).
    Scores high (+100 in direction of trend) when bbw_pct_rank < 0.20 and hv_ratio < 0.70 ahead of directional expansion.
    Filters for mean-reversion when Hurst H < 0.45.
    """
    bbw_rank = row.get("bbw_pct_rank")
    hv = row.get("hv_ratio")
    hurst = row.get("hurst")

    bbw_rank = float(bbw_rank) if (bbw_rank is not None and not pd.isna(bbw_rank)) else 0.5
    hv = float(hv) if (hv is not None and not pd.isna(hv)) else 1.0
    hurst = float(hurst) if (hurst is not None and not pd.isna(hurst)) else 0.5

    close = row.get("close") or 1.0
    ema50 = row.get("ema50") or close
    dir_sign = 1.0 if close >= ema50 else -1.0

    if bbw_rank < 0.20 and hv < 0.70:
        return dir_sign * 100.0

    if hurst < 0.45:
        bb_pctb = row.get("bb_pctb")
        if bb_pctb is not None and not pd.isna(bb_pctb):
            return _clip100(-(float(bb_pctb) - 0.5) * 200.0)

    compression_score = max(0.0, (0.5 - bbw_rank) * 200.0)
    return _clip100(dir_sign * compression_score)


def pillar_liquidity_sweep(row: pd.Series, extras: dict | None = None) -> float:
    """Pillar 4: Liquidity Sweep & Wick Absorption (weight: 0.15).
    Detects sweeps of 20-bar swing highs/lows with >2.0 sigma volume spikes
    and >45% rejection wicks where Open Interest flushes (Delta OI < -1.5 sigma).
    """
    close = row.get("close")
    open_px = row.get("open")
    high = row.get("high")
    low = row.get("low")
    vol = row.get("volume")
    vol_sma = row.get("vol_sma20")
    oi_z = row.get("oi_z")

    if None in (close, open_px, high, low, vol, vol_sma) or (high - low) <= 0:
        return 0.0

    rng = high - low
    upper_wick = high - max(close, open_px)
    lower_wick = min(close, open_px) - low
    vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
    oi_flush = (oi_z is not None and oi_z < -1.5) or bool(extras and extras.get("oi_flush", False))

    if lower_wick / rng >= 0.45 and (vol_ratio >= 2.0 or oi_flush):
        return 100.0

    if upper_wick / rng >= 0.45 and (vol_ratio >= 2.0 or oi_flush):
        return -100.0

    return 0.0


def pillar_htf_vwap_structure(row: pd.Series, extras: dict | None = None) -> float:
    """Pillar 5: Higher-Timeframe VWAP & Market Structure (weight: 0.10).
    Position relative to Rolling 5-Day and 20-Day VWAP and structural higher-highs/higher-lows.
    """
    close = row.get("close")
    vwap = row.get("vwap")
    up2 = row.get("vwap_up2")
    lo2 = row.get("vwap_lo2")

    if None in (close, vwap) or pd.isna(close) or pd.isna(vwap):
        return 0.0

    c, v = float(close), float(vwap)
    vwap_score = _tanh100((c - v) / (0.01 * v))

    if up2 is not None and not pd.isna(up2) and c > up2:
        vwap_score = max(vwap_score, 80.0)
    elif lo2 is not None and not pd.isna(lo2) and c < lo2:
        vwap_score = min(vwap_score, -80.0)

    return _clip100(vwap_score)


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
    """Score a single indicator row into orthogonal alpha pillars.

    Daily Fear & Greed sentiment is purged from intraday/4h signal generation.
    """
    # Deprecate daily sentiment from intraday / 4h intervals
    effective_sentiment = None if interval in ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h") else sentiment

    # 5 Orthogonal Pillars
    p1 = pillar_relative_strength(row, flow_extras)
    p2 = pillar_derivatives_matrix(row, flow_extras)
    p3 = pillar_vol_compression(row, regime)
    p4 = pillar_liquidity_sweep(row, flow_extras)
    p5 = pillar_htf_vwap_structure(row, flow_extras)

    core_cats: dict[str, float | None] = {
        "trend": _trend(row),
        "momentum": _momentum(row, regime),
        "volatility": _volatility(row, regime),
        "structure": _structure(row),
        "flow": _flow(row, flow_extras),
        "sentiment": effective_sentiment,
        "macro": macro,
        "consensus": consensus,
    }
    pillars_dict: dict[str, float] = {
        "pillar1_rs": p1,
        "pillar2_derivatives": p2,
        "pillar3_vol_regime": p3,
        "pillar4_liq_sweep": p4,
        "pillar5_htf_vwap": p5,
    }

    if weights is not None:
        # Caller provided an explicit category weight map
        available = {k: v for k, v in core_cats.items() if v is not None and k in weights}
        wsum = sum(abs(weights[k]) for k in available)
        raw = sum(weights[k] * v for k, v in available.items()) / wsum if wsum > 0 else 0.0
    else:
        # Default: 5 Orthogonal Pillars (0.25, 0.30, 0.20, 0.15, 0.10)
        raw = 0.25 * p1 + 0.30 * p2 + 0.20 * p3 + 0.15 * p4 + 0.10 * p5

    raw = _clip100(raw)

    available_core = {k: v for k, v in core_cats.items() if v is not None}
    if available_core:
        comp_sign = 1 if raw >= 0 else -1
        agree_n = sum(1 for v in available_core.values() if (1 if v >= 0 else -1) == comp_sign)
        agreement = agree_n / len(available_core)
        coverage = 100.0 * len(available_core) / len(CATEGORIES)
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
        categories={k: (round(v, 2) if v is not None else None) for k, v in core_cats.items()},
        bucket_interval=interval,
        price=float(row["close"]),
        atr=float(row["atr"]) if not pd.isna(row.get("atr")) else float("nan"),
        pillars={k: round(v, 2) for k, v in pillars_dict.items()},
    )


def _clip_conf(x: float) -> float:
    return float(max(0.0, min(100.0, x)))


def label_for(composite: float) -> str:
    return _label_for(composite)


def tier_for(abs_composite: float) -> str:
    return _tier_for(abs_composite)
