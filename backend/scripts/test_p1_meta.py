"""Local tests for the meta-labeling model (Blueprint v2 §5). Run: python -m scripts.test_p1_meta"""
from __future__ import annotations

import time
import numpy as np

from app import meta_model as mm
from app.meta_features import FEATURE_KEYS, build
from app.indicators import htf_trend, compute_indicators
import pandas as pd

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

print("== feature vector ==")
raw = {"composite": -40.0, "agreement": 0.6, "reward_risk": 1.8, "atr_pct": 0.012, "win_prob": 0.42,
       "hour_of_week": 50, "htf_trend": -1, "is_long": False, "regime": "range",
       "factors": {"trend": 20, "momentum": None, "volatility": -30, "structure": 10,
                   "flow": None, "sentiment": None, "macro": None, "consensus": None},
       "hurst": 0.3, "variance_ratio": 0.7, "entropy": None, "kalman_slope": -0.02}
v = build(raw)
check("vector length == FEATURE_KEYS", len(v) == len(FEATURE_KEYS) == 29)
check("None factor -> 0.0", v[FEATURE_KEYS.index("momentum")] == 0.0)
check("abs_composite correct", v[FEATURE_KEYS.index("abs_composite")] == 40.0)
check("regime one-hot: range=1, others=0", v[FEATURE_KEYS.index("regime_range")] == 1.0 and v[FEATURE_KEYS.index("regime_weak_trend")] == 0.0)
check("is_long false -> 0", v[FEATURE_KEYS.index("is_long")] == 0.0)
check("stat feature passed through (hurst=0.3)", v[FEATURE_KEYS.index("hurst")] == 0.3)
check("stat None -> neutral default (entropy=1.0)", v[FEATURE_KEYS.index("entropy")] == 1.0)
check("funding_z/fng_z default neutral 0.0 when absent", v[FEATURE_KEYS.index("funding_z")] == 0.0 and v[FEATURE_KEYS.index("fng_z")] == 0.0)

print("== z-score (§2.5) ==")
from app.signal_service import _zscore
check("z=0 at the mean", _zscore(5.0, [3.0, 5.0, 7.0]) == 0.0)
check("z>0 above mean, z<0 below", _zscore(9.0, [1.0, 2.0, 3.0]) > 0 and _zscore(0.0, [1.0, 2.0, 3.0]) < 0)
check("degenerate history -> 0", _zscore(5.0, [2.0, 2.0, 2.0]) == 0.0)

print("== AUC + rank ==")
r = mm._rankdata(np.array([10.0, 10.0, 20.0, 5.0]))  # sorted 5,10,10,20 -> ties at pos 2,3 = 2.5
check("tied ranks averaged", r[0] == r[1] == 2.5 and r[2] == 4.0 and r[3] == 1.0)
y = np.array([0, 0, 1, 1, 1]); s_perfect = np.array([0.1, 0.2, 0.8, 0.9, 0.95])
check("perfect separation AUC=1", abs(mm._auc(s_perfect, y) - 1.0) < 1e-9)
check("inverse separation AUC=0", abs(mm._auc(-s_perfect, y) - 0.0) < 1e-9)
rng = np.random.default_rng(0)
check("random AUC ~0.5", abs(mm._auc(rng.uniform(size=400), (rng.uniform(size=400) < 0.5).astype(int)) - 0.5) < 0.12)

print("== weighted logreg learns ==")
n = 300; X = rng.normal(size=(n, 4))
truth = (X[:, 0] - X[:, 1] > 0).astype(float)   # depends on features 0,1
sw = np.ones(n)
mu, sd = X.mean(0), X.std(0) + 1e-9
w = mm._fit_logreg((X - mu) / sd, truth, sw)
p = mm._predict_raw(X, mu, sd, w)
check("logreg separates the signal (AUC>0.9)", mm._auc(p, truth) > 0.9)

print("== time-series CV ==")
auc_cv = mm._ts_cv_auc(X, truth, sw)
check("ts-cv returns a finite AUC in [0,1]", auc_cv is not None and 0.0 <= auc_cv <= 1.0)
check("ts-cv AUC is strong for a learnable signal", auc_cv is not None and auc_cv > 0.8)

print("== predict from a stored model (shadow) ==")
nf = len(FEATURE_KEYS)
model = {"features": FEATURE_KEYS, "mu": [0.0]*nf, "sd": [1.0]*nf, "w": [0.0]*(nf+1),
         "knots_x": [0.0, 1.0], "knots_y": [0.3, 0.6], "is_active": False, "metrics": {}}
mm._cache = (time.time(), model)
p = mm.predict(raw)
check("predict returns calibrated p in [0.02,0.98]", p is not None and 0.02 <= p <= 0.98)
check("is_active False in shadow", mm.is_active() is False)
mm._cache = (time.time(), None)
check("predict None when no model", mm.predict(raw) is None)

print("== HTF trend (resample) ==")
idx = pd.date_range("2024-01-01", periods=400, freq="1h", tz="UTC")
up = pd.DataFrame({"open": np.arange(400)+100.0, "high": np.arange(400)+101.0,
                   "low": np.arange(400)+99.0, "close": np.arange(400)+100.0,
                   "volume": np.ones(400)}, index=idx)
check("HTF trend = +1 on a clean uptrend", htf_trend(up, "1h") == 1)
down = up.iloc[::-1].copy(); down.index = idx
check("HTF trend = -1 on a clean downtrend", htf_trend(down, "1h") == -1)

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL META TESTS PASSED")
