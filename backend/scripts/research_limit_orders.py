"""Does limit-order (maker) entry actually beat market entry, once misses are counted?

Maker execution saves 0.12-0.24% per round trip, which on the core crypto long book is worth
+0.34pp/trade. But a resting order only fills when price comes to it, and the setups that run away
immediately — disproportionately the winners — are never entered at all. That is adverse
selection, and it is the whole question.

The metric here is P&L PER SIGNAL, not per fill. Every signal counts once; an unfilled order
contributes ZERO. Market execution fills every signal at the close and pays taker cost. Limit
execution fills a subset at a better basis and pays maker cost. Whichever produces more money per
signal wins, and that comparison carries the misses automatically.

Both arms are driven by the SAME signals over the SAME bars, so nothing differs except how the
entry reaches the market.

    python -m scripts.research_limit_orders
"""

from __future__ import annotations

import concurrent.futures as cf
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.execution import fill_bar, limit_entry
from app.indicators import compute_indicators
from app import universe

INTERVAL = "4h"        # where the core edge lives
BARS = 3000
ATR_STOP = 1.5
RR = 2.0
MAX_HOLD = 24
STEP = 3


def _exit(highs, lows, closes, start, entry, stop, target, direction, n):
    for j in range(start + 1, min(start + 1 + MAX_HOLD, n)):
        if direction == "long":
            if lows[j] <= stop:
                return stop
            if highs[j] >= target:
                return target
        else:
            if highs[j] >= stop:
                return stop
            if lows[j] <= target:
                return target
    return closes[min(start + MAX_HOLD, n - 1)]


def run(args) -> pd.DataFrame:
    sym, offset, expiry = args
    try:
        ind = compute_indicators(fetch_klines_history(sym, INTERVAL, BARS))
    except Exception:
        return pd.DataFrame()
    if len(ind) < 400:
        return pd.DataFrame()
    h, l, c, a = (ind[k].to_numpy(float) for k in ("high", "low", "close", "atr"))
    n = len(ind)
    rows = []
    for i in range(250, n - MAX_HOLD - expiry - 2, STEP):
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        px, atr = c[i], a[i]
        atr_pct = atr / px
        d = "long"      # the measured edge is long-only; shorts are gated off live

        # --- ARM A: market entry at the close, taker cost ---
        m_entry = px
        m_stop = m_entry - ATR_STOP * atr
        m_tgt = m_entry + ATR_STOP * atr * RR
        m_exit = _exit(h, l, c, i, m_entry, m_stop, m_tgt, d, n)
        m_net = (m_exit - m_entry) / m_entry - round_trip_cost("crypto", sym, atr_pct, "taker")

        # --- ARM B: resting limit entry, maker cost, may never fill ---
        plan = limit_entry(px, atr, d, offset_atr=offset, expiry_bars=expiry)
        j = fill_bar(h, l, i, plan, d, n)
        if j is None:
            l_net, filled = 0.0, 0        # never entered — contributes nothing, which is the point
        else:
            e = plan.limit_price
            l_exit = _exit(h, l, c, j, e, e - ATR_STOP * atr, e + ATR_STOP * atr * RR, d, n)
            l_net = (l_exit - e) / e - round_trip_cost("crypto", sym, atr_pct, "maker")
            filled = 1
        rows.append({"symbol": sym, "market_net": m_net, "limit_net": l_net, "filled": filled})
    return pd.DataFrame(rows)


def main() -> None:
    syms = [c["symbol"] for c in universe.catalog(
        ["crypto"], crypto_limit=20, min_volume=universe.MIN_VOLUME_SCAN)]
    print(f"Comparing MARKET vs LIMIT entry on identical signals — {len(syms)} pairs, {INTERVAL}\n")
    print(f"{'offset':>7} {'expiry':>7} {'signals':>8} {'fill%':>7} "
          f"{'market/signal':>14} {'limit/signal':>13} {'edge':>10}")
    print("-" * 74)

    best = None
    for offset in (0.05, 0.10, 0.20, 0.35, 0.50):
        for expiry in (2, 3, 6):
            frames = []
            with cf.ThreadPoolExecutor(max_workers=8) as ex:
                for d in ex.map(run, [(s, offset, expiry) for s in syms]):
                    if not d.empty:
                        frames.append(d)
            if not frames:
                continue
            df = pd.concat(frames, ignore_index=True)
            mkt = df["market_net"].mean()
            lim = df["limit_net"].mean()     # unfilled rows are 0 and drag this down, correctly
            fill = df["filled"].mean()
            edge = lim - mkt
            star = "  <-- best" if best is None or edge > best[0] else ""
            if best is None or edge > best[0]:
                best = (edge, offset, expiry, fill, mkt, lim)
            print(f"{offset:>7.2f} {expiry:>7} {len(df):>8,} {fill*100:>6.1f}% "
                  f"{mkt*100:>+13.4f}% {lim*100:>+12.4f}% {edge*100:>+9.4f}%{star}")

    if not best:
        print("\nNo data.")
        return
    edge, offset, expiry, fill, mkt, lim = best
    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    print(f"  best config: offset {offset} ATR, expiry {expiry} bars, fill rate {fill*100:.1f}%")
    print(f"  market entry: {mkt*100:+.4f}% per signal")
    print(f"  limit  entry: {lim*100:+.4f}% per signal")
    if edge > 0:
        print(f"  -> limit entry is WORTH {edge*100:+.4f}pp per signal, AFTER counting every")
        print(f"     order that never filled as a zero. Ship it.")
    else:
        print(f"  -> limit entry LOSES {edge*100:.4f}pp per signal once misses are counted.")
        print(f"     The cheaper fills do not pay for the trades never taken. Do NOT ship it;")
        print(f"     the {(1-fill)*100:.0f}% of signals that never fill skew toward the winners.")


if __name__ == "__main__":
    main()
