"""STRATEGY RESEARCH LAB — find what works by measuring, not by trading blind.

Run: python -m scripts.research_lab

The problem this solves: "there are millions of techniques, how do we know which one works for us?"
You cannot answer that with live trades — at a few trades a week it would take years, and every
wrong guess costs money. You answer it by replaying many strategies over the SAME history with the
SAME costs and ranking them against a benchmark you must beat: buy-and-hold.

Everything here is walk-forward honest: decisions use only closed bars, fills happen next bar, and
every strategy pays the same realistic cost model. A strategy only earns attention if it beats
buy-and-hold on return AND drawdown — otherwise holding is strictly better.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT", "UNIUSDT"]
DAYS = 720          # ~2 years of daily bars
REBAL = 5           # rebalance every 5 days (weekly) — keeps turnover/cost sane


def load() -> dict[str, pd.DataFrame]:
    out = {}
    for s in UNIVERSE:
        try:
            df = fetch_klines_history(s, "1d", DAYS)
            df, _ = validate_ohlcv(df, "1d")
            if len(df) > 250:
                out[s] = df
        except Exception:
            pass
    return out


def metrics(equity: pd.Series, name: str) -> dict:
    """Return the numbers that actually decide whether a strategy is worth running."""
    rets = equity.pct_change().dropna()
    if len(rets) < 10:
        return {"name": name, "total": 0, "cagr": 0, "vol": 0, "sharpe": 0, "maxdd": 0, "calmar": 0}
    total = equity.iloc[-1] / equity.iloc[0] - 1
    years = len(rets) / 365
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    vol = rets.std(ddof=0) * np.sqrt(365)
    sharpe = (rets.mean() * 365) / vol if vol > 1e-9 else 0
    dd = (equity / equity.cummax() - 1).min()
    return {"name": name, "total": total, "cagr": cagr, "vol": vol,
            "sharpe": sharpe, "maxdd": dd, "calmar": cagr / abs(dd) if dd < 0 else 0}


def run_weights(data: dict[str, pd.DataFrame], weight_fn, name: str, cost_per_turn: float = 0.002) -> dict:
    """Backtest any strategy expressible as 'what weight in each asset each day'.

    weight_fn(history_slice) -> {symbol: weight}. History is strictly past bars (no lookahead).
    Costs are charged on turnover, so churn is penalised exactly as in real life.
    """
    idx = sorted(set().union(*[set(d.index.date) for d in data.values()]))
    closes = pd.DataFrame({s: d["close"] for s, d in data.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()

    equity = [1.0]
    dates = list(closes.index)
    prev_w: dict[str, float] = {}
    start = 220

    for i in range(start, len(dates) - 1):
        hist = closes.iloc[: i + 1]                 # closed bars only
        try:
            w = weight_fn(hist) or {}
        except Exception:
            w = {}
        # cost on turnover
        turn = sum(abs(w.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(w) | set(prev_w))
        cost = turn * cost_per_turn
        # next-day return (fill at next bar)
        r = 0.0
        for s, wt in w.items():
            if wt == 0:
                continue
            p0, p1 = closes[s].iloc[i], closes[s].iloc[i + 1]
            if p0 and p1 and not np.isnan(p0) and not np.isnan(p1):
                r += wt * (p1 / p0 - 1)
        equity.append(equity[-1] * (1 + r - cost))
        prev_w = w

    eq = pd.Series(equity, index=dates[start: start + len(equity)])
    return metrics(eq, name)


# ---------------- strategies ----------------

def s_buyhold(hist):
    """BENCHMARK: equal-weight everything, always. The bar every strategy must clear."""
    syms = [s for s in hist.columns if not np.isnan(hist[s].iloc[-1])]
    return {s: 1.0 / len(syms) for s in syms} if syms else {}


def s_ma200(hist):
    """Hold only assets above their 200-day average; cash otherwise (classic trend filter)."""
    ok = []
    for s in hist.columns:
        c = hist[s].dropna()
        if len(c) > 200 and c.iloc[-1] > c.iloc[-200:].mean():
            ok.append(s)
    return {s: 1.0 / len(ok) for s in ok} if ok else {}


def _mom12_1(c: pd.Series) -> float:
    if len(c) < 250:
        return -9
    return float(c.iloc[-21] / c.iloc[-250] - 1)


def s_momentum_top3(hist):
    """Cross-sectional momentum: hold the 3 strongest 12-1 performers."""
    sc = {s: _mom12_1(hist[s].dropna()) for s in hist.columns}
    sc = {k: v for k, v in sc.items() if v > -9}
    top = sorted(sc, key=sc.get, reverse=True)[:3]
    return {s: 1.0 / len(top) for s in top} if top else {}


def s_dual_momentum(hist):
    """Dual momentum: strongest 3, but ONLY those with positive absolute momentum (else cash).

    This is the version with real academic support — relative strength picks the winners,
    absolute momentum keeps you out of bear markets entirely.
    """
    sc = {s: _mom12_1(hist[s].dropna()) for s in hist.columns}
    sc = {k: v for k, v in sc.items() if v > -9}
    top = [s for s in sorted(sc, key=sc.get, reverse=True)[:3] if sc[s] > 0]
    return {s: 1.0 / len(top) for s in top} if top else {}


def s_dual_mom_trend(hist):
    """Dual momentum AND above the 200-day average — both filters must agree."""
    sc = {s: _mom12_1(hist[s].dropna()) for s in hist.columns}
    sc = {k: v for k, v in sc.items() if v > -9}
    cand = []
    for s in sorted(sc, key=sc.get, reverse=True):
        c = hist[s].dropna()
        if sc[s] > 0 and len(c) > 200 and c.iloc[-1] > c.iloc[-200:].mean():
            cand.append(s)
        if len(cand) == 3:
            break
    return {s: 1.0 / len(cand) for s in cand} if cand else {}


def s_vol_target(hist):
    """Dual momentum + inverse-volatility weighting (risk parity across the picks)."""
    sc = {s: _mom12_1(hist[s].dropna()) for s in hist.columns}
    sc = {k: v for k, v in sc.items() if v > -9}
    top = [s for s in sorted(sc, key=sc.get, reverse=True)[:3] if sc[s] > 0]
    if not top:
        return {}
    inv = {}
    for s in top:
        r = hist[s].pct_change().dropna().iloc[-60:]
        v = float(r.std(ddof=0)) or 0.02
        inv[s] = 1.0 / max(v, 0.005)
    tot = sum(inv.values())
    return {s: v / tot for s, v in inv.items()}


def s_btc_only(hist):
    """Sanity anchor: just hold BTC."""
    return {"BTCUSDT": 1.0} if "BTCUSDT" in hist.columns else {}


def main() -> None:
    print("loading daily history...")
    data = load()
    print(f"  {len(data)} assets, {DAYS} days\n")

    strategies = [
        (s_buyhold, "BUY & HOLD (benchmark)"),
        (s_btc_only, "BTC only"),
        (s_ma200, "200d trend filter"),
        (s_momentum_top3, "momentum top-3"),
        (s_dual_momentum, "DUAL momentum (abs+rel)"),
        (s_dual_mom_trend, "dual momentum + 200d"),
        (s_vol_target, "dual momentum + vol-weight"),
    ]
    results = []
    for fn, name in strategies:
        r = run_weights(data, fn, name)
        results.append(r)
        print(f"  tested: {name}")

    bench = next(r for r in results if r["name"].startswith("BUY & HOLD"))
    print("\n" + "=" * 92)
    print(f"{'strategy':30} {'total':>9} {'CAGR':>8} {'vol':>7} {'Sharpe':>7} {'maxDD':>8} {'Calmar':>7}  verdict")
    print("=" * 92)
    for r in sorted(results, key=lambda x: -x["sharpe"]):
        beats = r["total"] > bench["total"] and r["maxdd"] > bench["maxdd"]
        v = "BEATS HOLD" if beats and not r["name"].startswith("BUY") else ("benchmark" if r["name"].startswith("BUY") else "")
        print(f"{r['name']:30} {r['total']*100:+8.1f}% {r['cagr']*100:+7.1f}% "
              f"{r['vol']*100:6.1f}% {r['sharpe']:7.2f} {r['maxdd']*100:+7.1f}% {r['calmar']:7.2f}  {v}")
    print("=" * 92)
    print("A strategy is only worth running if it beats buy-and-hold on BOTH return and drawdown.")
    print("Anything else means holding was the better use of the same capital.")


if __name__ == "__main__":
    main()
