"""Layer 1 — Regime detection (Confluence Engine). The gate everything hangs on.

A trend signal in chop loses; a mean-reversion signal in a strong trend loses. So classify the
regime FIRST, then load the matching factor-weight profile (factors/weights.py REGIME_PROFILES).

Five regimes, rule-based (cheap, no model) from indicators we already compute:

  strong_trend : ADX > 25 and Chop < 38, price on one side of the 200EMA
  weak_trend   : ADX 18..25 (pullback entries only)
  range        : Chop > 61 and ADX < 18 (mean-reversion at edges)
  high_vol     : ATR% spike or very wide Bollinger band (cut size / stand down)
  squeeze      : Bollinger width near its multi-month low (pre-breakout, wait for expansion)
"""

from __future__ import annotations

import pandas as pd

REGIMES = ("strong_trend", "weak_trend", "range", "high_vol", "squeeze")


def detect_regime(row: pd.Series) -> str:
    close = row.get("close")
    atr = row.get("atr")
    adx = row.get("adx")
    chop = row.get("chop")
    bb_width = row.get("bb_width")
    bb_min = row.get("bb_width_min60")
    ema200 = row.get("ema200")

    atr_pct = (atr / close) if (atr and close) else 0.0

    # High volatility dominates everything.
    if atr_pct > 0.05 or (bb_width is not None and not pd.isna(bb_width) and bb_width > 0.16):
        return "high_vol"

    # Squeeze: band width compressed to near its rolling minimum.
    if (
        bb_width is not None and bb_min is not None
        and not pd.isna(bb_width) and not pd.isna(bb_min)
        and bb_width <= bb_min * 1.15
    ):
        return "squeeze"

    adx = float(adx) if (adx is not None and not pd.isna(adx)) else 0.0
    chop = float(chop) if (chop is not None and not pd.isna(chop)) else 50.0

    if adx > 25 and chop < 38:
        return "strong_trend"
    if chop > 61 and adx < 18:
        return "range"
    if 18 <= adx <= 25:
        return "weak_trend"
    # Ambiguous middle: lean on choppiness.
    return "range" if chop > 50 else "weak_trend"


def detect_macro_regime(btc_4h: pd.DataFrame, btc_1d: pd.DataFrame | None = None) -> dict:
    """3-State Macro Regime Gate using BTC 4h and 1d structure (Phase 3).

    States:
      * BULL_TREND: Close > EMA_50 > EMA_200 and Hurst > 0.52.
      * BEAR_TREND: Close < EMA_50 < EMA_200 (or Close < EMA_200) and Hurst > 0.52.
      * CHOP_RANGE: 0.45 <= Hurst <= 0.55 (or mixed structure).
    """
    if btc_4h is None or len(btc_4h) < 50:
        return {"state": "CHOP_RANGE", "hurst": 0.50, "close": None, "ema50": None, "ema200": None}

    from .indicators.engine import compute_indicators, hurst_exponent

    # Compute indicators on 4h BTC
    ind_4h = btc_4h if "ema50" in btc_4h.columns else compute_indicators(btc_4h)
    last_4h = ind_4h.iloc[-1]
    c_4h = float(last_4h.get("close") or 0.0)
    e50_4h = float(last_4h.get("ema50") or c_4h)
    e200_4h = float(last_4h.get("ema200") or e50_4h)
    h_4h = float(last_4h.get("hurst") if last_4h.get("hurst") is not None and not pd.isna(last_4h.get("hurst")) else 0.50)

    # If 1d provided, blend or confirm
    c_1d = e50_1d = e200_1d = h_1d = None
    if btc_1d is not None and len(btc_1d) >= 50:
        ind_1d = btc_1d if "ema50" in btc_1d.columns else compute_indicators(btc_1d)
        last_1d = ind_1d.iloc[-1]
        c_1d = float(last_1d.get("close") or 0.0)
        e50_1d = float(last_1d.get("ema50") or c_1d)
        e200_1d = float(last_1d.get("ema200") or e50_1d)
        h_1d = float(last_1d.get("hurst") if last_1d.get("hurst") is not None and not pd.isna(last_1d.get("hurst")) else 0.50)

    # Effective values
    c = c_4h
    e50 = e50_4h
    e200 = e200_4h
    hurst = (h_4h + (h_1d if h_1d is not None else h_4h)) / 2.0

    # Classification
    is_bull_structure = (c > e50 > e200)
    is_bear_structure = (c < e50 < e200) or (c < e200 and e50 < e200)

    if 0.45 <= hurst <= 0.55:
        state = "CHOP_RANGE"
    elif hurst > 0.52 and is_bull_structure:
        state = "BULL_TREND"
    elif hurst > 0.52 and is_bear_structure:
        state = "BEAR_TREND"
    else:
        state = "CHOP_RANGE"

    return {
        "state": state,
        "hurst": round(hurst, 4),
        "close": round(c, 2),
        "ema50": round(e50, 2),
        "ema200": round(e200, 2),
        "is_bull": state == "BULL_TREND",
        "is_bear": state == "BEAR_TREND",
        "is_chop": state == "CHOP_RANGE",
    }


_macro_cache: tuple[float, dict] | None = None

def get_macro_regime() -> dict:
    """Cached BTC Macro Regime Gate (60s TTL)."""
    global _macro_cache
    import time
    now = time.time()
    if _macro_cache and now - _macro_cache[0] < 60.0:
        return _macro_cache[1]
    try:
        from .data import fetch_klines
        btc_4h = fetch_klines("BTCUSDT", "4h", 120)
        res = detect_macro_regime(btc_4h)
        _macro_cache = (now, res)
        return res
    except Exception:
        fallback = {"state": "CHOP_RANGE", "hurst": 0.50, "is_bull": False, "is_bear": False, "is_chop": True}
        return fallback
