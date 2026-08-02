"""What does raising the concurrency cap actually do to drawdown?

The cap is currently 6 positions at the "standard" ($1k-$10k) tier, and it is the binding
constraint on how much the engine trades — not the size of the universe. Raising it is a real
risk decision, so it gets measured rather than argued about.

Method: backtest the live scorer across the whole allocatable universe to produce a stream of
dated trades, then REPLAY that one stream through a portfolio simulator under different cap
rules. Same signals, same fills, same costs every time — only the admission rule changes, so any
difference in the equity curve is caused by the rule and nothing else.

Rules compared:
  fixed N            classic count cap, the thing we have now
  per-class          count cap plus "no class may hold more than half the book"
  heat budget        admit while TOTAL OPEN RISK stays under a % of equity (count is emergent)
  heat + throttle    heat budget that shrinks while equity is below its high-water mark

    python -m scripts.research_cap
"""

from __future__ import annotations

import concurrent.futures as cf
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from app import universe
from app.backtest import backtest
from app.indicators import compute_indicators

RISK_PCT = 0.02          # risk per trade as a fraction of equity, matching sizing.TIERS
BARS = 1500
INTERVAL = "4h"


@dataclass
class Fill:
    """One trade from the signal stream, with the risk it consumes while open."""
    entry: pd.Timestamp
    exit: pd.Timestamp
    ret: float            # net return on notional, after costs
    market: str
    symbol: str
    risk_frac: float      # stop distance as a fraction of entry — the R of this trade


def _load(item: dict) -> list[Fill]:
    sym, market = item["symbol"], item["category"]
    try:
        df = universe.fetch(sym, INTERVAL, BARS)
        if len(df) < 400:
            return []
        res = backtest(compute_indicators(df), sym, INTERVAL)
    except Exception:
        return []
    out: list[Fill] = []
    for t in res.trades:
        # The stop distance recorded AT ENTRY. Never MAE — MAE is how far the trade actually went
        # against us, so sizing on it means every eventual winner looks risk-free and gets sized
        # enormous. That is lookahead, and the first run of this script produced a +25,688,827,324%
        # equity curve because of it.
        if t.risk_frac <= 1e-6:
            continue
        out.append(Fill(t.entry_time, t.exit_time, t.net_return, market, sym, t.risk_frac))
    return out


def build_stream() -> list[Fill]:
    items = universe.catalog(allocatable_only=True, crypto_limit=45)
    fills: list[Fill] = []
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for got in ex.map(_load, items):
            fills.extend(got)
    fills.sort(key=lambda f: f.entry)
    return fills


def simulate(stream: list[Fill], *, cap: int | None = None, class_cap: int | None = None,
             heat_cap: float | None = None, throttle: bool = False,
             max_gross: float = 1.0, risk_pct: float = RISK_PCT) -> dict:
    """Replay the stream, admitting trades under one rule. Returns equity-curve metrics.

    Every admitted trade risks `risk_pct` of CURRENT equity, so the book compounds down as well
    as up — the property that actually protects capital.
    """
    equity, peak = 1.0, 1.0
    open_pos: list[Fill] = []
    curve: list[tuple[pd.Timestamp, float]] = []
    taken = rejected = 0
    concurrent_seen: list[int] = []
    gross_seen: list[float] = []

    events: list[tuple[pd.Timestamp, int, Fill]] = []
    for f in stream:
        events.append((f.entry, 0, f))   # 0 = open sorts before...
        events.append((f.exit, 1, f))    # 1 = close, at the same timestamp
    events.sort(key=lambda e: (e[0], e[1]))

    live: set[int] = set()
    sizes: dict[int, float] = {}

    for ts, kind, f in events:
        fid = id(f)
        if kind == 1:
            if fid in live:
                equity += sizes.pop(fid, 0.0) * f.ret
                live.discard(fid)
                open_pos = [p for p in open_pos if id(p) != fid]
                peak = max(peak, equity)
                curve.append((ts, equity))
            continue

        # --- admission ---
        dd = equity / peak - 1.0
        ok = True
        if cap is not None and len(open_pos) >= cap:
            ok = False
        if ok and class_cap is not None:
            same = sum(1 for p in open_pos if p.market == f.market)
            if same >= class_cap:
                ok = False
        if ok and heat_cap is not None:
            budget = heat_cap
            if throttle:
                # Capital preservation: below the high-water mark the budget contracts, so a
                # losing run automatically de-risks instead of doubling down. Floor at 25% so the
                # engine never switches itself off entirely and stops learning.
                budget *= max(0.25, 1.0 + dd * 2.5)
            open_heat = sum(risk_pct for _ in open_pos)
            if open_heat + risk_pct > budget:
                ok = False
        if not ok:
            rejected += 1
            continue

        # Size so that being stopped out costs exactly risk_pct of equity...
        notional = (equity * risk_pct) / f.risk_frac
        # ...but never borrow. A tight stop implies a huge notional, and with several positions
        # open that silently becomes leverage. Cash accounts cannot do this, and pretending
        # otherwise is what turns a backtest into fiction. Gross exposure stays under 1x equity.
        gross_open = sum(sizes.values())
        gross_budget = equity * max_gross
        if throttle:
            # CAPITAL PRESERVATION. Below the high-water mark the exposure budget contracts, so a
            # losing run automatically de-risks instead of doubling down at full size. Floored at
            # 25% so the engine keeps taking (small) trades and keeps learning.
            gross_budget *= max(0.25, 1.0 + dd * 2.5)
        notional = min(notional, max(0.0, gross_budget - gross_open))
        if notional <= equity * 1e-4:
            rejected += 1          # no room left in the book — this is a real constraint, not a skip
            continue
        sizes[fid] = notional
        live.add(fid)
        open_pos.append(f)
        concurrent_seen.append(len(open_pos))
        gross_seen.append(sum(sizes.values()) / max(equity, 1e-9))
        taken += 1

    if not curve:
        return {}
    eq = pd.Series([v for _, v in curve])
    dd = float((eq / eq.cummax() - 1.0).min())
    days = max((curve[-1][0] - curve[0][0]).days, 1)
    cagr = float(equity ** (365 / days) - 1.0) if equity > 0 else -1.0
    return {"total": equity - 1.0, "cagr": cagr, "maxdd": dd,
            "calmar": cagr / abs(dd) if dd < -1e-9 else 0.0,
            "taken": taken, "rejected": rejected,
            "peak_gross": max(gross_seen) if gross_seen else 0.0,
            "avg_concurrent": float(np.mean(concurrent_seen)) if concurrent_seen else 0.0,
            "max_concurrent": max(concurrent_seen) if concurrent_seen else 0}


def show(tag: str, r: dict) -> None:
    if not r:
        print(f"{tag:38} (no trades)")
        return
    print(f"{tag:38} ret {r['total']*100:>7.1f}%  maxDD {r['maxdd']*100:>7.1f}%  "
          f"Calmar {r['calmar']:>6.2f}  took {r['taken']:>4}  "
          f"avg open {r['avg_concurrent']:>4.1f}  peak {r['max_concurrent']:>3}  "
          f"peak gross {r['peak_gross']:>5.2f}x")


def main() -> None:
    print("Building the trade stream across the allocatable universe...")
    stream = build_stream()
    if not stream:
        print("No trades produced — cannot measure.")
        return
    by_market: dict[str, int] = {}
    for f in stream:
        by_market[f.market] = by_market.get(f.market, 0) + 1
    span = (stream[-1].entry - stream[0].entry).days
    print(f"  {len(stream)} trades over {span} days across {len(by_market)} classes: {by_market}\n")

    print("=" * 124)
    print("1. COUNT CAP ALONE, at today's UNLIMITED gross exposure")
    print("   (this is what the live system does today: nothing caps notional)")
    print("=" * 124)
    for n in (3, 6, 10, 15, 20, 30, None):
        show(f"cap {n if n else 'unlimited'}, gross uncapped", simulate(stream, cap=n, max_gross=99.0))

    print()
    print("=" * 124)
    print("2. THE ACTUAL BINDING CONSTRAINT — gross exposure, with the count cap wide open")
    print("=" * 124)
    for g in (0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 99.0):
        show(f"gross <= {g:>4.1f}x, cap 30", simulate(stream, cap=30, max_gross=g))

    print()
    print("=" * 124)
    print("3. RAISING THE COUNT CAP once gross exposure is properly limited")
    print("=" * 124)
    for g in (1.0, 2.0, 3.0):
        for n in (6, 12, 20, 30):
            show(f"gross <= {g:.1f}x, cap {n}", simulate(stream, cap=n, max_gross=g))
        print()

    print("=" * 124)
    print("4. DRAWDOWN THROTTLE — does shrinking the budget under water protect capital?")
    print("=" * 124)
    for g in (1.0, 2.0, 3.0):
        show(f"gross <= {g:.1f}x, cap 20, no throttle",
             simulate(stream, cap=20, max_gross=g, heat_cap=0.99))
        show(f"gross <= {g:.1f}x, cap 20, THROTTLED",
             simulate(stream, cap=20, max_gross=g, heat_cap=0.99, throttle=True))

    print()
    print("=" * 124)
    print("5. THE CANDIDATE vs TODAY")
    print("=" * 124)
    show("TODAY: cap 6, class 3, gross uncapped",
         simulate(stream, cap=6, class_cap=3, max_gross=99.0))
    for g in (1.0, 1.5, 2.0):
        show(f"CANDIDATE: cap 20, class 7, gross {g:.1f}x, throttled",
             simulate(stream, cap=20, class_cap=7, max_gross=g, heat_cap=0.99, throttle=True))


if __name__ == "__main__":
    main()
