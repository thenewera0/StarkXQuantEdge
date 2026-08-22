"""Does taking profit earlier beat holding for target? Measured on the CURRENT config.

The live book captured only 17.3% of its cumulative peak unrealised profit: 345 trades reached
+526.8% of MFE in aggregate and booked +91.0%. That is the "profit shows but never gets taken"
complaint, quantified.

Two readings of that number, and they demand different fixes:
  * If winners are reversing before target, an earlier exit books more.
  * If most stops simply never worked (they went straight against), the giveback is an illusion of
    aggregation and an earlier exit only cuts the winners short.

The live data says the second is largely true -- 68% of stopped trades never reached even +0.5%
unrealised -- but 23% DID show a full +1% and still lost. So it has to be measured, not argued.

Every variant below runs on the SAME signals, same bars, same limit entry, same maker cost. Only
the exit changes. Long-only 4h, which is where the measured edge lives.

    python -m scripts.research_exits
"""

from __future__ import annotations

import concurrent.futures as cf
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.indicators import compute_indicators
from app import universe

INTERVAL = "4h"
BARS = 3000
ATR_STOP = 1.2          # matches geometry._TREND_ATR_K
RR = 1.8                # matches the live t1 ladder
MAX_HOLD = 24
STEP = 3
LIMIT_OFFSET = 0.20     # the shipped limit entry


def run_symbol(args):
    sym, mode, param = args
    try:
        ind = compute_indicators(fetch_klines_history(sym, INTERVAL, BARS))
    except Exception:
        return []
    if len(ind) < 400:
        return []
    h, l, c, a = (ind[k].to_numpy(float) for k in ("high", "low", "close", "atr"))
    n = len(ind)
    out = []
    for i in range(250, n - MAX_HOLD - 3, STEP):
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        atr = a[i]
        entry = c[i] - LIMIT_OFFSET * atr           # resting limit
        # fill within 2 bars, else no trade (the shipped rule)
        fill = None
        for j in range(i + 1, min(i + 3, n)):
            if l[j] <= entry:
                fill = j
                break
        if fill is None:
            out.append(0.0)                          # unfilled contributes zero
            continue
        cost = round_trip_cost("crypto", sym, atr / entry, "maker")
        stop = entry - ATR_STOP * atr
        risk = entry - stop
        target = entry + RR * risk
        booked, remaining, realised = False, 1.0, 0.0
        cur_stop = stop
        peak = entry
        exit_px = None
        for j in range(fill, min(fill + MAX_HOLD, n)):
            peak = max(peak, h[j])
            r_now = (h[j] - entry) / risk           # best R reached this bar

            if mode == "partial" and not booked and r_now >= param:
                realised += 0.5 * (entry + param * risk - entry) / entry
                remaining, booked = 0.5, True
            if mode == "breakeven" and r_now >= param:
                cur_stop = max(cur_stop, entry)
            if mode == "trail" and r_now >= 1.0:
                cur_stop = max(cur_stop, h[j] - param * atr)

            if l[j] <= cur_stop:
                exit_px = cur_stop
                break
            if h[j] >= target:
                exit_px = target
                break
        if exit_px is None:
            exit_px = c[min(fill + MAX_HOLD - 1, n - 1)]
        realised += remaining * (exit_px - entry) / entry
        out.append(realised - cost)
    return out


def evaluate(mode, param, syms):
    vals = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(run_symbol, [(s, mode, param) for s in syms]):
            vals.extend(r)
    if not vals:
        return None
    v = np.array(vals)
    traded = v[v != 0.0]
    return {"signals": len(v), "per_signal": v.mean(),
            "traded": len(traded), "hit": (traded > 0).mean() if len(traded) else 0.0}


def main():
    syms = [c["symbol"] for c in universe.catalog(
        ["crypto"], crypto_limit=20, min_volume=universe.MIN_VOLUME_SCAN)]
    print(f"Exit variants on {len(syms)} pairs, {INTERVAL}, long-only, limit entry, maker cost\n")
    print(f"{'exit rule':<38} {'signals':>8} {'per signal':>12} {'traded':>8} {'hit':>7}")
    print("-" * 78)
    rows = []
    for label, mode, param in [
        ("BASELINE fixed stop + 1.8R target", "fixed", 0.0),
        ("book half at +0.5R, run the rest", "partial", 0.5),
        ("book half at +1.0R, run the rest", "partial", 1.0),
        ("book half at +1.5R, run the rest", "partial", 1.5),
        ("stop to breakeven after +0.5R", "breakeven", 0.5),
        ("stop to breakeven after +1.0R", "breakeven", 1.0),
        ("stop to breakeven after +1.5R", "breakeven", 1.5),
        ("trail 1.0 ATR once +1R", "trail", 1.0),
        ("trail 1.5 ATR once +1R", "trail", 1.5),
        ("trail 2.5 ATR once +1R", "trail", 2.5),
    ]:
        r = evaluate(mode, param, syms)
        if not r:
            continue
        rows.append((label, r))
        print(f"{label:<38} {r['signals']:>8,} {r['per_signal']*100:>+11.4f}% "
              f"{r['traded']:>8,} {r['hit']*100:>6.1f}%")

    base = rows[0][1]["per_signal"]
    print("\n" + "=" * 78)
    print("VERDICT (vs the baseline fixed stop + target)")
    print("=" * 78)
    best = max(rows, key=lambda x: x[1]["per_signal"])
    for label, r in rows[1:]:
        d = (r["per_signal"] - base) * 100
        print(f"  {label:<38} {d:>+8.4f}pp  {'BETTER' if d > 0 else 'worse'}")
    print(f"\n  BEST: {best[0]}  ({best[1]['per_signal']*100:+.4f}% per signal)")
    if best[0].startswith("BASELINE"):
        print("  -> No exit change helps. The giveback is mostly trades that never worked,")
        print("     not winners reversing. Taking profit earlier would cut the winners short.")
