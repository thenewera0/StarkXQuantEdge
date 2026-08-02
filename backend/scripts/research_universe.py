"""Does BREADTH actually improve the one model with measured edge?

The allocation model (`mom252d top5 +MA200 +abs`) was chosen by a 44-strategy sweep run over 12
crypto assets. Crypto majors are ~0.8 correlated, so that test could never show what a
trend-follower is actually for: picking whichever asset class happens to be trending while the
others are not.

This runs the IDENTICAL rules over progressively wider universes and reports the difference. Same
walk-forward, same monthly rebalance, same turnover cost, same buy-and-hold benchmark. If breadth
does not help, this prints that and we do not ship it.

    python -m scripts.research_universe
"""

from __future__ import annotations

import concurrent.futures as cf

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

from app import universe

COST = 0.002          # 20bp per unit of turnover — spread + fees, charged on every weight change
LOOKBACK = 252        # 12-1 momentum: 252d return ...
SKIP = 21             # ... skipping the most recent 21d (short-term reversal)
MA = 200              # trend filter
TOP_N = 5
REBAL = 21            # rebalance monthly


def load(sym: str, bars: int = 1400) -> tuple[str, pd.Series | None]:
    try:
        df = universe.fetch(sym, "1d", bars)
        close = df["close"].astype(float)
        close.index = pd.to_datetime(close.index).tz_convert("UTC").normalize()
        close = close[~close.index.duplicated(keep="last")]
        return sym, close if len(close) >= LOOKBACK + SKIP + 40 else None
    except Exception:
        return sym, None


def build_panel(symbols: list[str]) -> pd.DataFrame:
    """Aligned daily close panel. Forward-fills session gaps so a futures holiday is not a NaN."""
    series: dict[str, pd.Series] = {}
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for sym, s in ex.map(load, symbols):
            if s is not None:
                series[sym] = s
    if not series:
        return pd.DataFrame()
    panel = pd.DataFrame(series).sort_index()
    return panel.ffill(limit=5).dropna(how="all")


def run(panel: pd.DataFrame, use_ma: bool = True, use_abs: bool = True, top_n: int = TOP_N) -> dict:
    """Walk the panel forward, rebalancing monthly. Returns equity-curve metrics."""
    need = LOOKBACK + SKIP + 5
    if len(panel) < need + REBAL:
        return {}
    rets = panel.pct_change(fill_method=None).fillna(0.0)
    ma = panel.rolling(MA, min_periods=int(MA * 0.8)).mean()

    equity, curve = 1.0, []
    weights = pd.Series(0.0, index=panel.columns)
    turnover_total = 0.0

    for i in range(need, len(panel)):
        if (i - need) % REBAL == 0:
            px = panel.iloc[i]
            mom = panel.iloc[i - SKIP] / panel.iloc[i - SKIP - LOOKBACK] - 1.0
            ok = mom.notna() & px.notna()
            if use_abs:
                ok &= mom > 0
            if use_ma:
                ok &= px > ma.iloc[i]
            picks = mom[ok].sort_values(ascending=False).head(top_n)
            new = pd.Series(0.0, index=panel.columns)
            if len(picks):
                new[picks.index] = 1.0 / len(picks)
            turn = float((new - weights).abs().sum())
            turnover_total += turn
            equity *= (1.0 - COST * turn)      # pay the cost at the rebalance, on the way in
            weights = new
        # next-bar return, so the decision never sees the bar it trades on
        equity *= 1.0 + float((weights * rets.iloc[i]).sum())
        curve.append(equity)

    eq = pd.Series(curve)
    dd = float((eq / eq.cummax() - 1.0).min())
    dr = eq.pct_change().dropna()
    vol = float(dr.std() * np.sqrt(365))
    total = float(eq.iloc[-1] - 1.0)
    years = len(eq) / 365
    cagr = float(eq.iloc[-1] ** (1 / years) - 1.0) if years > 0 else 0.0
    return {"total": total, "cagr": cagr, "maxdd": dd, "vol": vol,
            "sharpe": (cagr / vol) if vol > 1e-9 else 0.0,
            "calmar": (cagr / abs(dd)) if dd < -1e-9 else 0.0,
            "days": len(eq), "turnover": turnover_total}


def benchmark(panel: pd.DataFrame) -> dict:
    """Equal-weight buy-and-hold of the same panel — the only benchmark that matters."""
    need = LOOKBACK + SKIP + 5
    rets = panel.pct_change(fill_method=None).fillna(0.0).iloc[need:]
    eq = (1.0 + rets.mean(axis=1)).cumprod()
    dd = float((eq / eq.cummax() - 1.0).min())
    years = len(eq) / 365
    return {"total": float(eq.iloc[-1] - 1.0), "maxdd": dd,
            "cagr": float(eq.iloc[-1] ** (1 / years) - 1.0) if years > 0 else 0.0}


def line(tag: str, r: dict, b: dict) -> str:
    if not r:
        return f"{tag:34} (insufficient history)"
    edge = (r["total"] - b["total"]) * 100
    return (f"{tag:34} ret {r['total']*100:>8.1f}%  CAGR {r['cagr']*100:>7.1f}%  "
            f"maxDD {r['maxdd']*100:>7.1f}%  Calmar {r['calmar']:>5.2f}  "
            f"vs bench {edge:>+7.1f}pts")


def main() -> None:
    # allocatable_only is not optional here. Without it the ranker "buys" yield indices and
    # devaluing EM currencies, which is how the first run of this script produced a fake +310%.
    def syms(cat, **kw):
        return [c["symbol"] for c in universe.catalog([cat], allocatable_only=True, **kw)]
    cats = {
        "crypto": syms("crypto", crypto_limit=60),
        "forex": syms("forex"),
        "commodities": syms("commodities"),
        "indices": syms("indices"),
        "rates": syms("rates"),
    }
    print("Loading daily history for every asset class (this takes a minute)...")
    panels = {k: build_panel(v) for k, v in cats.items()}
    for k, p in panels.items():
        print(f"  {k:12} {p.shape[1]:>3} instruments  x {p.shape[0]:>5} days")

    print("\n" + "=" * 104)
    print("1. THE SAME MODEL, ONE ASSET CLASS AT A TIME")
    print("=" * 104)
    for k, p in panels.items():
        if p.empty or p.shape[1] < 3:
            continue
        b = benchmark(p)
        print(line(f"{k} only", run(p), b))
        print(f"{'  (buy & hold benchmark)':34} ret {b['total']*100:>8.1f}%  "
              f"CAGR {b['cagr']*100:>7.1f}%  maxDD {b['maxdd']*100:>7.1f}%")

    # Combined panel: the whole point of breadth.
    print("\n" + "=" * 104)
    print("2. CROSS-ASSET — the model choosing freely across every class")
    print("=" * 104)
    combos = {
        "crypto only": ["crypto"],
        "crypto + forex": ["crypto", "forex"],
        "crypto + commodities": ["crypto", "commodities"],
        "crypto + comm + rates": ["crypto", "commodities", "rates"],
        "EVERYTHING": ["crypto", "forex", "commodities", "indices", "rates"],
    }
    results = {}
    for tag, keys in combos.items():
        merged = pd.concat([panels[k] for k in keys if not panels[k].empty], axis=1)
        merged = merged.ffill(limit=5).dropna(how="all")
        if merged.empty:
            continue
        b = benchmark(merged)
        r = run(merged)
        results[tag] = (r, b)
        print(line(tag, r, b))
        print(f"{'  (buy & hold benchmark)':34} ret {b['total']*100:>8.1f}%  "
              f"CAGR {b['cagr']*100:>7.1f}%  maxDD {b['maxdd']*100:>7.1f}%")

    # Is the trend filter still the thing doing the work at this width?
    print("\n" + "=" * 104)
    print("3. ABLATION on the full cross-asset universe — which rule earns its place?")
    print("=" * 104)
    full = pd.concat([p for p in panels.values() if not p.empty], axis=1).ffill(limit=5).dropna(how="all")
    b = benchmark(full)
    for tag, kw in [("full model (MA200 + abs)", {}),
                    ("drop MA200 filter", {"use_ma": False}),
                    ("drop absolute momentum", {"use_abs": False}),
                    ("drop BOTH (raw momentum)", {"use_ma": False, "use_abs": False})]:
        print(line(tag, run(full, **kw), b))
    print(f"{'  (buy & hold benchmark)':34} ret {b['total']*100:>8.1f}%  maxDD {b['maxdd']*100:>7.1f}%")

    print("\n" + "=" * 104)
    print("4. HOW MANY NAMES TO HOLD, at full width")
    print("=" * 104)
    for n in (1, 3, 5, 8, 12, 20):
        print(line(f"top {n}", run(full, top_n=n), b))


if __name__ == "__main__":
    main()
