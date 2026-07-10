"""Tests for Kelly + ruin-constraint sizing (Blueprint v2 §7). Run: python -m scripts.test_p2_sizing"""
from __future__ import annotations

import numpy as np

from app import sizing

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)


def mc_ruin(f, p, b, target_dd=0.5, paths=20000, steps=800, seed=1):
    """Monte-Carlo P(50% DD before doubling) to validate the closed form."""
    rng = np.random.default_rng(seed)
    wins = rng.random((paths, steps)) < p
    logmult = np.where(wins, np.log(1 + f * b), np.log(1 - f))
    cum = np.cumsum(logmult, axis=1)
    hit_low = cum <= np.log(1 - target_dd)
    hit_high = cum >= np.log(2)
    first_low = np.where(hit_low.any(1), hit_low.argmax(1), steps)
    first_high = np.where(hit_high.any(1), hit_high.argmax(1), steps)
    return float((first_low < first_high).mean())


print("== quarter-Kelly ==")
check("no edge -> 0", sizing.quarter_kelly(0.4, 1.0) == 0.0)
check("positive edge -> positive f", sizing.quarter_kelly(0.6, 2.0) > 0)
# full Kelly for p=0.6,b=2: f = p-(1-p)/b = 0.6-0.2 = 0.4; quarter = 0.1
check("quarter-Kelly value", abs(sizing.quarter_kelly(0.6, 2.0) - 0.1) < 1e-9)

print("== ruin closed-form vs Monte-Carlo ==")
for (f, p, b) in [(0.1, 0.55, 2.0), (0.2, 0.55, 2.0), (0.15, 0.5, 1.8), (0.05, 0.6, 1.5)]:
    cf = sizing.ruin_prob(f, p, b)
    mc = mc_ruin(f, p, b)
    ok = abs(cf - mc) < 0.05
    print(f"    f={f} p={p} b={b}: closed-form={cf:.3f} MC={mc:.3f} {'ok' if ok else 'MISMATCH'}")
    check(f"ruin closed-form ~ MC (f={f},p={p})", ok)

print("== no overflow at tiny f / marginal edge (audit regression) ==")
# tiny f drives z -> +/-inf; must not raise math range error.
for (f, p, b) in [(1e-5, 0.62, 2.0), (1e-5, 0.40, 1.5), (1e-4, 0.5, 1.0), (1e-6, 0.55, 1.8)]:
    try:
        r = sizing.ruin_prob(f, p, b)
        check(f"ruin_prob(f={f},p={p}) finite in [0,1]", 0.0 <= r <= 1.0)
    except Exception as e:
        check(f"ruin_prob(f={f},p={p}) no exception", False)
# ruin_fraction over a negative edge must not raise and returns ~0.
check("ruin_fraction(neg edge) no crash -> ~0", sizing.ruin_fraction(0.45, 1.2, cap=0.02) < 1e-3)

print("== ruin monotonic + negative-edge ==")
check("ruin_prob increases with f", sizing.ruin_prob(0.05, 0.55, 2) < sizing.ruin_prob(0.3, 0.55, 2))
check("negative edge -> high ruin prob", sizing.ruin_prob(0.1, 0.4, 1.5) > 0.5)
check("ruin_fraction ~0 for negative edge", sizing.ruin_fraction(0.4, 1.5, cap=0.02) < 1e-3)
check("ruin_fraction positive for a real edge", sizing.ruin_fraction(0.62, 2.0, cap=0.02) > 0)

print("== tiers + position_size ==")
check("micro tier", sizing.tier_for_equity(50)["tier"] == "micro")
check("standard tier", sizing.tier_for_equity(5000)["tier"] == "standard")
check("growth tier + lower cap", sizing.tier_for_equity(50000)["tier"] == "growth" and sizing.tier_for_equity(50000)["risk_cap"] == 0.015)
check("micro EV threshold strictest", sizing.tier_for_equity(50)["ev_threshold"] > sizing.tier_for_equity(5000)["ev_threshold"])

ps = sizing.position_size(1000, 0.62, 2.0, stop_frac=0.02, drift_mult=1.0)
check("size positive for a real edge", ps["risk_fraction"] > 0 and ps["notional_usd"] > 0)
check("size capped by tier risk_cap (2%)", ps["risk_fraction"] <= 0.02 + 1e-9)
ps_neg = sizing.position_size(1000, 0.4, 1.5, stop_frac=0.02)
check("negative edge -> zero size", ps_neg["risk_fraction"] == 0.0 and ps_neg["tradeable"] is False)
ps_drift = sizing.position_size(1000, 0.62, 2.0, stop_frac=0.02, drift_mult=0.5)
check("drift multiplier halves size", abs(ps_drift["risk_fraction"] - ps["risk_fraction"] * 0.5) < 1e-9)
ps_micro = sizing.position_size(20, 0.62, 2.0, stop_frac=0.02, min_notional=5.0)
check("micro: tiny equity may fail min-notional", ps_micro["tier"] == "micro")

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL SIZING TESTS PASSED")
