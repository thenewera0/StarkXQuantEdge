"""Flash v3 research — test PRINCIPLED hypotheses, not a parameter sweep.

v1 (naive triggers, fixed 2R)         -> -0.350%/trade
v2 (multi-factor + adaptive exits)    -> -0.376%/trade
Both negative. But the live record says something loud: in crypto, LONGS win 51-66% by regime
while SHORTS lose in every regime. v1/v2 traded both directions symmetrically, so they spent half
their trades fighting the only edge the data actually shows.

Hypotheses tested here (each is a real idea, evaluated once — no hunting):
  H1 long-only                     — stop fighting the proven directional bias
  H2 long-only + HTF uptrend       — only buy when the higher timeframe agrees
  H3 buy-the-dip in an uptrend     — RSI oversold ABOVE the 200EMA (this is what the core engine's
                                      winning long trades actually look like: mean-reversion inside
                                      an uptrend, not breakout chasing)
  H4 H3 + order-flow confirmation  — same, but require CVD to show buyers actually stepping in

Exits use the v2 finding that trailing works: breakeven at +1R, ATR trail after +1.5R.
Causal: decide on closed bar t, fill at t+1 open, real per-market costs.
"""
from __future__ import annotations

import sys
import numpy as np

from app.config import settings
from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv
from app.flash import FLASH_SYMBOLS
from app.indicators import compute_indicators

INTERVALS = ["1h", "4h"]
BARS = 3000
STOP_ATR = 2.2
TRAIL_ATR = 1.6
BE_AT_R, TRAIL_AT_R = 1.0, 1.5
MAX_HOLD = 30


def _f(row, k):
    v = row.get(k)
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def entry_signal(ind, i: int, hypothesis: str) -> str | None:
    """Return 'long'/'short'/None for bar i under the given hypothesis."""
    last, prev = ind.iloc[i], ind.iloc[i - 1]
    close, ema9, ema21, ema200 = _f(last, "close"), _f(last, "ema9"), _f(last, "ema21"), _f(last, "ema200")
    rsi, atr = _f(last, "rsi"), _f(last, "atr")
    vol, volsma = _f(last, "volume"), _f(last, "vol_sma20")
    cvd_z, flow = _f(last, "cvd_z"), _f(last, "flow_ratio")
    if None in (close, ema9, ema21, rsi, atr) or atr <= 0:
        return None
    prev_close = _f(prev, "close") or close
    thrust = (close - prev_close) / close
    vol_exp = (vol / volsma) if (vol and volsma and volsma > 0) else 1.0
    up_htf = ema200 is not None and close > ema200

    if hypothesis in ("H1", "H2"):
        # momentum burst, long side only
        burst = vol_exp >= 1.15 and thrust > 0 and close > ema9 > ema21 and rsi > 52
        if not burst:
            return None
        if hypothesis == "H2" and not up_htf:
            return None
        return "long"

    if hypothesis in ("H3", "H4"):
        # buy the dip INSIDE an uptrend — what the core engine's winning longs look like
        if not up_htf:
            return None
        pullback = rsi < 42 and close < ema21          # oversold but structurally intact
        turning = thrust > 0                            # first sign of the bounce
        if not (pullback and turning):
            return None
        if hypothesis == "H4":
            if cvd_z is None or flow is None:
                return None
            if not (cvd_z > -0.5 and flow > 0):         # buyers actually stepping in
                return None
        return "long"
    return None


def run(symbol: str, interval: str, hypothesis: str) -> list[dict]:
    try:
        df = fetch_klines_history(symbol, interval, BARS)
        df, _ = validate_ohlcv(df, interval)
        ind = compute_indicators(df)
    except Exception:
        return []
    if len(ind) < 300:
        return []
    opens = ind["open"].to_numpy(); highs = ind["high"].to_numpy(); lows = ind["low"].to_numpy()
    atrs = ind["atr"].to_numpy(); n = len(ind)
    out: list[dict] = []
    i = 250
    while i < n - 1:
        d = entry_signal(ind, i, hypothesis)
        if d is None:
            i += 1; continue
        atr = float(atrs[i]); entry = float(opens[i + 1])
        if not np.isfinite(atr) or atr <= 0 or entry <= 0:
            i += 1; continue
        atr_pct = atr / entry
        if atr_pct < settings.flash_min_atr_pct:
            i += 1; continue
        risk = STOP_ATR * atr
        stop = entry - risk if d == "long" else entry + risk
        cost = round_trip_cost("crypto", symbol, atr_pct)
        best_r = 0.0; exit_px = None; reason = "time"
        j = i + 1
        while j < min(n, i + 1 + MAX_HOLD):
            hi, lo = float(highs[j]), float(lows[j])
            fav = (hi - entry) / risk if d == "long" else (entry - lo) / risk
            best_r = max(best_r, fav)
            if best_r >= TRAIL_AT_R:
                t = (hi - TRAIL_ATR * atr) if d == "long" else (lo + TRAIL_ATR * atr)
                stop = max(stop, t) if d == "long" else min(stop, t)
            elif best_r >= BE_AT_R:
                stop = max(stop, entry) if d == "long" else min(stop, entry)
            if d == "long" and lo <= stop: exit_px, reason = stop, ("trail" if stop >= entry else "stop"); break
            if d == "short" and hi >= stop: exit_px, reason = stop, ("trail" if stop <= entry else "stop"); break
            j += 1
        if exit_px is None:
            exit_px = float(opens[min(j, n - 1)])
        gross = (exit_px - entry) / entry if d == "long" else (entry - exit_px) / entry
        net = gross - cost
        out.append({"net": net, "r": net / (risk / entry), "reason": reason, "interval": interval})
        i = j + 1
    return out


def main() -> None:
    for hyp in (sys.argv[1:] or ["H1", "H2", "H3", "H4"]):
        allt: list[dict] = []
        for sym in FLASH_SYMBOLS[:14]:
            for itv in INTERVALS:
                allt.extend(run(sym, itv, hyp))
        if not allt:
            print(f"{hyp}: no trades"); continue
        nets = np.array([t["net"] for t in allt]); rs = np.array([t["r"] for t in allt])
        w = (nets > 0).sum(); g = nets[nets > 0].sum(); l = -nets[nets < 0].sum()
        print(f"{hyp}: n={len(allt):5} win={w/len(allt):.3f} total={nets.sum()*100:+9.2f}% "
              f"exp={nets.mean()*100:+.4f}%/trade avgR={rs.mean():+.3f} PF={g/l if l>0 else 0:.3f}")


if __name__ == "__main__":
    main()
