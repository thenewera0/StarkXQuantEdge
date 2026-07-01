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
