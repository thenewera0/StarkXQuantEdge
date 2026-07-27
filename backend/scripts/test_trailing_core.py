"""Does an ADAPTIVE TRAILING EXIT improve the CORE engine? Run: python -m scripts.test_trailing_core

The Flash v2 backtest showed trailing exits were the one strongly positive component (+277% over
281 trades, 59% win) even inside a losing strategy. The right move is to test that exit on the
strategy that ALREADY has an edge (core crypto), not to keep trying to rescue a broken one.

Replays historical core signals two ways on identical entries:
  A. FIXED    — the current rule: exit at target or stop
  B. TRAILING — breakeven at +1R, then an ATR trailing stop (winners run)
Same causal entries, same real costs. Purely an exit comparison.
"""
from __future__ import annotations

import numpy as np

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv
from app.factors import score_row
from app.geometry import trade_levels
from app.indicators import compute_indicators
from app.regime import detect_regime

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
INTERVAL = "4h"
BARS = 3000
MAX_HOLD = 48
LONG = {"Buy", "Strong Buy"}
SHORT = {"Sell", "Strong Sell"}
TRAIL_ATR = 2.0
BE_AT_R = 1.0
TRAIL_AT_R = 1.5


def replay(symbol: str) -> tuple[list[float], list[float]]:
    try:
        df = fetch_klines_history(symbol, INTERVAL, BARS)
        df, _ = validate_ohlcv(df, INTERVAL)
        ind = compute_indicators(df)
    except Exception:
        return [], []
    if len(ind) < 300:
        return [], []
    opens = ind["open"].to_numpy(); highs = ind["high"].to_numpy(); lows = ind["low"].to_numpy()
    n = len(ind)
    fixed: list[float] = []; trail: list[float] = []
    i = 250
    while i < n - 1:
        prev = ind.iloc[i]
        regime = detect_regime(prev)
        sig = score_row(prev, INTERVAL, regime=regime)
        direction = "long" if sig.label in LONG else "short" if sig.label in SHORT else None
        if direction is None or np.isnan(sig.atr) or sig.atr <= 0:
            i += 1; continue
        entry = float(opens[i + 1])
        plan = trade_levels(entry, sig.atr, direction, INTERVAL, regime,
                            swing_high=prev.get("swing_high"), swing_low=prev.get("swing_low"),
                            pivot_r1=prev.get("pivot_r1"), pivot_s1=prev.get("pivot_s1"),
                            bb_mid=prev.get("bb_mid"), bb_upper=prev.get("bb_upper"),
                            bb_lower=prev.get("bb_lower"))
        if plan["direction"] == "flat" or not plan["stop"] or not plan["target"]:
            i += 1; continue
        stop0, target = float(plan["stop"]), float(plan["target"])
        risk = abs(entry - stop0)
        if risk <= 0:
            i += 1; continue
        atr = float(sig.atr)
        cost = round_trip_cost("crypto", symbol, atr / entry)

        # ---- A: fixed target/stop ----
        fx = None
        j = i + 1
        while j < min(n, i + 1 + MAX_HOLD):
            hi, lo = float(highs[j]), float(lows[j])
            if direction == "long":
                if lo <= stop0: fx = stop0; break
                if hi >= target: fx = target; break
            else:
                if hi >= stop0: fx = stop0; break
                if lo <= target: fx = target; break
            j += 1
        if fx is None: fx = float(opens[min(j, n - 1)])
        g = (fx - entry) / entry if direction == "long" else (entry - fx) / entry
        fixed.append(g - cost)

        # ---- B: trailing ----
        st = stop0; best_r = 0.0; tx = None
        k = i + 1
        while k < min(n, i + 1 + MAX_HOLD):
            hi, lo = float(highs[k]), float(lows[k])
            fav = (hi - entry) / risk if direction == "long" else (entry - lo) / risk
            best_r = max(best_r, fav)
            if best_r >= TRAIL_AT_R:
                t = (hi - TRAIL_ATR * atr) if direction == "long" else (lo + TRAIL_ATR * atr)
                st = max(st, t) if direction == "long" else min(st, t)
            elif best_r >= BE_AT_R:
                st = max(st, entry) if direction == "long" else min(st, entry)
            if direction == "long" and lo <= st: tx = st; break
            if direction == "short" and hi >= st: tx = st; break
            k += 1
        if tx is None: tx = float(opens[min(k, n - 1)])
        g2 = (tx - entry) / entry if direction == "long" else (entry - tx) / entry
        trail.append(g2 - cost)

        i = max(j, k) + 1
    return fixed, trail


def main() -> None:
    F: list[float] = []; T: list[float] = []
    for s in SYMBOLS:
        f, t = replay(s)
        F.extend(f); T.extend(t)
        print(f"  {s}: {len(f)} trades")
    if not F:
        print("no trades"); return
    for name, arr in (("FIXED target/stop", F), ("TRAILING (BE@1R, ATR trail)", T)):
        a = np.array(arr); w = (a > 0).sum()
        gains = a[a > 0].sum(); losses = -a[a < 0].sum()
        print(f"\n{name}: trades={len(a)} win={w/len(a):.3f} total={a.sum()*100:+.2f}% "
              f"expectancy={a.mean()*100:+.4f}%/trade PF={gains/losses if losses>0 else 0:.3f}")
    d = (np.array(T).sum() - np.array(F).sum()) * 100
    print(f"\nTRAILING vs FIXED: {d:+.2f}% total  ({'BETTER' if d > 0 else 'WORSE'})")


if __name__ == "__main__":
    main()
