"""Honest historical backtest of the Flash Bot triggers. Run: python -m scripts.backtest_flash

Replays each trigger causally (decision from closed bar t, entry at t+1 open), walks forward with
the real stop/target/time-stop, and charges the SAME per-market cost model the live system uses.
No optimization here — just: does this trigger family have any edge net of costs?
"""
from __future__ import annotations

import numpy as np

from app.config import settings
from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv
from app.flash import detect_trigger, FLASH_SYMBOLS
from app.indicators import compute_indicators

INTERVALS = ["15m", "1h"]
BARS = 3000


def backtest(symbol: str, interval: str) -> list[dict]:
    try:
        df = fetch_klines_history(symbol, interval, BARS)
        df, _ = validate_ohlcv(df, interval)
        ind = compute_indicators(df)
    except Exception:
        return []
    if len(ind) < 300:
        return []

    opens = ind["open"].to_numpy(); highs = ind["high"].to_numpy(); lows = ind["low"].to_numpy()
    n = len(ind)
    trades: list[dict] = []
    i = 250
    while i < n - 1:
        window = ind.iloc[: i + 1]                       # only closed bars up to i
        trig = detect_trigger(window)
        if trig is None:
            i += 1
            continue
        last = ind.iloc[i]
        atr = float(last["atr"]) if not np.isnan(last["atr"]) else 0.0
        entry = float(opens[i + 1])                      # fill at NEXT bar open (causal)
        if atr <= 0 or entry <= 0:
            i += 1
            continue
        atr_pct = atr / entry
        if atr_pct < settings.flash_min_atr_pct:
            i += 1
            continue

        stop_d = settings.flash_stop_atr * atr
        tgt_d = settings.flash_rr * stop_d
        direction = trig["direction"]
        if direction == "long":
            stop, target = entry - stop_d, entry + tgt_d
        else:
            stop, target = entry + stop_d, entry - tgt_d
        cost = round_trip_cost("crypto", symbol, atr_pct)

        exit_px, reason = None, "time"
        j = i + 1
        while j < min(n, i + 1 + settings.flash_max_hold_bars):
            hi, lo = highs[j], lows[j]
            if direction == "long":
                if lo <= stop: exit_px, reason = stop, "stop"; break
                if hi >= target: exit_px, reason = target, "target"; break
            else:
                if hi >= stop: exit_px, reason = stop, "stop"; break
                if lo <= target: exit_px, reason = target, "target"; break
            j += 1
        if exit_px is None:
            exit_px = float(opens[min(j, n - 1)])
        gross = (exit_px - entry) / entry if direction == "long" else (entry - exit_px) / entry
        net = gross - cost
        trades.append({"symbol": symbol, "interval": interval, "kind": trig["kind"],
                       "direction": direction, "net": net, "reason": reason,
                       "r": net / (stop_d / entry)})
        i = j + 1                                        # no overlapping positions
    return trades


def main() -> None:
    allt: list[dict] = []
    for sym in FLASH_SYMBOLS[:12]:
        for itv in INTERVALS:
            t = backtest(sym, itv)
            allt.extend(t)
        print(f"  {sym}: {sum(1 for x in allt if x['symbol']==sym)} trades")

    if not allt:
        print("no trades"); return
    nets = np.array([t["net"] for t in allt])
    rs = np.array([t["r"] for t in allt])
    wins = (nets > 0).sum()
    print("\n=== FLASH BOT BACKTEST (net of real costs, causal) ===")
    print(f"trades={len(allt)}  win_rate={wins/len(allt):.3f}  total_net={nets.sum()*100:.2f}%  "
          f"avg_R={rs.mean():+.3f}  expectancy={nets.mean()*100:+.4f}%/trade")
    gains = nets[nets > 0].sum(); losses = -nets[nets < 0].sum()
    print(f"profit_factor={gains/losses if losses>0 else float('inf'):.3f}")
    for key in ("kind", "interval", "direction"):
        print(f"\nby {key}:")
        for v in sorted({t[key] for t in allt}):
            sub = [t for t in allt if t[key] == v]
            sn = np.array([t["net"] for t in sub]); sw = (sn > 0).sum()
            print(f"  {str(v):10} n={len(sub):4} win={sw/len(sub):.3f} avgR={np.mean([t['r'] for t in sub]):+.3f} total={sn.sum()*100:+.2f}%")


if __name__ == "__main__":
    main()
