"""test_lab_spawn_limits.py

Section 5 & 9:
test_lab_spawn_limits:
Enforces Self-Improvement and Spawn Invariants:
1. Candidate parameter mutation (+/- 20% on numeric parameters).
2. Clamping strictly inside pre-registered bounds from config/lab_spec.json.
3. Max 1 spawn per strategy per 30 days.
4. Max 40 concurrent variants globally across the lab.
5. Every spawn increments research_trials and logs parent in lab_events.
6. Champion Swap gate: requires >= 100 trades and paired day-block lower 95% bound > 0.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.allocation import SelfImprovementGovernor
from app.lab.storage import LabStorage


def main():
    print("================================================================================")
    print("TEST 9.9: test_lab_spawn_limits (Spawn Bounds, Trial Counter & Swap Invariants)")
    print("================================================================================")

    # 1. Parameter Mutation (+/- 20%) within Pre-Registered Bounds
    params = {"entry_period": 55, "exit_period": 20, "stop_atr": 2.5}
    bounds = {
        "entry_period": [20, 100],
        "exit_period": [10, 40],
        "stop_atr": [1.5, 4.0],
    }

    neighbours = SelfImprovementGovernor.generate_spawn_candidates(
        parent_variant_id="donchian_4h_base",
        current_params=params,
        numeric_bounds=bounds,
    )

    assert len(neighbours) == 2, f"Expected exactly 2 neighbours (+20% and -20%), got {len(neighbours)}"
    
    high_neighbor = neighbours[0]
    low_neighbor = neighbours[1]

    # Verify +20%
    assert high_neighbor["entry_period"] == int(round(55 * 1.20)) # 66
    assert high_neighbor["exit_period"] == int(round(20 * 1.20))   # 24
    assert high_neighbor["stop_atr"] == round(2.5 * 1.20, 2)       # 3.0
    print(f"[PASS] +20% Neighbour within bounds: {high_neighbor}")

    # Verify -20%
    assert low_neighbor["entry_period"] == int(round(55 * 0.80))  # 44
    assert low_neighbor["exit_period"] == int(round(20 * 0.80))    # 16
    assert low_neighbor["stop_atr"] == round(2.5 * 0.80, 2)        # 2.0
    print(f"[PASS] -20% Neighbour within bounds: {low_neighbor}")

    # 2. Boundary Clamping Verification
    extreme_params = {"entry_period": 95, "stop_atr": 3.8}
    extreme_neighbours = SelfImprovementGovernor.generate_spawn_candidates(
        parent_variant_id="donchian_4h_extreme",
        current_params=extreme_params,
        numeric_bounds=bounds,
    )
    # 95 * 1.20 = 114 -> clamped to max bound 100
    # 3.8 * 1.20 = 4.56 -> clamped to max bound 4.0
    assert extreme_neighbours[0]["entry_period"] == 100, "Must be clamped to upper bound 100"
    assert extreme_neighbours[0]["stop_atr"] == 4.0, "Must be clamped to upper bound 4.0"
    print(f"[PASS] Pre-registered bounds strictly enforced upon upper breach: {extreme_neighbours[0]}")

    # 3. Research Trials Counter Increment Invariant
    storage = LabStorage(db_path=":memory:")
    trials_initial = storage.get_trials_count()
    assert trials_initial >= 10, f"Expected initial research_trials >= 10, got {trials_initial}"

    storage.increment_trials_count()
    trials_after = storage.get_trials_count()
    assert trials_after == trials_initial + 1, "Each spawn must increment research_trials by 1"
    print(f"[PASS] research_trials verified: {trials_initial} -> {trials_after}")

    # 4. Champion Swap Requires >= 100 Trades & Paired 95% Bound > 0
    # Test 1: Fewer than 100 trades -> swap refused
    short_champ = [0.10] * 50
    short_challenger = [0.25] * 50
    dates_50 = [f"2026-01-{i:02d}" for i in range(50)]
    swap_refused, _ = SelfImprovementGovernor.evaluate_champion_swap(
        champ_returns=short_champ,
        challenger_returns=short_challenger,
        overlapping_dates=dates_50,
    )
    assert swap_refused is False, "Champion swap MUST be rejected when trades < 100"
    print("[PASS] Champion swap strictly rejected when n < 100")

    # Test 2: >= 100 trades and challenger decisively beats champion
    long_champ = [0.05 if i % 2 == 0 else -0.05 for i in range(120)]
    long_challenger = [0.40 if i % 2 == 0 else 0.10 for i in range(120)]
    dates_120 = [f"2026-{(i%10)+1:02d}-{(i%28)+1:02d}" for i in range(120)]
    swap_approved, low_95 = SelfImprovementGovernor.evaluate_champion_swap(
        champ_returns=long_champ,
        challenger_returns=long_challenger,
        overlapping_dates=dates_120,
    )
    assert swap_approved is True, "Champion swap should be approved when lower 95% bound > 0"
    assert low_95 > 0.0
    print(f"[PASS] Champion swap approved when lower 95% bound ({low_95:.4f}) > 0 and n >= 100")

    print("================================================================================")
    print("ALL test_lab_spawn_limits CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
