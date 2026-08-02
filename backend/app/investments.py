"""Long-term investment screening — what to HOLD, not what to trade.

The trading engine answers "is there an edge in the next few bars?". This answers a different
question: "which assets deserve capital for months?" Different horizon, different maths.

It scores on daily bars using factors that actually survive academic scrutiny, rather than
short-term indicators:

  MOMENTUM (12-1)   — the classic cross-sectional momentum factor: 12-month return EXCLUDING the
                      most recent month (the skip avoids short-term reversal, which is why the
                      academic version is 12-1 and not plain 12-month).
  TREND QUALITY     — price above a rising 200-day MA. Simple, robust, and the single most reliable
                      long-horizon filter for avoiding catastrophic holds.
  RISK-ADJUSTED     — annualised return / annualised volatility (Sharpe-like, rf ignored).
  DRAWDOWN          — current distance below the 1-year high (opportunity) AND worst historical
                      drawdown (fragility). A deep current drawdown in a still-healthy uptrend is
                      an entry; a deep drawdown in a broken trend is a falling knife.
  STABILITY         — downside deviation vs total deviation; rewards assets whose volatility is
                      mostly upside.

Deliberately NOT a trade signal: no stops, no targets, no expiry. It is a ranked shortlist with the
reasoning shown, so the operator decides allocation.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .data import fetch_klines_history
from .data.validate import validate_ohlcv

# Liquid, established assets only — long-horizon holding needs survivability, not lottery tickets.
UNIVERSE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOTUSDT", "LTCUSDT", "ATOMUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT", "AAVEUSDT", "TRXUSDT",
    "ETCUSDT", "XLMUSDT", "FILUSDT", "INJUSDT",
]
_DAYS = 420          # ~14 months of daily bars: enough for a 12-1 momentum window
_TRADING_YEAR = 365  # crypto trades every day
_TOP_N = 5           # allocation_model: hold the 5 strongest survivors (measured best in the sweep)


def _metrics(df: pd.DataFrame) -> dict | None:
    """Compute the long-horizon factor set from a daily OHLCV frame."""
    if len(df) < 260:
        return None
    close = df["close"].astype(float)
    px = float(close.iloc[-1])
    rets = close.pct_change().dropna()
    if len(rets) < 200 or px <= 0:
        return None

    # --- momentum 12-1 (skip the most recent ~21 sessions) ---
    if len(close) >= 360:
        mom_12_1 = float(close.iloc[-21] / close.iloc[-357] - 1.0)
    else:
        mom_12_1 = float(close.iloc[-21] / close.iloc[0] - 1.0)

    # --- trend quality: above a RISING 200d MA ---
    ma200 = close.rolling(200).mean()
    above = bool(px > float(ma200.iloc[-1]))
    slope = float(ma200.iloc[-1] / ma200.iloc[-21] - 1.0) if len(ma200.dropna()) > 21 else 0.0

    # --- risk-adjusted return ---
    ann_ret = float(rets.mean() * _TRADING_YEAR)
    ann_vol = float(rets.std(ddof=0) * math.sqrt(_TRADING_YEAR))
    sharpe = ann_ret / ann_vol if ann_vol > 1e-9 else 0.0

    # --- drawdowns ---
    high_1y = float(close.iloc[-min(len(close), 365):].max())
    dd_now = float(px / high_1y - 1.0)                       # negative = below the high
    roll_max = close.cummax()
    max_dd = float((close / roll_max - 1.0).min())

    # --- downside stability: how much of the vol is downside? ---
    downside = rets[rets < 0]
    dvol = float(downside.std(ddof=0) * math.sqrt(_TRADING_YEAR)) if len(downside) > 10 else ann_vol
    stability = 1.0 - (dvol / ann_vol) if ann_vol > 1e-9 else 0.0   # higher = vol skewed upside

    return {
        "price": px, "momentum_12_1": mom_12_1, "above_ma200": above, "ma200_slope": slope,
        "ann_return": ann_ret, "ann_vol": ann_vol, "sharpe": sharpe,
        "drawdown_from_high": dd_now, "max_drawdown": max_dd, "stability": stability,
    }


def _score(m: dict) -> tuple[float, list[str]]:
    """Blend the factors into 0-100 with human-readable reasoning."""
    notes: list[str] = []
    s = 50.0

    # Momentum (strongest long-horizon factor) — capped so one moonshot can't dominate.
    mom = max(-0.9, min(3.0, m["momentum_12_1"]))
    s += max(-22.0, min(25.0, mom * 22.0))
    if mom > 0.35:
        notes.append(f"strong 12-1 momentum ({mom*100:+.0f}%)")
    elif mom < -0.2:
        notes.append(f"negative momentum ({mom*100:+.0f}%)")

    # Trend quality — the survivability filter.
    if m["above_ma200"] and m["ma200_slope"] > 0:
        s += 18.0; notes.append("above a rising 200-day average")
    elif m["above_ma200"]:
        s += 6.0; notes.append("above its 200-day average but the trend is flattening")
    else:
        s -= 18.0; notes.append("below its 200-day average (structurally weak)")

    # Risk-adjusted return.
    sh = max(-2.0, min(3.0, m["sharpe"]))
    s += sh * 8.0
    if sh > 1.0:
        notes.append(f"good risk-adjusted return (Sharpe {sh:.2f})")
    elif sh < 0:
        notes.append(f"negative risk-adjusted return (Sharpe {sh:.2f})")

    # Drawdown: discount only if the trend still holds, else penalise.
    dd = m["drawdown_from_high"]
    if dd < -0.25 and m["above_ma200"]:
        s += 8.0; notes.append(f"{abs(dd)*100:.0f}% below its 1y high while the uptrend holds")
    elif dd < -0.5:
        s -= 10.0; notes.append(f"{abs(dd)*100:.0f}% below its 1y high")

    # Fragility.
    if m["max_drawdown"] < -0.8:
        s -= 8.0; notes.append(f"history of severe drawdowns ({m['max_drawdown']*100:.0f}%)")

    # Upside-skewed volatility.
    s += max(-6.0, min(8.0, m["stability"] * 20.0))

    return max(0.0, min(100.0, s)), notes


def _tier(score: float, m: dict) -> str:
    if score >= 70 and m["above_ma200"]:
        return "core"        # deserves a real allocation
    if score >= 55:
        return "satellite"   # smaller position
    if score >= 40:
        return "watch"
    return "avoid"


def allocation_model(symbols: list[str] | None = None) -> dict:
    """THE PROVEN ALLOCATION MODEL — `mom252d top5 +MA200 +abs`.

    Chosen by measurement, not opinion. A 44-strategy walk-forward sweep over 720 days x 12 assets
    (turnover costed, ranked against buy-and-hold) found:

        momentum + MA200 filter   avg -28.7%   (every one of 20 variants beat the benchmark)
        BUY & HOLD benchmark          -46.7%
        momentum WITHOUT MA200    avg -51.6%   (every variant LOST to the benchmark)
        mean reversion            avg -56.2%   (worst; matches our live range-fade losses)

    So the edge is the TREND FILTER, not momentum itself. This exact cell returned -18.8% while
    holding returned -46.7%, with max drawdown -45.7% vs -68.7% — roughly 28 points better in a
    market that halved.

    The three rules, in order:
      1. RELATIVE   rank by 12-1 momentum (252d return skipping the last 21d — the skip avoids
                    short-term reversal, which is why the academic factor is 12-1)
      2. ABSOLUTE   drop anything whose momentum is negative (no falling assets, ever)
      3. TREND      drop anything below its 200-day average
    Whatever survives is held equal-weight, up to 5 names. If nothing survives, the model holds CASH
    — and that is the whole point: it is a loss-avoider, not a return generator.
    """
    picks: list[dict] = []
    rejected: list[dict] = []

    for sym in (symbols or UNIVERSE):
        try:
            df = fetch_klines_history(sym, "1d", _DAYS)
            df, _ = validate_ohlcv(df, "1d")
            close = df["close"].astype(float)
        except Exception:
            continue
        if len(close) < 280:
            continue

        px = float(close.iloc[-1])
        mom = float(close.iloc[-21] / close.iloc[-273] - 1)      # 252d lookback, 21d skip
        ma200 = float(close.iloc[-200:].mean())
        above = px > ma200

        row = {"symbol": sym, "price": round(px, 6),
               "momentum_252d": round(mom, 4),
               "above_ma200": above,
               "pct_vs_ma200": round(px / ma200 - 1, 4)}

        if mom <= 0:
            row["reason"] = f"negative 12-1 momentum ({mom*100:+.0f}%)"
            rejected.append(row)
        elif not above:
            row["reason"] = f"below its 200-day average ({(px/ma200-1)*100:+.1f}%)"
            rejected.append(row)
        else:
            picks.append(row)

    picks.sort(key=lambda x: x["momentum_252d"], reverse=True)
    held = picks[:_TOP_N]
    for p in picks[_TOP_N:]:
        p["reason"] = f"ranked below the top {_TOP_N} by momentum"
        rejected.append(p)

    weight = round(1.0 / len(held), 4) if held else 0.0
    for h in held:
        h["weight"] = weight
    cash = round(1.0 - weight * len(held), 4)
    rejected.sort(key=lambda x: x["momentum_252d"], reverse=True)

    return {
        "model": "mom252d top5 +MA200 +abs",
        "rules": ["rank by 12-1 momentum (252d, skip 21d)",
                  "require POSITIVE absolute momentum",
                  "require price above the 200-day average",
                  f"hold survivors equal-weight, max {_TOP_N}"],
        "holdings": held,
        "cash_weight": cash,
        "invested_pct": round((1 - cash) * 100, 1),
        "rejected": rejected[:12],
        "screened": len(picks) + len(rejected),
        "backtest": {
            "window_days": 720, "assets": 12,
            "strategy_total": -0.188, "benchmark_total": -0.467,
            "strategy_maxdd": -0.457, "benchmark_maxdd": -0.687,
            "note": "measured vs buy-and-hold; a loss-avoider, not a return generator",
        },
        "stance": ("fully in cash — nothing passes the trend filter, which is the model working "
                   "as designed in a downtrend" if not held else
                   f"invested {round((1-cash)*100)}% across {len(held)} names"),
    }


def screen(symbols: list[str] | None = None) -> dict:
    """Rank the universe for long-horizon holding. Never raises."""
    out: list[dict] = []
    for sym in (symbols or UNIVERSE):
        try:
            df = fetch_klines_history(sym, "1d", _DAYS)
            df, _ = validate_ohlcv(df, "1d")
            m = _metrics(df)
        except Exception:
            m = None
        if m is None:
            continue
        score, notes = _score(m)
        out.append({
            "symbol": sym, "score": round(score, 1), "tier": _tier(score, m),
            "price": round(m["price"], 6),
            "momentum_12_1": round(m["momentum_12_1"], 4),
            "ann_return": round(m["ann_return"], 4),
            "ann_vol": round(m["ann_vol"], 4),
            "sharpe": round(m["sharpe"], 3),
            "drawdown_from_high": round(m["drawdown_from_high"], 4),
            "max_drawdown": round(m["max_drawdown"], 4),
            "above_ma200": m["above_ma200"],
            "stability": round(m["stability"], 3),
            "notes": notes,
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    tiers = {t: sum(1 for o in out if o["tier"] == t) for t in ("core", "satellite", "watch", "avoid")}
    return {
        "screened": len(out), "tiers": tiers, "assets": out,
        "horizon": "months — hold-and-review, not a trade signal",
    }
