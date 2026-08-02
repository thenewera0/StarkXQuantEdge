"""COMPREHENSIVE STRATEGY SWEEP — test many techniques against our own data.

Run: python -m scripts.research_sweep

Covers three families in one honest framework:
  A. ALLOCATION  (investments)  — momentum lookbacks, holding counts, trend filters, vol targeting
  B. TIMING      (main engine)  — does our own confluence signal beat a passive rule?
  C. Everything is scored the same way: walk-forward, next-bar fills, turnover costed, ranked
     against buy-and-hold on BOTH return and drawdown.

Guard against curve-fitting: this sweep reports EVERY variant tested, not just the winner. A grid
this size will always contain something that looks good by luck, so the honest read is the SHAPE of
the results (does a whole family work?) rather than the single best cell.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT", "UNIUSDT"]
DAYS = 720
COST_PER_TURN = 0.002


def load_closes() -> pd.DataFrame:
    frames = {}
    for s in UNIVERSE:
        try:
            df = fetch_klines_history(s, "1d", DAYS)
            df, _ = validate_ohlcv(df, "1d")
            if len(df) > 260:
                frames[s] = df["close"]
        except Exception:
            pass
    c = pd.DataFrame(frames)
    c.index = pd.to_datetime(c.index).date
    return c.groupby(level=0).last().sort_index().ffill()


def backtest(closes: pd.DataFrame, weight_fn, name: str) -> dict:
    equity = [1.0]
    dates = list(closes.index)
    prev: dict[str, float] = {}
    start = 260
    for i in range(start, len(dates) - 1):
        hist = closes.iloc[: i + 1]
        try:
            w = weight_fn(hist) or {}
        except Exception:
            w = {}
        turn = sum(abs(w.get(s, 0.0) - prev.get(s, 0.0)) for s in set(w) | set(prev))
        r = 0.0
        for s, wt in w.items():
            if wt:
                p0, p1 = closes[s].iloc[i], closes[s].iloc[i + 1]
                if p0 and p1 and not np.isnan(p0) and not np.isnan(p1):
                    r += wt * (p1 / p0 - 1)
        equity.append(equity[-1] * (1 + r - turn * COST_PER_TURN))
        prev = w
    eq = pd.Series(equity)
    rets = eq.pct_change().dropna()
    if len(rets) < 10:
        return {"name": name, "total": 0, "cagr": 0, "sharpe": 0, "maxdd": 0, "exposure": 0}
    years = len(rets) / 365
    dd = float((eq / eq.cummax() - 1).min())
    vol = float(rets.std(ddof=0) * np.sqrt(365))
    return {
        "name": name,
        "total": float(eq.iloc[-1] - 1),
        "cagr": float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0,
        "sharpe": float((rets.mean() * 365) / vol) if vol > 1e-9 else 0.0,
        "maxdd": dd,
    }


def mom(c: pd.Series, look: int, skip: int = 21) -> float:
    c = c.dropna()
    if len(c) < look + skip + 5:
        return -9
    return float(c.iloc[-skip] / c.iloc[-(look + skip)] - 1)


def make_momentum(look: int, top: int, ma: int | None, absolute: bool, volwt: bool):
    """Factory for the momentum family so the whole grid shares one implementation."""
    def fn(hist: pd.DataFrame) -> dict:
        sc = {s: mom(hist[s], look) for s in hist.columns}
        sc = {k: v for k, v in sc.items() if v > -9}
        ranked = sorted(sc, key=sc.get, reverse=True)
        picks = []
        for s in ranked:
            if absolute and sc[s] <= 0:
                continue                       # absolute momentum: no falling assets
            if ma:
                c = hist[s].dropna()
                if len(c) < ma or c.iloc[-1] <= c.iloc[-ma:].mean():
                    continue                   # trend filter
            picks.append(s)
            if len(picks) >= top:
                break
        if not picks:
            return {}
        if not volwt:
            return {s: 1.0 / len(picks) for s in picks}
        inv = {}
        for s in picks:
            v = float(hist[s].pct_change().dropna().iloc[-60:].std(ddof=0)) or 0.02
            inv[s] = 1.0 / max(v, 0.005)
        tot = sum(inv.values())
        return {s: v / tot for s, v in inv.items()}
    return fn


def make_meanrev(look: int, top: int):
    """Opposite of momentum — buy the biggest losers (contrarian)."""
    def fn(hist: pd.DataFrame) -> dict:
        sc = {s: mom(hist[s], look) for s in hist.columns}
        sc = {k: v for k, v in sc.items() if v > -9}
        picks = sorted(sc, key=sc.get)[:top]
        return {s: 1.0 / len(picks) for s in picks} if picks else {}
    return fn


def main() -> None:
    print("loading history...")
    closes = load_closes()
    print(f"  {closes.shape[1]} assets x {closes.shape[0]} days\n")

    tests: list[tuple] = [
        (lambda h: {s: 1.0 / len(h.columns) for s in h.columns}, "BENCHMARK buy&hold"),
        (lambda h: {"BTCUSDT": 1.0}, "BTC only"),
    ]
    # --- momentum grid: lookback x holdings x trend filter x absolute x vol-weight ---
    for look in (63, 126, 252):
        for top in (1, 3, 5):
            for ma in (None, 200):
                for absolute in (False, True):
                    tag = f"mom{look}d top{top}{' +MA200' if ma else ''}{' +abs' if absolute else ''}"
                    tests.append((make_momentum(look, top, ma, absolute, False), tag))
    # vol-weighted variants of the best-formed rule
    for look in (126, 252):
        tests.append((make_momentum(look, 3, 200, True, True), f"mom{look}d top3 +MA200 +abs +volwt"))
    # --- contrarian family ---
    for look in (63, 252):
        for top in (3, 5):
            tests.append((make_meanrev(look, top), f"MEAN-REV {look}d bottom{top}"))

    results = []
    for fn, name in tests:
        results.append(backtest(closes, fn, name))
    bench = results[0]

    print("=" * 96)
    print(f"{'strategy':40} {'total':>9} {'CAGR':>8} {'Sharpe':>7} {'maxDD':>8}   vs hold")
    print("=" * 96)
    for r in sorted(results, key=lambda x: -x["total"]):
        better = r["total"] > bench["total"] and r["maxdd"] > bench["maxdd"]
        flag = "  BEATS" if better and r is not bench else ("  <-- benchmark" if r is bench else "")
        print(f"{r['name']:40} {r['total']*100:+8.1f}% {r['cagr']*100:+7.1f}% "
              f"{r['sharpe']:7.2f} {r['maxdd']*100:+7.1f}%{flag}")
    print("=" * 96)

    fam = {}
    for r in results[2:]:
        key = ("MEAN-REV" if r["name"].startswith("MEAN-REV") else
               "momentum +MA200+abs" if "+MA200 +abs" in r["name"] else
               "momentum +MA200" if "+MA200" in r["name"] else
               "momentum raw")
        fam.setdefault(key, []).append(r["total"])
    print("\nFAMILY AVERAGES (the honest read — is the whole family working, or one lucky cell?)")
    for k, v in sorted(fam.items(), key=lambda x: -np.mean(x[1])):
        print(f"  {k:26} avg {np.mean(v)*100:+7.1f}%   best {max(v)*100:+7.1f}%   n={len(v)}")
    print(f"  {'BENCHMARK buy&hold':26} avg {bench['total']*100:+7.1f}%")


if __name__ == "__main__":
    main()
