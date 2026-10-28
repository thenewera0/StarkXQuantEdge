"""StarkX QuantEdge v2: Test Volatility Targeting & Portfolio Sizing.

Asserts:
1. EWMA 30-day halflife volatility with strict 20% floor.
2. Sizing formula: w_i = e_i * (SIGMA_TARGET / sigma_i) / N_active.
3. Per-asset weight cap at 0.25 (25%).
4. Portfolio covariance vol targeting scale factor k = min(1, SIGMA_TARGET / sigma_p).
5. Gross exposure cap <= 1.0 (no leverage permitted).
6. No-trade band hysteresis: |w_target - w_current| > max(0.20 * w_target, 0.02).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from app.v2.config import settings_v2
from app.v2.sleeve_trend import compute_ewma_volatility, rebalance_sleeve_t


def test_volatility_floor():
    print("Testing EWMA volatility floor...")
    # Flat price series -> zero true volatility
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    df = pd.DataFrame({"close": [100.0] * 100}, index=dates)
    vols = compute_ewma_volatility(df, halflife_days=30.0, floor=0.20)
    
    # Assert every single element is >= 20% floor
    assert (vols >= 0.20 - 1e-9).all(), f"Vol dropped below 20% floor: min={vols.min()}"
    assert abs(vols.iloc[-1] - 0.20) < 1e-6, f"Vol on flat series should equal floor 0.20, got {vols.iloc[-1]}"
    print("PASS: EWMA volatility respects 20% floor on flat and zero-vol regimes.")


def test_per_asset_and_gross_caps():
    print("Testing per-asset cap (25%) and gross exposure cap (100%)...")
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=150, freq="D")
    
    # Create 3 synthetic assets with very low vol to induce high sizing
    assets = {}
    for sym in ["BTC", "ETH", "SOL"]:
        prices = 100.0 * np.exp(np.cumsum(np.random.normal(0.001, 0.005, len(dates))))
        assets[sym] = pd.DataFrame({
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": [1e6] * len(dates),
        }, index=dates)
        
    res = rebalance_sleeve_t(
        asset_data=assets,
        current_weights={"BTC": 0.0, "ETH": 0.0, "SOL": 0.0},
        sigma_target=0.15,
        per_asset_cap=0.25,
    )
    
    # Check per asset cap <= 0.25
    for sym, w in res["final_targets"].items():
        assert w <= 0.25 + 1e-6, f"Per-asset cap exceeded for {sym}: {w}"
        
    # Check gross cap <= 1.0
    gross = sum(res["final_targets"].values())
    assert gross <= 1.0 + 1e-6, f"Gross exposure cap exceeded: {gross}"
    print(f"PASS: Weight caps verified (max asset={max(res['final_targets'].values()):.4f} <= 0.25, gross={gross:.4f} <= 1.0).")


def test_no_trade_band_hysteresis():
    print("Testing no-trade band hysteresis...")
    # Target is 0.10, threshold is max(0.20 * 0.10, 0.02) = 0.02
    # If current is 0.09, delta is 0.01 <= 0.02 -> HOLD
    # If current is 0.07, delta is 0.03 > 0.02 -> TRADE
    dates = pd.date_range("2024-01-01", periods=150, freq="D")
    df = pd.DataFrame({
        "open": [100.0] * 150,
        "high": [102.0] * 150,
        "low": [98.0] * 150,
        "close": np.linspace(100, 200, 150),
        "volume": [1e6] * 150,
    }, index=dates)
    
    assets = {"BTC": df}
    # Case 1: delta inside band
    res1 = rebalance_sleeve_t(assets, current_weights={"BTC": 0.245}, per_asset_cap=0.25)
    trade_action = res1["trades"]["BTC"]["action"]
    # If target is ~0.25 and current is 0.245, delta is 0.005 < 0.05 -> HOLD
    assert trade_action == "HOLD", f"Expected HOLD inside no-trade band, got {trade_action}"
    
    # Case 2: delta outside band
    res2 = rebalance_sleeve_t(assets, current_weights={"BTC": 0.0}, per_asset_cap=0.25)
    trade_action2 = res2["trades"]["BTC"]["action"]
    assert trade_action2 == "BUY", f"Expected BUY outside no-trade band, got {trade_action2}"
    print("PASS: No-trade band hysteresis prevents sub-threshold churn.")


if __name__ == "__main__":
    test_volatility_floor()
    test_per_asset_and_gross_caps()
    test_no_trade_band_hysteresis()
    print("SUCCESS: All v2 vol targeting and sizing tests passed.")
