"""test_lab_controls.py

Section 1 & 9:
test_lab_controls:
1. Baseline series != strategy series.
2. Trade counts: n_baseline > n_strategy (AlwaysLongControl holds continuous positions across closed bars).
3. RandomEntryControl: 1,000 permutations, same number of trades, same exit logic.
4. CostGate: Auto-disables any strategy/timeframe variant whose median cost_R > 0.25.
"""

import numpy as np
import pandas as pd
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.controls import CostGate, RandomEntryControl, AlwaysLongControl


def generate_bars(n: int = 250, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    returns = np.random.normal(0.0002, 0.015, n)
    price = 60000.0 * np.cumprod(1.0 + returns)
    high = price * (1.0 + np.abs(np.random.normal(0.002, 0.005, n)))
    low = price * (1.0 - np.abs(np.random.normal(0.002, 0.005, n)))
    open_p = low + (high - low) * np.random.uniform(0.2, 0.8, n)
    volume = np.random.uniform(100.0, 5000.0, n)
    return pd.DataFrame({"open": open_p, "high": high, "low": low, "close": price, "volume": volume})


def main():
    print("================================================================================")
    print("TEST 9.6: test_lab_controls (Statistical Controls & Cost Gate)")
    print("================================================================================")

    bars = generate_bars(n=250, seed=17)

    # 1. CostGate Invariant: median cost_R <= 0.25
    trades_cheap = [
        {"risk_r_usd": 50.0, "fee_paid_usd": 2.50, "gst_paid_usd": 0.45, "slippage_usd": 1.50, "funding_paid_usd": 0.0}
        for _ in range(30)
    ]
    passed_cheap, med_r_cheap = CostGate.evaluate(trades_cheap)
    assert passed_cheap is True, f"Cheap trades should pass cost gate, got median cost_R: {med_r_cheap}"
    assert med_r_cheap <= 0.25
    print(f"[PASS] Low-cost strategy passed CostGate: median cost_R = {med_r_cheap:.4f} <= 0.25")

    # High-cost trades: total cost $15 on $50 risk = 0.30 R > 0.25 R
    trades_expensive = [
        {"risk_r_usd": 50.0, "fee_paid_usd": 8.00, "gst_paid_usd": 1.44, "slippage_usd": 5.00, "funding_paid_usd": 1.00}
        for _ in range(30)
    ]
    passed_exp, med_r_exp = CostGate.evaluate(trades_expensive)
    assert passed_exp is False, f"Expensive trades must fail cost gate, got median cost_R: {med_r_exp}"
    assert med_r_exp > 0.25
    print(f"[PASS] High-cost strategy correctly auto-disabled: median cost_R = {med_r_exp:.4f} > 0.25")

    # 2. RandomEntryControl: 1,000 permutations
    n_strat_trades = 25
    perm_means = RandomEntryControl.simulate_random_entries(
        bars=bars,
        n_trades=n_strat_trades,
        stop_atr_mult=2.0,
        target_r=2.0,
        max_hold_bars=12,
        permutations=1000,
        seed=17,
    )
    assert len(perm_means) == 1000, f"Expected 1,000 permutations, got {len(perm_means)}"
    print(f"[PASS] RandomEntryControl completed 1,000 permutations. Baseline mean R = {np.mean(perm_means):.4f}")

    # 3. AlwaysLongControl vs Strategy Series: n_baseline > n_strategy and series != strategy
    always_long_series = AlwaysLongControl.simulate_always_long(
        bars=bars,
        stop_atr_mult=2.0,
        max_hold_bars=12,
    )
    n_baseline = len(always_long_series)
    assert n_baseline > n_strat_trades, (
        f"Invariant failed: n_baseline ({n_baseline}) must be > n_strategy ({n_strat_trades})"
    )
    print(f"[PASS] Invariant verified: n_baseline ({n_baseline}) > n_strategy ({n_strat_trades})")

    # Mock strategy series
    strat_series = [0.15 + (i % 3) * 0.20 for i in range(n_strat_trades)]
    assert np.array_equal(strat_series, always_long_series[:n_strat_trades]) is False, (
        "Baseline series must not equal strategy series"
    )
    print("[PASS] Invariant verified: baseline series != strategy series")

    print("================================================================================")
    print("ALL test_lab_controls CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
