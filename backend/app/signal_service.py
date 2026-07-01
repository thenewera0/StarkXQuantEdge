"""Confluence Engine orchestration — turns raw data into an explainable, risk-vetted signal.

Pipeline (spec layers): L1 regime -> L2 factor families -> L3 regime-weighted confluence +
agreement multiplier -> L4 positioning/psychology (boost/veto) -> L5 risk geometry (laddered
targets, RR gate) -> L6 hard filters / silence -> L7 enriched signal object.

CRITICAL: every number is computed here in Python. The LLM only narrates. "Silence is a position":
a vetoed / low-conviction / poor-RR setup returns a Neutral, non-actionable object on purpose.
"""

from __future__ import annotations

import math

import pandas as pd

from . import learning
from .config import settings
from .data import (
    crypto_macro_score,
    fear_greed,
    fetch_depth,
    fetch_funding_basis,
    fetch_klines,
    fetch_klines_td,
    fetch_long_short_ratio,
    fetch_oi_trend,
    fng_score,
    news_sentiment,
    onchain_score,
)
from .factors import label_for, score_row, tier_for
from .indicators import compute_indicators
from .psychology import positioning_engine
from .regime import detect_regime

_LONG = {"Buy", "Strong Buy"}
_SHORT = {"Sell", "Strong Sell"}
_CRYPTO_MARKETS = {"crypto"}
# Only trade trend regimes; stand down in range / high_vol / squeeze (per-regime P&L is negative there).
_TRADEABLE_REGIMES = {"strong_trend", "weak_trend"}
_OI_PERIODS = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}


def _round_price(x: float | None) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    ax = abs(x)
    return round(x, 2) if ax >= 100 else round(x, 4) if ax >= 1 else round(x, 6)


def _num(row: pd.Series, key: str) -> float | None:
    v = row.get(key)
    if v is None or pd.isna(v):
        return None
    return float(v)


def _fetch_ohlcv(symbol: str, interval: str, limit: int, market: str):
    if market in _CRYPTO_MARKETS:
        return fetch_klines(symbol, interval, limit)
    return fetch_klines_td(symbol, interval, outputsize=limit)


def _risk_geometry(row: pd.Series, direction: str, interval: str, regime: str) -> dict:
    """L5 — structure-based stop, laddered targets T1/T2/T3, RR, size. None levels if flat."""
    flat = {"direction": "flat", "entry": None, "stop": None, "target": None,
            "targets": None, "reward_risk": None, "size_pct": None, "invalidation": None}
    price = _num(row, "close")
    atr = _num(row, "atr")
    if direction == "flat" or price is None or atr is None or atr <= 0:
        return flat

    # Volatility-based stop (tight, consistent risk); a nearby swing tightens it further if closer.
    atr_k = 1.2
    size_pct = settings.risk_per_trade_pct
    if regime == "high_vol":          # widen stops, cut size in stressed vol
        atr_k, size_pct = 1.8, size_pct * 0.5

    swing_low = _num(row, "swing_low") or price
    swing_high = _num(row, "swing_high") or price
    pivot_r1 = _num(row, "pivot_r1")
    pivot_s1 = _num(row, "pivot_s1")

    # Laddered targets are R-multiple based; T1 extends to a structure level if one sits FURTHER
    # out (better reward), but never collapses to a nearby swing that would wreck the R:R.
    if direction == "long":
        stop = price - atr_k * atr
        risk = price - stop
        t1 = price + 1.8 * risk
        resistances = [v for v in (swing_high, pivot_r1) if v is not None and t1 < v < price + 3.0 * risk]
        if resistances:
            t1 = min(resistances)
        t2, t3 = price + 2.8 * risk, price + 4.5 * risk
        rr = (t1 - price) / risk if risk > 0 else None
        invalidation = f"{interval} close below {_round_price(stop)}"
    else:  # short
        stop = price + atr_k * atr
        risk = stop - price
        t1 = price - 1.8 * risk
        supports = [v for v in (swing_low, pivot_s1) if v is not None and price - 3.0 * risk < v < t1]
        if supports:
            t1 = max(supports)
        t2, t3 = price - 2.8 * risk, price - 4.5 * risk
        rr = (price - t1) / risk if risk > 0 else None
        invalidation = f"{interval} close above {_round_price(stop)}"

    targets = [_round_price(t1), _round_price(t2), _round_price(t3)]
    return {
        "direction": direction, "entry": _round_price(price), "stop": _round_price(stop),
        "target": targets[0], "targets": targets,
        "reward_risk": round(rr, 2) if rr is not None else None,
        "size_pct": round(size_pct, 2), "invalidation": invalidation,
    }


def compute_signal(
    symbol: str,
    interval: str,
    *,
    market: str = "crypto",
    limit: int = 500,
    with_flow: bool = True,
    with_news: bool = True,
    with_macro: bool = True,
) -> dict:
    market = market.lower()
    is_crypto = market in _CRYPTO_MARKETS
    df = _fetch_ohlcv(symbol, interval, limit, market)
    ind = compute_indicators(df)
    last = ind.iloc[-1]
    regime = detect_regime(last)  # L1

    # --- L2 evidence families ---
    flow_extras = None
    deriv_meta = None
    if with_flow and is_crypto:
        flow_extras = {}
        try:
            flow_extras["imbalance"] = fetch_depth(symbol).get("imbalance")
        except RuntimeError:
            pass
        try:
            flow_extras["long_short_ratio"] = fetch_long_short_ratio(symbol, "1h").get("long_short_ratio")
        except RuntimeError:
            pass
        try:
            fb = fetch_funding_basis(symbol)
            flow_extras["funding_rate"], flow_extras["basis"] = fb["funding_rate"], fb["basis"]
        except RuntimeError:
            pass
        try:
            oi_period = interval if interval in _OI_PERIODS else "4h"
            flow_extras["oi_change"] = fetch_oi_trend(symbol, oi_period).get("oi_change")
        except RuntimeError:
            pass
        deriv_meta = {k: flow_extras.get(k) for k in ("funding_rate", "basis", "oi_change", "long_short_ratio")}

    # F7 sentiment: news + Fear&Greed (crypto)
    sentiment = None
    news_meta = fng_meta = None
    if with_news:
        news_meta = news_sentiment(symbol)
        parts = [p for p in [news_meta.get("score")] if p is not None]
        if is_crypto:
            fng_meta = fear_greed()
            fs = fng_score()
            if fs is not None:
                parts.append(fs)
        if parts:
            sentiment = round(sum(parts) / len(parts), 1)

    # F8 macro + F6 on-chain (crypto)
    macro = macro_meta = None
    onchain = onchain_meta = None
    if is_crypto:
        if with_macro:
            macro_meta = crypto_macro_score(symbol)
            macro = macro_meta.get("score")
        onchain_meta = onchain_score(symbol)
        onchain = onchain_meta.get("score")

    # --- L3 confluence (regime-weighted + agreement multiplier) ---
    weights = learning.active_weights(interval, regime)
    result = score_row(
        last, interval, flow_extras=flow_extras, sentiment=sentiment,
        macro=macro, consensus=onchain, weights=weights,
    )

    # --- L4 positioning / psychology ---
    direction_sign = 1 if result.composite > 0 else (-1 if result.composite < 0 else 0)
    fng_value = fng_meta.get("value") if fng_meta else None
    vwap_dist = _num(last, "vwap_dist")
    psych_mod, crowd_veto, psych_text = positioning_engine(direction_sign, flow_extras, fng_value, vwap_dist)

    composite = max(-100.0, min(100.0, result.composite + psych_mod))
    label = label_for(composite)
    tier = tier_for(abs(composite))
    candidate_dir = "long" if label in _LONG else "short" if label in _SHORT else "flat"

    # --- L5 risk geometry ---
    geo = _risk_geometry(last, candidate_dir, interval, regime)

    # --- L6 hard filters / silence ("silence is a position") ---
    silence_reason = None
    if crowd_veto:
        silence_reason = "crowd_veto"
    elif settings.regime_filter_enabled and regime not in _TRADEABLE_REGIMES:
        silence_reason = "regime_filter"  # only trade trend regimes
    elif abs(composite) < settings.conviction_floor:
        silence_reason = "below_conviction_floor"
    elif geo["direction"] == "flat":
        silence_reason = "neutral"
    elif geo["reward_risk"] is not None and geo["reward_risk"] < settings.min_reward_risk:
        silence_reason = "reward_risk_below_gate"
    actionable = silence_reason is None

    if not actionable:
        label, tier = "Neutral", "no_trade"
        geo = _risk_geometry(last, "flat", interval, regime)

    return {
        "symbol": symbol.upper() if is_crypto else symbol,
        "market": market,
        "interval": interval,
        "regime": regime,
        "as_of": str(ind.index[-1]),
        "label": label,
        "composite": round(composite, 2),
        "confidence": result.confidence,
        "tier": tier,
        "agreement": result.agreement,
        "actionable": actionable,
        "silence_reason": silence_reason,
        "categories": result.categories,
        "price": _round_price(result.price),
        "atr": _round_price(result.atr),
        "levels": {
            "direction": geo["direction"], "entry": geo["entry"], "stop": geo["stop"],
            "target": geo["target"], "reward_risk": geo["reward_risk"],
        },
        "targets": geo["targets"],
        "reward_risk": geo["reward_risk"],
        "size_pct": geo["size_pct"],
        "invalidation": geo["invalidation"],
        "psychology": psych_text,
        "psychology_modifier": psych_mod,
        "crowd_veto": crowd_veto,
        "derivatives": deriv_meta,
        "news": news_meta,
        "fear_greed": fng_meta,
        "macro": macro_meta,
        "onchain": onchain_meta,
        "disclaimer": "Decision-support only, not financial advice. Probabilistic edge; manage risk.",
    }


def get_candles(symbol: str, interval: str, *, market: str = "crypto", limit: int = 300) -> dict:
    """OHLC candles + indicator overlays for the chart. Times are UNIX seconds (UTC)."""
    market = market.lower()
    df = _fetch_ohlcv(symbol, interval, limit, market)
    ind = compute_indicators(df)
    times = (ind.index.view("int64") // 1_000_000_000).astype("int64")

    candles = [
        {"time": int(t), "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        for t, o, h, l, c in zip(times, ind["open"], ind["high"], ind["low"], ind["close"])
    ]

    def line(col: str) -> list[dict]:
        return [
            {"time": int(t), "value": round(float(v), 6)}
            for t, v in zip(times, ind[col]) if not math.isnan(v)
        ]

    return {
        "symbol": symbol.upper() if market in _CRYPTO_MARKETS else symbol,
        "market": market, "interval": interval, "candles": candles,
        "ema50": line("ema50"), "ema200": line("ema200"), "ut_stop": line("ut_stop"),
    }
