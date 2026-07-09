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

from . import calibration, learning, meta_features, meta_model
from .config import settings
from .costs import cost_in_r
from .geometry import trade_levels
from .indicators import htf_trend
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
from .data.validate import validate_ohlcv
from .factors import label_for, score_row, tier_for
from .indicators import compute_indicators
from .psychology import positioning_engine
from .regime import detect_regime

_LONG = {"Buy", "Strong Buy"}
_SHORT = {"Sell", "Strong Sell"}
_CRYPTO_MARKETS = {"crypto"}
# Baseline: only trade trend regimes. The live gate (learning.tradeable_regimes) narrows this
# further to regimes with proven positive expectancy once enough outcomes exist.
_TRADEABLE_REGIMES = {"strong_trend", "weak_trend"}


def _allowed_regimes() -> set[str]:
    if settings.regime_perf_gate_enabled:
        return learning.tradeable_regimes(settings.regime_perf_min_sample, settings.regime_perf_window_days)
    return _TRADEABLE_REGIMES


def _allowed_directions() -> set[str]:
    if settings.direction_perf_gate_enabled:
        return learning.tradeable_directions(
            settings.direction_perf_min_sample, settings.direction_perf_window_days
        )
    return {"long", "short"}
_OI_PERIODS = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}


def _rr_floor(regime: str | None) -> float:
    """Range fades win often but small, so they clear a looser reward:risk floor than trends."""
    return settings.min_reward_risk_range if regime == "range" else settings.min_reward_risk


def _range_reversion_ok(row: pd.Series) -> bool:
    """§3.3: only fade a range when the OU half-life is finite and short (fast mean reversion).
    Missing/NaN half-life (not mean-reverting) or a long half-life (slow/drifting) -> stand down."""
    hl = row.get("ou_halflife")
    if hl is None or pd.isna(hl):
        return False
    return 0.0 < float(hl) <= settings.range_max_halflife_bars


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
        df = fetch_klines(symbol, interval, limit)
    else:
        df = fetch_klines_td(symbol, interval, outputsize=limit)
    df, _ = validate_ohlcv(df, interval)  # drop dupes/NaN/inconsistent bars before scoring
    return df


def _risk_geometry(row: pd.Series, direction: str, interval: str, regime: str) -> dict:
    """L5 — delegate to the shared geometry module (same plan live + backtest). Range uses fade
    geometry (target the mean/opposite band); trends use ATR stop + laddered R targets."""
    return trade_levels(
        _num(row, "close"), _num(row, "atr"), direction, interval, regime,
        swing_high=_num(row, "swing_high"), swing_low=_num(row, "swing_low"),
        pivot_r1=_num(row, "pivot_r1"), pivot_s1=_num(row, "pivot_s1"),
        bb_mid=_num(row, "bb_mid"), bb_upper=_num(row, "bb_upper"), bb_lower=_num(row, "bb_lower"),
        risk_per_trade_pct=settings.risk_per_trade_pct,
    )


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
        last, interval, regime=regime, flow_extras=flow_extras, sentiment=sentiment,
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

    # --- L5b expected value (Blueprint v2 §2.6): calibrated P(win) x R minus modelled cost ---
    win_prob = calibration.win_prob(regime, abs(composite))
    price_v = _num(last, "close")
    atr_v = _num(last, "atr")
    atr_pct = (atr_v / price_v) if (atr_v and price_v) else 0.0

    # --- L5c meta-labeling (§5): richer secondary P(win). Shadow-logged; drives EV only if promoted.
    _ts = ind.index[-1]
    raw_features = {
        "composite": composite, "agreement": result.agreement, "reward_risk": geo["reward_risk"],
        "atr_pct": atr_pct, "win_prob": win_prob,
        "hour_of_week": _ts.dayofweek * 24 + _ts.hour, "htf_trend": htf_trend(df, interval),
        "is_long": candidate_dir == "long", "regime": regime, "factors": result.categories,
        "hurst": _num(last, "hurst"), "variance_ratio": _num(last, "variance_ratio"),
        "entropy": _num(last, "entropy"), "kalman_slope": _num(last, "kalman_slope"),
    }
    feature_vec = meta_features.build(raw_features)
    meta_p = meta_model.predict(raw_features)
    use_meta = meta_p is not None and settings.meta_gate_enabled and meta_model.is_active()
    p_eff = meta_p if use_meta else win_prob   # promoted meta prob replaces the primary in the EV

    ev_r = None
    if geo["direction"] != "flat" and geo["entry"] and geo["stop"] and geo["reward_risk"]:
        stop_frac = abs(geo["entry"] - geo["stop"]) / geo["entry"]
        cost_r = cost_in_r(market, symbol.upper() if is_crypto else symbol, atr_pct, stop_frac)
        rr = geo["reward_risk"]
        ev_r = round(p_eff * rr - (1.0 - p_eff) - cost_r, 4)

    # --- L6 hard filters / silence ("silence is a position") ---
    sig_symbol = symbol.upper() if is_crypto else symbol
    silence_reason = None
    if crowd_veto:
        silence_reason = "crowd_veto"
    elif settings.regime_filter_enabled and regime not in _allowed_regimes():
        silence_reason = "regime_filter"  # only trade regimes with proven positive expectancy
    elif settings.symbol_perf_gate_enabled and not learning.is_symbol_tradeable(
        sig_symbol, settings.symbol_perf_min_sample, settings.symbol_perf_window_days
    ):
        silence_reason = "symbol_filter"  # this symbol has proven negative expectancy
    elif candidate_dir != "flat" and candidate_dir not in _allowed_directions():
        silence_reason = "direction_filter"  # this direction has proven negative expectancy
    elif abs(composite) < settings.conviction_floor:
        silence_reason = "below_conviction_floor"
    elif geo["direction"] == "flat":
        silence_reason = "neutral"  # incl. a range signal with no valid fade geometry
    elif regime == "range" and not _range_reversion_ok(last):
        silence_reason = "reversion_too_slow"  # §3.3: range isn't mean-reverting fast enough to fade
    elif geo["reward_risk"] is not None and geo["reward_risk"] < _rr_floor(regime):
        silence_reason = "reward_risk_below_gate"
    elif settings.ev_gate_enabled and ev_r is not None and ev_r < settings.min_ev_r:
        silence_reason = "ev_below_gate"  # calibrated expected value doesn't clear cost
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
        "strategy": "range-fade" if geo.get("is_fade") else "trend",
        "win_prob": round(win_prob, 4),
        "meta_p": round(meta_p, 4) if meta_p is not None else None,
        "htf_trend": raw_features["htf_trend"],
        "features": feature_vec,
        "ev_r": ev_r,
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
