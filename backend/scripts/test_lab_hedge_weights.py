"""test_lab_hedge_weights.py

Section 5 & 9:
test_lab_hedge_weights:
Enforces Hedge algorithm allocation rules:
- eta = 0.1 on daily net R per unit risk.
- James-Stein shrinkage toward zero when n < 100.
- Floor: 2% (0.02), Cap: 30% (0.30).
- T0 variants fixed at floor (2%).
- Weights normalized to sum to 1.0.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.allocation import HedgeAllocator


def main():
    print("================================================================================")
    print("TEST 9.8: test_lab_hedge_weights (Hedge Allocation & Shrinkage Constraints)")
    print("================================================================================")

    # 1. Verification of constants
    assert HedgeAllocator.ETA == 0.10, "ETA must be 0.10"
    assert HedgeAllocator.FLOOR_WEIGHT == 0.02, "FLOOR must be 2%"
    assert HedgeAllocator.CAP_WEIGHT == 0.30, "CAP must be 30%"
    print("[PASS] Verified parameters: eta=0.10, floor=2%, cap=30%")

    # 2. Test portfolio with mixed T0, T1, T2, T3 variants
    variants = {
        "v_t0_1": {"tier": "T0", "status": "active", "n_trades": 10, "mean_net_r": 0.50},
        "v_t0_2": {"tier": "T0", "status": "active", "n_trades": 15, "mean_net_r": 0.10},
        "v_t1_shrunk": {"tier": "T1", "status": "active", "n_trades": 40, "mean_net_r": 0.80}, # n < 100 -> shrunk
        "v_t2_mature": {"tier": "T2", "status": "active", "n_trades": 120, "mean_net_r": 0.45}, # n >= 100 -> full
        "v_t3_stellar": {"tier": "T3", "status": "active", "n_trades": 200, "mean_net_r": 4.50}, # huge edge -> capped at 30%
        "v_t1_losing": {"tier": "T1", "status": "active", "n_trades": 50, "mean_net_r": -0.40},
    }

    weights = HedgeAllocator.compute_weights(variants)

    # 3. Assert T0 variants are clamped at floor (2%)
    assert weights["v_t0_1"] == 0.02, f"T0 must be fixed at 2%, got {weights['v_t0_1']}"
    assert weights["v_t0_2"] == 0.02, f"T0 must be fixed at 2%, got {weights['v_t0_2']}"
    print(f"[PASS] T0 variants fixed at floor: v_t0_1={weights['v_t0_1']}, v_t0_2={weights['v_t0_2']}")

    # 4. Assert 30% cap is enforced on stellar performer
    assert weights["v_t3_stellar"] <= 0.3001, f"Top variant must not exceed 30%, got {weights['v_t3_stellar']}"
    print(f"[PASS] Top variant capped at 30%: v_t3_stellar={weights['v_t3_stellar']}")

    # 5. Assert Floor of 2% is enforced for lowest performer
    for vid, w in weights.items():
        assert w >= 0.0199, f"Variant {vid} below floor: {w}"
    print(f"[PASS] Minimum floor (>=2%) verified across all active variants")

    # 6. Assert Normalization: sum of weights equals 1.0 (within roundoff)
    total_weight = sum(weights.values())
    assert abs(total_weight - 1.0) < 0.01, f"Weights must sum to 1.0, got {total_weight}"
    print(f"[PASS] Total weights sum to 1.0: sum = {total_weight:.4f}")

    # 7. James-Stein Shrinkage Check
    # A variant with n=20 trades and mean R = 1.0 should receive less weight than n=150 with mean R = 1.0
    # when uncapped in a multi-asset portfolio
    comp_variants = {
        "v_small_sample": {"tier": "T1", "status": "active", "n_trades": 20, "mean_net_r": 1.0},
        "v_large_sample": {"tier": "T2", "status": "active", "n_trades": 150, "mean_net_r": 1.0},
        "v_other_1": {"tier": "T1", "status": "active", "n_trades": 50, "mean_net_r": 0.2},
        "v_other_2": {"tier": "T1", "status": "active", "n_trades": 50, "mean_net_r": 0.2},
        "v_other_3": {"tier": "T1", "status": "active", "n_trades": 50, "mean_net_r": 0.2},
    }
    comp_weights = HedgeAllocator.compute_weights(comp_variants)
    assert comp_weights["v_large_sample"] > comp_weights["v_small_sample"], (
        f"James-Stein shrinkage failed: large sample ({comp_weights['v_large_sample']}) "
        f"should exceed small sample ({comp_weights['v_small_sample']})"
    )
    print(f"[PASS] James-Stein shrinkage verified: n=20 weight ({comp_weights['v_small_sample']:.4f}) < n=150 weight ({comp_weights['v_large_sample']:.4f})")

    print("================================================================================")
    print("ALL test_lab_hedge_weights CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
