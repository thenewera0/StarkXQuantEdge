"""Fast synchronous 120-strategy Flash Bot Evaluator.

Run: python -m scripts.run_flash_fast
"""

from __future__ import annotations

import itertools
import numpy as np
import pandas as pd

from app.costs import round_trip_cost
from app.data import fetch_klines
from app.data.validate import validate_ohlcv
from app.indicators import compute_indicators

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
INTERVALS = ["1h"]
LIMIT = 500


def main():
    dataset = {}
    for s in SYMBOLS:
        try:
            df = fetch_klines(s, "1h", LIMIT)
            df, _ = validate_ohlcv(df, "1h")
            if len(df) > 150:
                dataset[s] = compute_indicators(df)
        except Exception:
            pass

    triggers = ["mom_burst", "rsi_dip", "keltner_break", "supertrend_flip", "cvd_climax"]
    htf_filters = ["none", "ema200", "kalman"]
    biases = ["long_short", "long_only"]
    reward_risks = [1.5, 2.0]
    hold_bars = [12, 24]

    grid = list(itertools.product(triggers, htf_filters, biases, reward_risks, hold_bars))
    results = []

    for trig, htf, bias, rr, hold in grid:
        all_trades = []
        for s, ind in dataset.items():
            opens = ind["open"].to_numpy(float)
            highs = ind["high"].to_numpy(float)
            lows = ind["low"].to_numpy(float)
            closes = ind["close"].to_numpy(float)
            atrs = ind["atr"].to_numpy(float)
            n = len(ind)

            i = 100
            while i < n - 1:
                row = ind.iloc[i]
                close, atr = closes[i], atrs[i]
                if not close or not atr or atr <= 0:
                    i += 1
                    continue

                ema200 = row.get("ema200")
                rsi = row.get("rsi")
                cvd_z = row.get("cvd_z")
                vol_burst = row.get("vol_burst")
                kalman_slope = row.get("kalman_slope")
                ut_pos = row.get("ut_pos")
                bb_upper = row.get("bb_upper")
                bb_lower = row.get("bb_lower")

                direction = None

                # HTF Filter
                if htf == "ema200" and ema200:
                    htf_long = close > ema200
                    htf_short = close < ema200
                elif htf == "kalman" and kalman_slope is not None:
                    htf_long = kalman_slope > 0
                    htf_short = kalman_slope < 0
                else:
                    htf_long = htf_short = True

                # Triggers
                if trig == "mom_burst":
                    if vol_burst and vol_burst > 1.2:
                        if htf_long and close > row.get("ema9", close):
                            direction = "long"
                        elif bias == "long_short" and htf_short and close < row.get("ema9", close):
                            direction = "short"

                elif trig == "rsi_dip":
                    if rsi and rsi < 40 and htf_long:
                        direction = "long"
                    elif bias == "long_short" and rsi and rsi > 60 and htf_short:
                        direction = "short"

                elif trig == "keltner_break":
                    if bb_upper and close > bb_upper and htf_long:
                        direction = "long"
                    elif bias == "long_short" and bb_lower and close < bb_lower and htf_short:
                        direction = "short"

                elif trig == "supertrend_flip":
                    if ut_pos == 1 and htf_long:
                        direction = "long"
                    elif bias == "long_short" and ut_pos == -1 and htf_short:
                        direction = "short"

                elif trig == "cvd_climax":
                    if cvd_z and cvd_z > 0.4 and htf_long:
                        direction = "long"
                    elif bias == "long_short" and cvd_z and cvd_z < -0.4 and htf_short:
                        direction = "short"

                if direction is None:
                    i += 1
                    continue

                entry = opens[i + 1]
                stop_dist = 1.5 * atr
                stop = entry - stop_dist if direction == "long" else entry + stop_dist
                target = entry + rr * stop_dist if direction == "long" else entry - rr * stop_dist
                cost = round_trip_cost("crypto", s, atr / entry)

                exit_px = None
                j = i + 1
                while j < min(n, i + 1 + hold):
                    hi, lo = highs[j], lows[j]
                    if direction == "long":
                        if lo <= stop:
                            exit_px = stop
                            break
                        if hi >= target:
                            exit_px = target
                            break
                    else:
                        if hi >= stop:
                            exit_px = stop
                            break
                        if lo <= target:
                            exit_px = target
                            break
                    j += 1

                if exit_px is None:
                    exit_px = opens[min(j, n - 1)]

                gross = (exit_px - entry) / entry if direction == "long" else (entry - exit_px) / entry
                net = gross - cost
                all_trades.append(net)
                i = j + 1

        if all_trades:
            arr = np.array(all_trades)
            wins = (arr > 0).sum()
            gains = arr[arr > 0].sum()
            losses = -arr[arr < 0].sum()
            pf = gains / losses if losses > 0 else 0.0
            results.append({
                "name": f"{trig} | {htf} | {bias} | RR{rr} | h{hold}",
                "trades": len(arr),
                "net": float(arr.sum() * 100),
                "win_rate": float(wins / len(arr)),
                "exp": float(arr.mean() * 100),
                "pf": float(pf),
            })

    results.sort(key=lambda x: -x["net"])

    print("=" * 110)
    print(f"{'FLASH BOT STRATEGY CONFIGURATION':50} {'TRADES':>7} {'WIN RATE':>9} {'TOTAL NET%':>12} {'EXP%/TRADE':>12} {'PF':>7}")
    print("=" * 110)
    for r in results[:15]:
        print(f"{r['name']:50} {r['trades']:7d} {r['win_rate']*100:8.1f}% {r['net']:+11.2f}% {r['exp']:+11.4f}% {r['pf']:7.3f}")

    print("\n--- BOTTOM 5 WORST ---")
    for r in results[-5:]:
        print(f"{r['name']:50} {r['trades']:7d} {r['win_rate']*100:8.1f}% {r['net']:+11.2f}% {r['exp']:+11.4f}% {r['pf']:7.3f}")
    print("=" * 110)


if __name__ == "__main__":
    main()
