"""Tests for the Hedge strategy allocator (Blueprint v2 §4.3). Run: python -m scripts.test_p2_alloc"""
from __future__ import annotations

import unittest.mock as m

from app import allocator
from app.config import settings

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)


def mk(trend_r, trend_n, fade_r, fade_n):
    return {"trend": {"n": trend_n, "r_mean_decayed": trend_r},
            "range-fade": {"n": fade_n, "r_mean_decayed": fade_r}}


print("== Hedge weights ==")
with m.patch.object(allocator, "_family_stats", return_value=mk(0.3, 20, -0.4, 20)):
    w = allocator.weights()
check("tilts toward the winning family", w["trend"] > w["range-fade"])
check("weights sum to 1", abs(sum(w.values()) - 1.0) < 1e-9)
check("floor holds on the loser", w["range-fade"] >= settings.allocator_floor - 1e-9)

with m.patch.object(allocator, "_family_stats", return_value=mk(0.2, 20, 0.2, 20)):
    w2 = allocator.weights()
check("equal performance -> ~equal weights", abs(w2["trend"] - w2["range-fade"]) < 0.02)

print("== thin families stay neutral ==")
with m.patch.object(allocator, "_family_stats", return_value=mk(0.9, 3, -0.9, 2)):
    w3 = allocator.weights()   # both below min_trades -> neutral scores -> equal
check("thin data -> no tilt (equal weights)", abs(w3["trend"] - w3["range-fade"]) < 0.02)

print("== family_multiplier ==")
allocator.refresh()
with m.patch.object(allocator, "_family_stats", return_value=mk(0.4, 30, -0.5, 30)):
    mt = allocator.family_multiplier("trend")
    mf = allocator.family_multiplier("range-fade")
check("winner multiplier > 1", mt > 1.0)
check("loser multiplier < 1", mf < 1.0)
check("multiplier capped at allocator_max_mult", mt <= settings.allocator_max_mult + 1e-9)
check("disabled -> 1.0", (lambda: (setattr(settings, 'allocator_enabled', False),
                                    allocator.family_multiplier("trend") == 1.0,
                                    setattr(settings, 'allocator_enabled', True))[1])())

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL ALLOCATOR TESTS PASSED")
