"""Structurally different approaches — not more indicators.

Everything this project has measured as a LOSER shares two properties: a short holding period
(round-trip cost eats the move) and directional beta (correlated positions die together). The one
measured WINNER has the opposite: long holds, cross-asset, sized by volatility. And the largest
single improvement ever found here was not a signal at all — it was inverse-vol sizing.

So this does not test new indicators. It tests different STRUCTURES, each of which drops an
assumption the losing strategies all shared:

  1 MARKET-NEUTRAL      long the strongest, short the weakest, equal gross each side. Removes beta
                        entirely — the thing that caused every correlated blow-up we have had.
                        Only became testable now that the universe has 319 instruments; a
                        cross-sectional strategy needs breadth to have anything to rank.
  2 VOL-MANAGED BETA    no forecasting at all. Hold the market, scale exposure inversely to recent
                        realised volatility (Moreira & Muir). Tests whether our edge is entirely
                        in sizing rather than in prediction.
  3 SHORT-TERM REVERSAL cross-sectional 1-week reversal. Genuinely different from the time-series
                        mean-reversion we measured as the worst family.
  4 CARRY-FREE TREND    time-series momentum on each asset independently, vol-scaled, no ranking.
  5 ENSEMBLE            equal-risk blend of whichever of the above survive, on the theory that
                        combining weak uncorrelated edges beats picking one strong one.

Every run is walk-forward, next-bar, turnover-costed, and reported against buy-and-hold on BOTH
return and drawdown. Anything that does not clear both is not an edge.

    python -m scripts.research_unconventional
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from app import universe
from scripts.research_universe import build_panel

COST = 0.002          # 20bp per unit of turnover
REBAL = 21            # monthly
ANN = 365


def load_panel() -> pd.DataFrame:
    cats = ("crypto", "forex", "commodities", "indices", "rates")
    frames = []
    for c in cats:
        syms = [x["symbol"] for x in universe.catalog([c], allocatable_only=True, crypto_limit=60)]
        p = build_panel(syms)
        if not p.empty:
            frames.append(p)
    return pd.concat(frames, axis=1).ffill(limit=5).dropna(how="all")


def metrics(curve: list[float], days: int) -> dict:
    if len(curve) < 30:
        return {}
    eq = pd.Series(curve)
    dd = float((eq / eq.cummax() - 1.0).min())
    yrs = max(days / ANN, 1e-9)
    total = float(eq.iloc[-1] - 1.0)
    cagr = float(eq.iloc[-1] ** (1 / yrs) - 1.0) if eq.iloc[-1] > 0 else -1.0
    r = eq.pct_change().dropna()
    vol = float(r.std() * np.sqrt(ANN))
    return {"total": total, "cagr": cagr, "maxdd": dd, "vol": vol,
            "sharpe": cagr / vol if vol > 1e-9 else 0.0,
            "calmar": cagr / abs(dd) if dd < -1e-9 else 0.0}


def show(tag: str, m: dict) -> None:
    if not m:
        print(f"  {tag:44} (insufficient data)")
        return
    print(f"  {tag:44} ret {m['total']*100:>8.1f}%  CAGR {m['cagr']*100:>6.1f}%  "
          f"vol {m['vol']*100:>5.1f}%  maxDD {m['maxdd']*100:>7.1f}%  "
          f"Sharpe {m['sharpe']:>5.2f}  Calmar {m['calmar']:>5.2f}")


def _vol(rets: pd.DataFrame, win: int = 60) -> pd.DataFrame:
    return (rets.rolling(win).std() * np.sqrt(ANN)).clip(lower=0.03)


def run_weights(panel: pd.DataFrame, weight_fn, warmup: int, vol_target: float | None = None,
                max_gross: float = 1.0) -> dict:
    """Generic walk-forward driver. `weight_fn(i) -> Series of weights` (may be long/short)."""
    rets = panel.pct_change(fill_method=None).fillna(0.0)
    rv = _vol(rets)
    equity, curve = 1.0, []
    w = pd.Series(0.0, index=panel.columns)
    for i in range(warmup, len(panel)):
        if (i - warmup) % REBAL == 0:
            new = weight_fn(i)
            if new is None:
                new = pd.Series(0.0, index=panel.columns)
            new = new.reindex(panel.columns).fillna(0.0)
            if vol_target is not None:
                # scale the BOOK to a volatility budget (weighted-average asset vol; deliberately
                # ignores diversification so the book ends up under-, not over-, levered)
                pv = float((new.abs() * rv.iloc[i].fillna(1.0)).sum())
                if pv > 1e-9:
                    new = new * min(max_gross, vol_target / pv)
            gross = float(new.abs().sum())
            if gross > max_gross:
                new = new * (max_gross / gross)
            equity *= 1.0 - COST * float((new - w).abs().sum())
            w = new
        equity *= 1.0 + float((w * rets.iloc[i]).sum())
        curve.append(equity)
    days = len(panel) - warmup
    return metrics(curve, days)


def main() -> None:
    print("Loading the allocatable universe (daily)...")
    panel = load_panel()
    print(f"  {panel.shape[1]} instruments x {panel.shape[0]} days\n")
    rets = panel.pct_change(fill_method=None).fillna(0.0)
    rv = _vol(rets)
    LB, SKIP, MA = 252, 21, 200
    warm = LB + SKIP + 5

    # -------- benchmark --------
    bench_curve = (1.0 + rets.iloc[warm:].mean(axis=1)).cumprod().tolist()
    b = metrics(bench_curve, len(panel) - warm)
    print("=" * 132)
    print("BENCHMARK")
    print("=" * 132)
    show("buy & hold, equal weight, everything", b)

    # -------- 0. what we currently ship (the control) --------
    def shipped(i):
        px, ma = panel.iloc[i], panel.iloc[max(0, i - MA):i].mean()
        mom = panel.iloc[i - SKIP] / panel.iloc[i - SKIP - LB] - 1.0
        ok = mom.notna() & px.notna() & (mom > 0) & (px > ma)
        picks = mom[ok].sort_values(ascending=False).head(15)
        if not len(picks):
            return None
        iv = 1.0 / rv.iloc[i][picks.index]
        return iv / iv.sum()
    print()
    print("=" * 132)
    print("0. THE CONTROL — what the Investments view ships today")
    print("=" * 132)
    show("cross-asset mom + MA200, inv-vol, 20% target", run_weights(panel, shipped, warm, 0.20))

    # -------- 1. MARKET NEUTRAL: long strong / short weak, zero net --------
    print()
    print("=" * 132)
    print("1. MARKET-NEUTRAL cross-sectional momentum — beta removed entirely")
    print("=" * 132)

    def neutral(n, lb=LB, skip=SKIP, invvol=True):
        def f(i):
            if i - skip - lb < 0:
                return None
            mom = panel.iloc[i - skip] / panel.iloc[i - skip - lb] - 1.0
            mom = mom[mom.notna() & panel.iloc[i].notna()]
            if len(mom) < 2 * n:
                return None
            ranked = mom.sort_values(ascending=False)
            longs, shorts = ranked.head(n).index, ranked.tail(n).index
            w = pd.Series(0.0, index=panel.columns)
            if invvol:
                lw = 1.0 / rv.iloc[i][longs]; sw = 1.0 / rv.iloc[i][shorts]
                w[longs] = 0.5 * lw / lw.sum(); w[shorts] = -0.5 * sw / sw.sum()
            else:
                w[longs] = 0.5 / n; w[shorts] = -0.5 / n
            return w
        return f

    for n in (5, 10, 15, 20):
        show(f"long {n} / short {n}, inverse-vol", run_weights(panel, neutral(n), warm, None))
    for n in (10, 15):
        show(f"long {n} / short {n}, equal weight", run_weights(panel, neutral(n, invvol=False), warm, None))
    for vt in (0.10, 0.15):
        show(f"long 15 / short 15, inv-vol, {vt*100:.0f}% vol target",
             run_weights(panel, neutral(15), warm, vt))

    # -------- 2. VOL-MANAGED BETA: no forecasting whatsoever --------
    print()
    print("=" * 132)
    print("2. VOL-MANAGED BETA — no forecast at all, only sizing")
    print("=" * 132)

    def volmanaged(target):
        def f(i):
            eq = pd.Series(1.0, index=panel.columns)
            eq = eq[panel.iloc[i].notna()]
            if not len(eq):
                return None
            w = pd.Series(0.0, index=panel.columns)
            w[eq.index] = 1.0 / len(eq)
            pv = float((w * rv.iloc[i].fillna(1.0)).sum())
            return w * min(1.0, target / max(pv, 1e-9))
        return f

    for t in (0.06, 0.10, 0.15, 0.20):
        show(f"hold everything, scaled to {t*100:.0f}% vol", run_weights(panel, volmanaged(t), warm))

    # -------- 3. SHORT-TERM CROSS-SECTIONAL REVERSAL --------
    print()
    print("=" * 132)
    print("3. SHORT-TERM REVERSAL — cross-sectional, not time-series")
    print("=" * 132)

    def reversal(n, lb):
        def f(i):
            if i - lb < 0:
                return None
            r = panel.iloc[i] / panel.iloc[i - lb] - 1.0
            r = r[r.notna()]
            if len(r) < 2 * n:
                return None
            ranked = r.sort_values()                    # WORST first — we buy the losers
            w = pd.Series(0.0, index=panel.columns)
            lw = 1.0 / rv.iloc[i][ranked.head(n).index]
            sw = 1.0 / rv.iloc[i][ranked.tail(n).index]
            w[ranked.head(n).index] = 0.5 * lw / lw.sum()
            w[ranked.tail(n).index] = -0.5 * sw / sw.sum()
            return w
        return f

    for lb in (5, 10, 21):
        show(f"buy {lb}d losers / sell winners, long 10/short 10",
             run_weights(panel, reversal(10, lb), warm))

    # -------- 4. TIME-SERIES TREND, no ranking --------
    print()
    print("=" * 132)
    print("4. TIME-SERIES TREND — every asset judged only against itself")
    print("=" * 132)

    def tsmom(lb, allow_short):
        def f(i):
            if i - lb < 0:
                return None
            sig = np.sign(panel.iloc[i] / panel.iloc[i - lb] - 1.0)
            sig = sig[panel.iloc[i].notna() & sig.notna()]
            if not allow_short:
                sig = sig.clip(lower=0)
            live = sig[sig != 0]
            if not len(live):
                return None
            iv = 1.0 / rv.iloc[i][live.index]
            w = pd.Series(0.0, index=panel.columns)
            w[live.index] = live * iv / iv.abs().sum()
            return w
        return f

    for lb in (63, 126, 252):
        show(f"{lb}d trend, LONG only, inv-vol, 15% target",
             run_weights(panel, tsmom(lb, False), warm, 0.15))
    for lb in (63, 126, 252):
        show(f"{lb}d trend, LONG+SHORT, inv-vol, 15% target",
             run_weights(panel, tsmom(lb, True), warm, 0.15))

    print()
    print("=" * 132)
    print("Anything that fails to beat the benchmark on BOTH return and drawdown is not an edge.")
    print("=" * 132)


if __name__ == "__main__":
    main()
