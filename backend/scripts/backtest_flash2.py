"""Flash v2 backtest: multi-factor score + ADAPTIVE exits. Run: python -m scripts.backtest_flash2

v1 measured 35.2% win / PF 0.65 / -0.35% per trade with 3 naive triggers and a fixed 2R target.
v2 changes two things and measures whether either actually helps:
  1. entry  — multi-factor confluence (order flow + momentum + excitation gate + location)
  2. exit   — breakeven at +1R, then an ATR trailing stop (let winners run past a fixed target)

Causal throughout: decision from closed bar t, fill at t+1 open, real per-market costs.
"""
from __future__ import annotations

import sys
import numpy as np

from app.config import settings
from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv
from app.flash import flash_score, FLASH_SYMBOLS
from app.indicators import compute_indicators

INTERVALS = ["15m", "1h"]
BARS = 3000
SCORE_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0
EXCITE_MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
TRAIL_ATR = 1.6
BE_AT_R = 1.0
TRAIL_AT_R = 1.5


def run(symbol: str, interval: str) -> list[dict]:
    try:
        df = fetch_klines_history(symbol, interval, BARS)
        df, _ = validate_ohlcv(df, interval)
        ind = compute_indicators(df)
    except Exception:
        return []
    if len(ind) < 300:
        return []

    opens = ind["open"].to_numpy(); highs = ind["high"].to_numpy(); lows = ind["low"].to_numpy()
    atrs = ind["atr"].to_numpy()
    n = len(ind)
    out: list[dict] = []
    i = 250
    while i < n - 1:
        sc = flash_score(ind.iloc[: i + 1])
        if sc is None or abs(sc["score"]) < SCORE_MIN:
            i += 1; continue
        if sc["factors"].get("excitation", 0.0) < EXCITE_MIN:
            i += 1; continue
        atr = float(atrs[i])
        entry = float(opens[i + 1])
        if not np.isfinite(atr) or atr <= 0 or entry <= 0:
            i += 1; continue
        atr_pct = atr / entry
        if atr_pct < settings.flash_min_atr_pct:
            i += 1; continue

        direction = sc["direction"]
        risk = settings.flash_stop_atr * atr
        stop = entry - risk if direction == "long" else entry + risk
        cost = round_trip_cost("crypto", symbol, atr_pct)

        best_r = 0.0
        exit_px, reason = None, "time"
        j = i + 1
        while j < min(n, i + 1 + settings.flash_max_hold_bars):
            hi, lo = float(highs[j]), float(lows[j])
            # favourable excursion in R
            fav = (hi - entry) / risk if direction == "long" else (entry - lo) / risk
            best_r = max(best_r, fav)

            # adaptive stop: breakeven at +1R, ATR-trail after +1.5R
            if best_r >= TRAIL_AT_R:
                trail = (hi - TRAIL_ATR * atr) if direction == "long" else (lo + TRAIL_ATR * atr)
                stop = max(stop, trail) if direction == "long" else min(stop, trail)
            elif best_r >= BE_AT_R:
                stop = max(stop, entry) if direction == "long" else min(stop, entry)

            if direction == "long" and lo <= stop:
                exit_px, reason = stop, ("stop" if stop < entry else "trail"); break
            if direction == "short" and hi >= stop:
                exit_px, reason = stop, ("stop" if stop > entry else "trail"); break
            j += 1
        if exit_px is None:
            exit_px = float(opens[min(j, n - 1)])

        gross = (exit_px - entry) / entry if direction == "long" else (entry - exit_px) / entry
        net = gross - cost
        out.append({"symbol": symbol, "interval": interval, "direction": direction,
                    "net": net, "r": net / (risk / entry), "reason": reason, "mfe_r": best_r})
        i = j + 1
    return out


def main() -> None:
    allt: list[dict] = []
    for sym in FLASH_SYMBOLS[:12]:
        for itv in INTERVALS:
            allt.extend(run(sym, itv))
    if not allt:
        print("no trades"); return
    nets = np.array([t["net"] for t in allt]); rs = np.array([t["r"] for t in allt])
    wins = (nets > 0).sum(); gains = nets[nets > 0].sum(); losses = -nets[nets < 0].sum()
    print(f"\n=== FLASH v2 (score>={SCORE_MIN}, excite>={EXCITE_MIN}, adaptive exits) ===")
    print(f"trades={len(allt)}  win={wins/len(allt):.3f}  totalNet={nets.sum()*100:+.2f}%  "
          f"avgR={rs.mean():+.3f}  expectancy={nets.mean()*100:+.4f}%/trade  PF={gains/losses if losses>0 else 0:.3f}")
    for key in ("interval", "direction", "reason"):
        print(f"by {key}: ", end="")
        for v in sorted({t[key] for t in allt}):
            sub = [t for t in allt if t[key] == v]
            sn = np.array([t["net"] for t in sub])
            print(f"{v}: n={len(sub)} win={(sn>0).sum()/len(sub):.2f} tot={sn.sum()*100:+.1f}%  ", end="")
        print()


if __name__ == "__main__":
    main()
