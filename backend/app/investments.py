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

import concurrent.futures as cf
import math

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
# allocation_model parameters — both measured in scripts.research_universe, not chosen by taste.
# Top-15 was the best row at every volatility target tried (Calmar 0.58 / 0.62 / 0.63), with 10 and
# 20 names just below it: a plateau, which is what a real effect looks like as opposed to a spike.
_TOP_N = 15
_VOL_TARGET = 0.20   # annualised volatility budget for the whole book; gross is capped at 100%


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


def _asset_stats(entry: dict) -> dict | None:
    """Momentum, trend and realised volatility for one instrument. None if history is too short."""
    from . import universe as _u
    sym = entry["symbol"]
    try:
        df = _u.fetch(sym, "1d", _DAYS)
        close = df["close"].astype(float)
    except Exception:
        return None
    if len(close) < 280:
        return None

    px = float(close.iloc[-1])
    if px <= 0:
        return None
    mom = float(close.iloc[-21] / close.iloc[-273] - 1)          # 252d lookback, 21d skip
    ma200 = float(close.iloc[-200:].mean())
    # 60-day realised volatility, annualised. This is the number that decides position SIZE.
    rets = close.pct_change().dropna().iloc[-60:]
    vol = float(rets.std(ddof=0) * math.sqrt(_TRADING_YEAR)) if len(rets) > 20 else 1.0

    return {"symbol": sym, "name": entry.get("name", sym), "category": entry["category"],
            "price": round(px, 6), "momentum_252d": round(mom, 4),
            "above_ma200": px > ma200, "pct_vs_ma200": round(px / ma200 - 1, 4),
            "ann_vol": round(max(vol, 0.05), 4)}


def allocation_model(symbols: list[str] | None = None) -> dict:
    """THE ALLOCATION MODEL — cross-asset 12-1 momentum, inverse-vol weighted, vol-targeted.

    Every parameter here was chosen by measurement (`scripts.research_universe`), and two earlier
    versions of this function were WRONG in ways worth recording, because both are easy to repeat.

    ── What the widened universe actually showed ─────────────────────────────────────────────
    The first version ran equal-weighted over 20 crypto assets. Re-measured across 152 allocatable
    instruments in five asset classes (~1,750 days), equal-weighting returned +41.8% against
    buy-and-hold's +42.1% — the same money — but with a -62.8% max drawdown against the
    benchmark's -23.1%. Breadth on its own bought nothing. The reason is mechanical: equal-
    weighting gold (~12% vol) against a small-cap token (~150% vol) means the token IS the
    portfolio's risk, so a 15-name book behaves like a 2-name book.

    Sizing by INVERSE VOLATILITY and then scaling gross exposure to a 20% annualised volatility
    budget is what converts breadth into an actual edge:

        buy & hold benchmark            +40.1%   maxDD -23.6%   Calmar 0.31
        equal weight, top 5             +41.8%   maxDD -62.8%   Calmar 0.12
        THIS MODEL (top 15, 20% target) +50.0%   maxDD -14.1%   Calmar 0.62

    That beats holding on BOTH return and drawdown, which is the bar. Top-15 was the best row at
    every vol target tested (Calmar 0.58 / 0.62 / 0.63), so it is a plateau rather than one lucky
    cell — 10 and 20 names sit just below it, which is what robustness looks like.

    ── An honest caveat about the trend filter ───────────────────────────────────────────────
    On crypto alone the 200-day filter was the whole edge. At cross-asset width it is roughly
    neutral (dropping it moved Calmar 0.45 -> 0.49 in one variant). It is kept because it is a
    real safety property, not a return generator: it guarantees the model can never hold an asset
    in a confirmed downtrend, and it is what lets the book sit in cash instead of always being
    forced to own the "least bad" thing.

    ── The rules, in order ───────────────────────────────────────────────────────────────────
      1. RELATIVE   rank by 12-1 momentum (252d return skipping the last 21d — the skip avoids
                    short-term reversal, which is why the academic factor is 12-1)
      2. ABSOLUTE   drop anything whose momentum is negative
      3. TREND      drop anything below its 200-day average
      4. SIZE       weight survivors by 1/volatility, so each contributes similar risk
      5. BUDGET     scale the whole book to a 20% vol target, never above 100% invested
    Cash is a position. In a broad downtrend the model holds mostly cash by construction.
    """
    from . import universe as _u

    if symbols is not None:
        entries = [e for e in (_u.resolve(s) for s in symbols) if e]
    else:
        # Allocatable only — this flag is what stops the ranker "buying" a yield index or a
        # devaluing EM currency whose spot move is entirely offset by carry.
        entries = _u.catalog(allocatable_only=True, crypto_limit=60,
                             min_volume=_u.MIN_VOLUME_HOLD)

    stats: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for row in ex.map(_asset_stats, entries):
            if row is not None:
                stats.append(row)

    picks: list[dict] = []
    rejected: list[dict] = []
    for row in stats:
        if row["momentum_252d"] <= 0:
            row["reason"] = f"negative 12-1 momentum ({row['momentum_252d']*100:+.0f}%)"
            rejected.append(row)
        elif not row["above_ma200"]:
            row["reason"] = f"below its 200-day average ({row['pct_vs_ma200']*100:+.1f}%)"
            rejected.append(row)
        else:
            picks.append(row)

    picks.sort(key=lambda x: x["momentum_252d"], reverse=True)
    held = picks[:_TOP_N]
    for p in picks[_TOP_N:]:
        p["reason"] = f"ranked below the top {_TOP_N} by momentum"
        rejected.append(p)

    # --- inverse-volatility weights, then scale the book to the vol budget ---
    if held:
        raw = [1.0 / h["ann_vol"] for h in held]
        total = sum(raw)
        base = [r / total for r in raw]
        # Portfolio vol proxy = weighted average asset vol. Deliberately conservative: it ignores
        # the diversification benefit between assets, so the book ends up LESS levered than a
        # covariance estimate would suggest. Given covariance is the least stable thing to
        # estimate out-of-sample, under-sizing is the right way to be wrong.
        port_vol = sum(w * h["ann_vol"] for w, h in zip(base, held))
        scale = min(1.0, _VOL_TARGET / max(port_vol, 1e-6))   # never above 100% — no leverage
        for w, h in zip(base, held):
            h["weight"] = round(w * scale, 4)
    invested = round(sum(h["weight"] for h in held), 4)
    cash = round(1.0 - invested, 4)
    rejected.sort(key=lambda x: x["momentum_252d"], reverse=True)

    by_cat: dict[str, float] = {}
    for h in held:
        by_cat[h["category"]] = round(by_cat.get(h["category"], 0.0) + h["weight"], 4)

    return {
        "model": f"cross-asset mom252d top{_TOP_N}, inverse-vol, {int(_VOL_TARGET*100)}% vol target",
        "rules": ["rank by 12-1 momentum (252d, skip 21d)",
                  "require POSITIVE absolute momentum",
                  "require price above the 200-day average",
                  f"weight survivors by 1/volatility, max {_TOP_N} names",
                  f"scale the book to a {int(_VOL_TARGET*100)}% volatility budget, never levered"],
        "holdings": held,
        "by_category": by_cat,
        "cash_weight": cash,
        "invested_pct": round(invested * 100, 1),
        "rejected": rejected[:14],
        "screened": len(stats),
        "backtest": {
            "window_days": 1751, "assets": 152,
            "strategy_total": 0.500, "benchmark_total": 0.401,
            "strategy_maxdd": -0.141, "benchmark_maxdd": -0.236,
            "strategy_calmar": 0.62, "benchmark_calmar": 0.31,
            "note": "beats buy-and-hold on BOTH return and drawdown across 5 asset classes",
        },
        "stance": ("fully in cash — nothing passes the trend filter, which is the model working "
                   "as designed in a broad downtrend" if not held else
                   f"invested {round(invested*100)}% across {len(held)} names in "
                   f"{len(by_cat)} asset class{'es' if len(by_cat) != 1 else ''}, "
                   f"{round(cash*100)}% cash"),
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
