"""Local tests for the range-fade family (Blueprint v2 §2.2, §3.3). Run: python -m scripts.test_p1_range"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.factors.scorer import _momentum, _volatility, score_row
from app.geometry import trade_levels
from app.indicators import compute_indicators
from app.signal_service import _risk_geometry
from app.regime import detect_regime

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

print("== regime-conditional scorer (fade in range) ==")
overbought = pd.Series({"rsi": 80.0, "stoch_k": 90.0, "bb_pctb": 0.95})
m_trend = _momentum(overbought, "weak_trend")
m_range = _momentum(overbought, "range")
v_trend = _volatility(overbought, "weak_trend")
v_range = _volatility(overbought, "range")
check("overbought momentum: bullish in trend, bearish in range", m_trend > 0 and m_range < 0)
check("overbought momentum flips exact sign", abs(m_trend + m_range) < 1e-9)
check("overbought %B: bullish in trend, bearish in range", v_trend > 0 and v_range < 0)

print("== range-fade geometry ==")
# Price below the mean -> a LONG fade targets the mean, stops below the lower band.
g_long = trade_levels(100.0, 2.0, "long", "4h", "range", bb_mid=104.0, bb_upper=108.0, bb_lower=99.0)
check("range long is a fade", g_long["is_fade"] is True)
check("range long target = mid (above price)", g_long["target"] == 104.0 and g_long["target"] > g_long["entry"])
check("range long stop below entry & below lower band-ish", g_long["stop"] < g_long["entry"])
check("range long RR positive", g_long["reward_risk"] is not None and g_long["reward_risk"] > 0)
# Price ABOVE the mean but 'long' signal -> no valid fade -> stand down (flat).
g_bad = trade_levels(106.0, 2.0, "long", "4h", "range", bb_mid=104.0, bb_upper=108.0, bb_lower=99.0)
check("range long above mean -> no trade (flat)", g_bad["direction"] == "flat")
# Short fade above the mean.
g_short = trade_levels(106.0, 2.0, "short", "4h", "range", bb_mid=104.0, bb_upper=108.0, bb_lower=99.0)
check("range short is a fade targeting mid (below price)", g_short["is_fade"] and g_short["target"] == 104.0 and g_short["target"] < g_short["entry"])
# Trend geometry unaffected (extension target beyond price).
g_tr = trade_levels(100.0, 2.0, "long", "4h", "weak_trend", swing_high=130.0, bb_mid=104.0, bb_upper=108.0, bb_lower=99.0)
check("trend long uses extension target (not the mid band)", g_tr["is_fade"] is False and g_tr["target"] > 100.0)

print("== OU half-life indicator ==")
# Mean-reverting series (AR(1) with phi~0.5) should yield a finite, positive half-life.
rng = np.random.default_rng(3)
n = 400
x = np.zeros(n)
for t in range(1, n):
    x[t] = 0.5 * x[t-1] + rng.normal(0, 1)
close = 100 + x
df = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close,
                   "volume": np.ones(n)}, index=pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"))
ind = compute_indicators(df)
hl = ind["ou_halflife"].dropna()
check("OU half-life computed + finite", len(hl) > 0 and bool(np.isfinite(hl).all()))
check("OU half-life positive & short for phi=0.5 series", bool((hl > 0).all()) and float(hl.median()) < 10)

print("== live geometry delegates to shared module (consistency) ==")
row = ind.iloc[-1].copy()
# Force a clean range fade scenario on the row.
row["close"], row["atr"], row["bb_mid"], row["bb_upper"], row["bb_lower"] = 100.0, 2.0, 104.0, 108.0, 99.0
live = _risk_geometry(row, "long", "4h", "range")
shared = trade_levels(100.0, 2.0, "long", "4h", "range",
                      swing_high=row.get("swing_high"), swing_low=row.get("swing_low"),
                      pivot_r1=row.get("pivot_r1"), pivot_s1=row.get("pivot_s1"),
                      bb_mid=104.0, bb_upper=108.0, bb_lower=99.0, risk_per_trade_pct=0.75)
check("live _risk_geometry == shared trade_levels (same stop/target)",
      live["stop"] == shared["stop"] and live["target"] == shared["target"])

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL RANGE-FAMILY TESTS PASSED")
