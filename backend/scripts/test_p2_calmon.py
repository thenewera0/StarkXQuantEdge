"""Tests for the self-calibration monitor (Blueprint v2 §4.6). Run: python -m scripts.test_p2_calmon"""
from __future__ import annotations

import unittest.mock as m
import numpy as np

from app import calibration as cal
from app.config import settings

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)


class FakeCur:
    def __init__(self, rows): self._rows = rows
    def execute(self, *a, **k): pass
    def fetchall(self): return self._rows
    def __enter__(self): return self
    def __exit__(self, *a): return False

class FakeConn:
    def __init__(self, rows): self._rows = rows
    def cursor(self): return FakeCur(self._rows)
    def __enter__(self): return self
    def __exit__(self, *a): return False


def run_health(rows):
    cal._health_cache = None
    with m.patch.object(cal.db, "enabled", return_value=True), \
         m.patch.object(cal.db, "get_conn", return_value=FakeConn(rows)):
        return cal.calibration_health()


print("== Brier calibration monitor ==")
rng = np.random.default_rng(0)
# Well-calibrated + skilled: p high -> usually win, p low -> usually lose.
good = []
for _ in range(80):
    p = rng.uniform(0.1, 0.9)
    y = 1.0 if rng.uniform() < p else 0.0
    good.append((p, y))
hg = run_health(good)
check("skilled probs: ratio < 1 (adds skill)", hg["ratio"] is not None and hg["ratio"] < 1.0)
check("skilled probs: size_mult == 1.0 (no shrink)", hg["size_mult"] == 1.0)

# Mis-calibrated: predictions ANTI-correlated with outcomes (confidently wrong).
bad = []
for _ in range(80):
    p = rng.uniform(0.1, 0.9)
    y = 1.0 if rng.uniform() < (1 - p) else 0.0   # outcome opposite to prediction
    bad.append((p, y))
hb = run_health(bad)
check("mis-calibrated: ratio > 1 (worse than base rate)", hb["ratio"] is not None and hb["ratio"] > 1.0)
check("mis-calibrated: size shrinks below 1", hb["size_mult"] < 1.0)
check("size never below floor", hb["size_mult"] >= settings.calibration_size_floor - 1e-9)

print("== thin data -> neutral ==")
ht = run_health([(0.5, 1.0)] * 5)   # < calibration_min_trades
check("thin data -> mult 1.0, n small", ht["size_mult"] == 1.0 and ht["n"] == 0)

print("== size_multiplier respects the flag ==")
cal._health_cache = (9e18, {"size_mult": 0.5})  # force a cached degraded value
settings.calibration_monitor_enabled = False
check("disabled -> 1.0", cal.size_multiplier() == 1.0)
settings.calibration_monitor_enabled = True
check("enabled -> uses health mult", cal.size_multiplier() == 0.5)
cal._health_cache = None

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL CALIBRATION-MONITOR TESTS PASSED")
