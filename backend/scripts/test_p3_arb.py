"""Tests for the funding-carry detector (Blueprint v2 §6.1). Run: python -m scripts.test_p3_arb"""
from __future__ import annotations

import unittest.mock as m
import numpy as np

from app import arb
from app.config import settings

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

print("== AR(1) params ==")
# Mean-reverting funding around 0.0001 with phi~0.6.
rng = np.random.default_rng(0)
mu_true = 0.0001
x = [mu_true]
for _ in range(199):
    x.append(mu_true + 0.6 * (x[-1] - mu_true) + rng.normal(0, 0.00005))
p = arb._ar1_params(x)
check("AR(1) fits", p is not None)
mu, phi = p
check("mu ~ true mean", abs(mu - mu_true) < 0.0001)
check("phi in (0,1) and ~0.6", 0.3 < phi < 0.9)
check("thin history -> None", arb._ar1_params([0.0001] * 5) is None)

print("== forecast collection ==")
# Persistent high funding -> collection > flat mean.
c_hi = arb._forecast_collection(current=0.001, mu=0.0002, phi=0.8, horizon=9)
c_lo = arb._forecast_collection(current=0.0002, mu=0.0002, phi=0.8, horizon=9)
check("higher current funding -> more expected collection", c_hi > c_lo)
check("collection positive when funding positive", c_hi > 0)

print("== EV gate ==")
cost = 2 * (settings.arb_spot_taker + settings.arb_perp_taker)   # ~0.0028
# Normal low funding (0.01%/8h): 9 periods ~ 0.09% < 0.28% cost -> negative EV.
with m.patch.object(arb, "fetch_funding_history", return_value=[0.0001] * 60):
    o_norm = arb.funding_carry_opportunity("BTCUSDT")
check("normal funding -> opportunity computed", o_norm is not None)
check("normal funding -> NEGATIVE EV (not worth it)", o_norm["ev"] < 0 and o_norm["positive"] is False)
check("cost is both-legs round trip (~0.28%)", abs(o_norm["cost"] - cost) < 1e-9)

# Funding SPIKE (0.15%/8h sustained): 9 periods ~ 1.35% >> cost -> positive EV.
with m.patch.object(arb, "fetch_funding_history", return_value=[0.0015] * 60):
    o_spike = arb.funding_carry_opportunity("BTCUSDT")
check("funding spike -> POSITIVE EV", o_spike["ev"] > 0 and o_spike["positive"] is True)
check("spike annualized yield is large", o_spike["annualized_yield"] > 0.5)

print("== scan ==")
with m.patch.object(arb, "fetch_funding_history", return_value=[0.0001] * 60), \
     m.patch.object(arb, "_log_opportunities", return_value=None):
    res = arb.scan_funding_carry(["BTCUSDT", "ETHUSDT"])
check("scan returns per-symbol opportunities", res["scanned"] == 2 and len(res["opportunities"]) == 2)
check("scan sorted by EV desc", res["opportunities"][0]["ev"] >= res["opportunities"][-1]["ev"])
check("normal market -> 0 positive opportunities (honest)", res["positive"] == 0)

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL ARB TESTS PASSED")
