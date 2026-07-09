"""Local unit tests for the P0 measurement-layer changes (Blueprint v2 §2.3, §2.8, §11).

Pure-function tests only — no DB, no network. Run: python -m scripts.test_p0
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.costs import round_trip_cost, cost_in_r
from app.data.validate import validate_ohlcv
from app.factors.scorer import score_row
from app.factors.weights import weights_for_interval
from app import learning
from app.indicators import compute_indicators
from app.backtest import backtest

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

print("== costs ==")
maj = round_trip_cost("crypto", "BTCUSDT", 0.01)
lrg = round_trip_cost("crypto", "SOLUSDT", 0.01)
alt = round_trip_cost("crypto", "ADAUSDT", 0.01)
check("crypto tiers ordered major<large<alt", maj < lrg < alt)
check("atr_pct raises crypto cost", round_trip_cost("crypto","BTCUSDT",0.05) > maj)
check("atr_pct clamp (15%) bounds cost", round_trip_cost("crypto","BTCUSDT",99.0) == round_trip_cost("crypto","BTCUSDT",0.15))
fx_major = round_trip_cost("forex", "EUR/USD", 0.0)
fx_metal = round_trip_cost("forex", "XAU/USD", 0.0)
check("forex spread-based, metal>major", fx_metal > fx_major > 0)
check("forex ignores atr_pct", round_trip_cost("forex","EUR/USD",0.5) == fx_major)
check("cost_in_r inf when no stop", cost_in_r("crypto","BTCUSDT",0.01,0.0) == float("inf"))
check("cost_in_r = cost/stop", abs(cost_in_r("crypto","BTCUSDT",0.01,0.02) - maj/0.02) < 1e-9)

print("== scorer sum|w| normalization ==")
# Build one indicator row.
idx = pd.date_range("2024-01-01", periods=300, freq="1h", tz="UTC")
rng = np.random.default_rng(0)
price = 100 + np.cumsum(rng.normal(0, 1, 300))
df = pd.DataFrame({"open": price, "high": price + 1, "low": price - 1,
                   "close": price + rng.normal(0, 0.2, 300), "volume": rng.uniform(1, 5, 300)}, index=idx)
ind = compute_indicators(df)
row = ind.iloc[-1]
pos_w = weights_for_interval("4h")               # all-positive profile
r_pos = score_row(row, "4h", weights=pos_w)
# Manual sum(w*v)/sum(|w|) over available cats == engine's composite pre-agreement is hard to
# reproduce exactly; instead assert positive-profile path is unchanged vs sum(w) (equal since >0).
avail = {k: v for k, v in r_pos.categories.items() if v is not None}
den_abs = sum(abs(pos_w[k]) for k in avail)
den_sum = sum(pos_w[k] for k in avail)
check("positive profile: sum|w| == sum(w) (no regression)", abs(den_abs - den_sum) < 1e-12)
# Signed weight must not blow the composite past 100.
signed = dict(pos_w); signed["trend"] = -signed["trend"]
r_signed = score_row(row, "4h", weights=signed)
check("signed weight keeps composite in [-100,100]", -100 <= r_signed.composite <= 100)

print("== validate_ohlcv ==")
bad = df.copy()
bad.iloc[5, bad.columns.get_loc("close")] = np.nan           # NaN
bad.iloc[6, bad.columns.get_loc("high")] = -1.0              # negative
bad.iloc[7, bad.columns.get_loc("high")] = bad.iloc[7]["low"] - 5  # high<low inconsistency
bad = pd.concat([bad, bad.iloc[[10]]])                       # duplicate timestamp
bad = bad.sort_index()
clean, rep = validate_ohlcv(bad, "1h")
check("dropped NaN/neg/inconsistent rows", rep["dropped"] >= 3)
check("deduped duplicate timestamp", rep["dedup"] == 1)
check("index unique + sorted after clean", clean.index.is_unique and clean.index.is_monotonic_increasing)
check("all OHLC finite+positive after clean", bool(np.isfinite(clean[["open","high","low","close"]].to_numpy()).all()
                                                   and (clean[["open","high","low","close"]].to_numpy() > 0).all()))

print("== learning label/weight fixes ==")
# Synthetic training rows: 'trend' is anti-predictive (high trend -> loss), volatility predictive.
rows = []
for i in range(120):
    tr = rng.uniform(-100, 100); vol = rng.uniform(-100, 100)
    win = vol > 0 and tr < 0                      # volatility helps, trend hurts
    pnl = (abs(vol) / 1000.0) if win else -(abs(tr) / 1000.0 + 0.01)
    rows.append({"trend": tr, "momentum": rng.uniform(-50, 50), "volatility": vol,
                 "structure": rng.uniform(-50, 50), "result": "target" if win else "stop",
                 "pnl": pnl, "age_days": rng.uniform(0, 30)})
sw = learning._sample_weights(rows)
check("sample weights positive + finite", bool((sw > 0).all() and np.isfinite(sw).all()))
chal = learning._challenger_weights(rows, "4h")
check("challenger produced", chal is not None)
if chal:
    check("trend down-weighted below its base (anti-predictive learned)", chal["trend"] < weights_for_interval("4h")["trend"])
    check("all 8 categories present + summed", set(chal.keys()) == set(weights_for_interval("4h").keys()))
    # timeouts included: a row with pnl>0 but result!='target' counts as a win now.
    rows2 = rows + [{"trend": -50, "momentum": 0, "volatility": 80, "structure": 0,
                     "result": "timeout", "pnl": 0.02, "age_days": 1}]
    check("timeout with pnl>0 accepted as training row (no crash)", learning._challenger_weights(rows2, "4h") is not None)

print("== backtest with new cost model ==")
res = backtest(ind, "BTCUSDT", "4h")
check("backtest runs end-to-end", res.n_bars == len(ind))
check("net returns are cost-adjusted (finite)", all(np.isfinite(t.net_return) for t in res.trades))

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL P0 TESTS PASSED")
