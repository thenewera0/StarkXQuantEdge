"""Tests for drift detection + circuit breaker (Blueprint v2 §4.2). Run: python -m scripts.test_p2_drift"""
from __future__ import annotations

import time
import unittest.mock as m

from app import drift
from app.config import settings

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

print("== Page-Hinkley ==")
# Stable positive expectancy -> no drift.
stable = [0.5, -1.0, 1.5, 0.4, -1.0, 1.8, 0.3, -1.0, 1.6] * 4
d1, _ = drift.page_hinkley(stable, settings.drift_delta, settings.drift_lambda)
check("no drift on a stable +EV sequence", d1 is False)

# Regime break: healthy, then a persistent losing run -> drift detected.
broke = [1.5, 1.8, 1.6, 0.5, 1.7] * 4 + [-1.0] * 15
d2, ph2 = drift.page_hinkley(broke, settings.drift_delta, settings.drift_lambda)
check("drift detected after a downward shift", d2 is True and ph2 > settings.drift_lambda)

# Recovery: once the window is all-good again, no drift (auto-recover).
recovered = [1.5, 1.6, 1.7, 1.4, 1.8] * 6
d3, _ = drift.page_hinkley(recovered, settings.drift_delta, settings.drift_lambda)
check("recovers (no drift) once the window is healthy again", d3 is False)

print("== state(): drift de-risk ==")
drift.refresh()
with m.patch.object(drift, "_recent_r", return_value=broke), m.patch.object(drift, "_daily_r", return_value=(0.5, 3)):
    st = drift.state()
check("drifting flag set", st["drifting"] is True)
check("ev_floor raised while drifting", st["ev_floor"] == settings.drift_ev_floor)
check("size cut while drifting", st["size_mult"] == settings.drift_size_mult)
check("not halted (day_r ok)", st["circuit_halted"] is False)

print("== state(): circuit breaker ==")
drift.refresh()
with m.patch.object(drift, "_recent_r", return_value=stable), m.patch.object(drift, "_daily_r", return_value=(-4.2, 8)):
    st2 = drift.state()
check("circuit halts on day_r < -3R with enough trades", st2["circuit_halted"] is True)
drift.refresh()
with m.patch.object(drift, "_recent_r", return_value=stable), m.patch.object(drift, "_daily_r", return_value=(-4.2, 2)):
    st3 = drift.state()
check("no halt on tiny sample (< circuit_min_trades)", st3["circuit_halted"] is False)

print("== state(): thin data ==")
drift.refresh()
with m.patch.object(drift, "_recent_r", return_value=[0.5, -1.0]), m.patch.object(drift, "_daily_r", return_value=(0.0, 0)):
    st4 = drift.state()
check("no drift below drift_min_trades", st4["drifting"] is False and st4["size_mult"] == 1.0)

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL DRIFT TESTS PASSED")
