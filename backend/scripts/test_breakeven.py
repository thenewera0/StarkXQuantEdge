"""Does a BREAKEVEN stop fix the give-back problem? Run: python -m scripts.test_breakeven

Live evidence (07-28/29): 19 straight losses while the market rose. MFE showed nearly every trade
reached ~0.8-1.3R in profit and then round-tripped into a full stop. AVAX went +1.45% with a 1.10%
stop (1.3R) and still lost the full R.

An earlier test of a WIDE ATR trail made the core engine worse, so this tests something narrower and
more surgical: once a trade has proven itself by N R of favourable movement, move the stop to
breakeven and stop nothing else. That converts give-backs into scratches without capping winners.

Compares, on identical causal entries and real costs:
    A  fixed stop/target (current behaviour)
    B  breakeven once +0.5R is reached
    C  breakeven once +0.75R is reached
    D  breakeven once +1.0R is reached
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

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
           "LINKUSDT", "AVAXUSDT", "UNIUSDT", "AAVEUSDT", "SUIUSDT", "RUNEUSDT"]
INTERVALS = ["1h", "4h"]
BARS = 3000
MAX_HOLD = 48
LONG = {"Buy", "Strong Buy"}
SHORT = {"Sell", "Strong Sell"}
BE_LEVELS = [None, 0.5, 0.75, 1.0]


def replay(symbol: str, interval: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {str(b): [] for b in BE_LEVELS}
    try:
        df = fetch_klines_history(symbol, interval, BARS)
        df, _ = validate_ohlcv(df, interval)
        ind = compute_indicators(df)
    except Exception:
        return out
    if len(ind) < 300:
        return out
    opens = ind["open"].to_numpy(); highs = ind["high"].to_numpy(); lows = ind["low"].to_numpy()
    n = len(ind)
    i = 250
    while i < n - 1:
        prev = ind.iloc[i]
        regime = detect_regime(prev)
        sig = score_row(prev, interval, regime=regime)
        d = "long" if sig.label in LONG else "short" if sig.label in SHORT else None
        if d is None or np.isnan(sig.atr) or sig.atr <= 0:
            i += 1; continue
        entry = float(opens[i + 1])
        plan = trade_levels(entry, sig.atr, d, interval, regime,
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
        cost = round_trip_cost("crypto", symbol, sig.atr / entry)

        last_j = i + 1
        for be in BE_LEVELS:
            st = stop0; best_r = 0.0; px = None
            j = i + 1
            while j < min(n, i + 1 + MAX_HOLD):
                hi, lo = float(highs[j]), float(lows[j])
                fav = (hi - entry) / risk if d == "long" else (entry - lo) / risk
                best_r = max(best_r, fav)
                if be is not None and best_r >= be:
                    st = max(st, entry) if d == "long" else min(st, entry)
                if d == "long":
                    if lo <= st: px = st; break
                    if hi >= target: px = target; break
                else:
                    if hi >= st: px = st; break
                    if lo <= target: px = target; break
                j += 1
            if px is None:
                px = float(opens[min(j, n - 1)])
            g = (px - entry) / entry if d == "long" else (entry - px) / entry
            out[str(be)].append(g - cost)
            last_j = max(last_j, j)
        i = last_j + 1
    return out


def main() -> None:
    agg: dict[str, list[float]] = {str(b): [] for b in BE_LEVELS}
    for s in SYMBOLS:
        for itv in INTERVALS:
            r = replay(s, itv)
            for k, v in r.items():
                agg[k].extend(v)
        print(f"  {s} done ({len(agg[str(BE_LEVELS[0])])} trades so far)")

    print("\n=== BREAKEVEN STOP COMPARISON (net of real costs) ===")
    base = None
    for be in BE_LEVELS:
        a = np.array(agg[str(be)])
        if not len(a):
            continue
        w = (a > 0).sum(); scr = ((a <= 0) & (a > -0.002)).sum()
        gains = a[a > 0].sum(); losses = -a[a < 0].sum()
        tot = a.sum() * 100
        if be is None:
            base = tot
        label = "A fixed (current)" if be is None else f"BE at +{be}R"
        delta = "" if be is None else f"  ({tot - base:+.1f}% vs fixed)"
        print(f"  {label:20} n={len(a):5} win={w/len(a):.3f} scratches={scr:4} "
              f"total={tot:+9.2f}% exp={a.mean()*100:+.4f}%/trade PF={gains/losses if losses>0 else 0:.3f}{delta}")


if __name__ == "__main__":
    main()
