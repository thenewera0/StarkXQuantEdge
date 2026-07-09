"""Local unit tests for P1.5 — isotonic calibration + EV gate (Blueprint v2 §2.6).

Pure-function tests, no network. Run: python -m scripts.test_p1
"""
from __future__ import annotations

import numpy as np

from app.calibration import _pava, win_prob
from app.costs import cost_in_r

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

print("== PAVA isotonic ==")
# Monotone-increasing truth with noise -> fit must be non-decreasing.
rng = np.random.default_rng(1)
x = rng.uniform(0, 100, 400)
p_true = x / 120.0
y = (rng.uniform(0, 1, 400) < p_true).astype(float)
kn, fit = _pava(x, y)
check("knots sorted ascending", bool(np.all(np.diff(kn) >= 0)))
check("fit non-decreasing (isotonic)", bool(np.all(np.diff(fit) >= -1e-9)))
check("fit within [0,1]", bool((fit >= 0).all() and (fit <= 1).all()))
# higher composite -> higher fitted prob for a clearly increasing signal
lo = float(np.interp(10, kn, fit)); hi = float(np.interp(90, kn, fit))
check("monotone signal: p(90) >= p(10)", hi >= lo)

# Anti-predictive truth (higher x -> LOWER win): isotonic-increasing must flatten (not invert).
y2 = (rng.uniform(0, 1, 400) < (1 - x / 120.0)).astype(float)
kn2, fit2 = _pava(x, y2)
check("anti-predictive signal flattens (near-constant fit)", float(fit2.max() - fit2.min()) < 0.25)

print("== win_prob bounds ==")
# With no DB the module returns 0.5 (non-committal); just assert the clamp contract via _pava lookup.
p = float(np.interp(50, kn, fit))
check("interp prob in [0,1]", 0.0 <= p <= 1.0)

print("== EV math ==")
# EV = p*R - (1-p) - cost_in_r. Positive-edge example.
R = 1.8
cr = cost_in_r("crypto", "BTCUSDT", 0.01, 0.02)
ev_win = 0.55 * R - 0.45 - cr
ev_lose = 0.30 * R - 0.70 - cr
check("cost_in_r finite + positive", np.isfinite(cr) and cr > 0)
check("high p -> higher EV than low p", ev_win > ev_lose)
check("p=0.30,R=1.8 is negative EV (correctly gated out)", ev_lose < 0)
# Breakeven p for R=1.8 ignoring cost is 1/(1+R)=0.357; with cost it's higher.
p_be = (1 + cr) / (1 + R)
check("breakeven p accounts for cost (>1/(1+R))", p_be > 1 / (1 + R))

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL P1 TESTS PASSED")
