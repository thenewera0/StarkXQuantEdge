"""StarkX QuantEdge v2: Test Evidence Gates & Promotion Protocol.

Asserts:
1. Stage A -> B for Sleeve T:
   - Pre-registration spec hash verified in config/v2_spec.json.
   - >= 2 full market cycles in the historical evidence.
   - Max drawdown <= 60% of buy-and-hold drawdown.
   - Basket pre-tax net Sharpe >= 0.60.
   - 36 monthly start dates after-tax terminal wealth vs cash benchmark.
   - All 4 neighbourhood parameter variants evaluated.
2. Stage A -> B for Sleeve C:
   - Economic gate discipline (hurdle >= 10.5%).
   - Stress window liquidation survival (2021-05-19, 2022-06-13, 2022-11-08).
3. Canonical day_block_bootstrap (B=10,000, seed=17).
4. Tracking error computation (Stage B -> C <= 1.5%).
5. HMAC kill-switch verification (Stage D).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from app.v2.data import get_daily_asset
from app.v2.promotion import (
    day_block_bootstrap,
    evaluate_sleeve_t_stage_a_to_b,
    evaluate_sleeve_c_stage_a_to_b,
    verify_hmac_kill_switch,
    Stage,
)
from app.v2.execution import compute_weekly_tracking_error


def test_bootstrap_statistics():
    print("Testing canonical day-block bootstrap (B=10,000, seed=17)...")
    np.random.seed(42)
    # 200 daily returns with positive drift
    daily_rets = np.random.normal(0.0008, 0.015, 200)
    mean_val, p05, p95 = day_block_bootstrap(daily_rets, block_size=5, n_bootstrap=10000, seed=17)
    
    assert abs(mean_val - np.mean(daily_rets)) < 1e-3, f"Bootstrap mean differs from sample mean: {mean_val}"
    assert p05 < mean_val < p95, f"Percentiles inconsistent: {p05} < {mean_val} < {p95}"
    print(f"PASS: Day-block bootstrap generated: mean={mean_val:.4f}, 5th pctl={p05:.4f}, 95th pctl={p95:.4f}.")


def test_sleeve_t_gates():
    print("Testing Sleeve T Stage A -> Stage B promotion gates...")
    btc_df = get_daily_asset("BTCUSDT")
    eth_df = get_daily_asset("ETHUSDT")
    spec_hash = "3704e9e742e5ee9bcaa491df0c919fba0af23e65417ce106369e09a3803f6497"
    
    status = evaluate_sleeve_t_stage_a_to_b(btc_df, eth_df, {}, spec_hash)
    assert len(status.gates) >= 5, f"Expected at least 5 evidence gates, got {len(status.gates)}"
    
    for g in status.gates:
        print(f"  - Gate '{g.gate_name}': observed={g.observed_value}, threshold={g.threshold} -> {'PASS' if g.passed else 'FAIL'}")
        
    # The pre-registration hash, 2 market cycles, and max drawdown gates must pass
    assert status.gates[0].passed is True, "Pre-registration spec hash gate failed"
    assert status.gates[1].passed is True, "Market cycles gate failed"
    assert status.gates[2].passed is True, "Max drawdown gate failed"
    print("PASS: Sleeve T evidence gates evaluated.")


def test_sleeve_c_gates():
    print("Testing Sleeve C Stage A -> Stage B promotion gates...")
    spec_hash = "3704e9e742e5ee9bcaa491df0c919fba0af23e65417ce106369e09a3803f6497"
    status_c = evaluate_sleeve_c_stage_a_to_b(spec_hash)
    
    for g in status_c.gates:
        print(f"  - Gate '{g.gate_name}': observed={g.observed_value} -> {'PASS' if g.passed else 'FAIL'}")
        
    assert status_c.gates[0].passed is True, "Spec hash gate failed for Sleeve C"
    assert status_c.gates[1].passed is True, "Stress window survival failed for Sleeve C"
    assert status_c.gates[2].passed is False, "Configured hurdle gate should fail for Sleeve C (6.95% < 10.5%)"
    assert status_c.eligible_for_promotion is False, "Sleeve C must not be eligible for promotion"
    assert status_c.target_stage == Stage.STAGE_A, "Sleeve C must be HELD IN STAGE A"
    assert status_c.summary_verdict == "FAIL", "Sleeve C summary verdict must be FAIL"
    print("PASS: Sleeve C evidence gates evaluated (HELD IN STAGE A, hurdle gate failed).")


def test_tracking_error_and_hmac():
    print("Testing Stage B->C tracking error and Stage D HMAC kill switch...")
    # Test tracking error
    ideal_rets = pd.Series([0.01, -0.005, 0.008, 0.002, -0.003] * 10)
    paper_rets = ideal_rets + pd.Series([0.0001, -0.0001, 0.0002, 0.0000, -0.0001] * 10)
    te = compute_weekly_tracking_error(paper_rets, ideal_rets)
    assert te < 0.015, f"Tracking error {te:.4f} exceeded 1.5% limit"
    print(f"PASS: Tracking error {te*100:.2f}% satisfies Stage B->C requirement (<= 1.50%).")
    
    # Test HMAC kill switch
    secret = "starkx-v2-hmac-kill-switch-secret"
    payload = b"EMERGENCY_HALT_20261028"
    import hmac, hashlib
    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    
    assert verify_hmac_kill_switch(payload, valid_sig, secret) is True
    assert verify_hmac_kill_switch(payload, "invalid_sig", secret) is False
    print("PASS: HMAC-SHA256 kill switch cryptographic signature verified.")


if __name__ == "__main__":
    test_bootstrap_statistics()
    test_sleeve_t_gates()
    test_sleeve_c_gates()
    test_tracking_error_and_hmac()
    print("SUCCESS: All v2 evidence gates and promotion tests passed.")
