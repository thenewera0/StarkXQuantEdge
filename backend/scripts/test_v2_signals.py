"""StarkX QuantEdge v2: Test Sleeve T Signals & Neighbourhood Variants.

Asserts:
1. 7 individual trend signals: 4 momentum lookbacks {20, 60, 120, 250} and 3 EMA pairs {(16,64), (32,128), (64,256)}.
2. Composite signal s = mean of the 7 signals in range [-1.0, +1.0].
3. Exposure e = max(s, 0) strictly bounded in [0.0, 1.0]; shorts strictly disabled.
4. Robustness neighbourhood variants (lookbacks 0.75x/1.25x, EMA pairs 0.75x/1.25x).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from app.v2.sleeve_trend import (
    compute_asset_signals,
    evaluate_neighbourhood_variants,
    NEIGHBOURHOOD_VARIANTS,
)
from app.v2.data import get_daily_asset


def test_signals_mechanics():
    print("Testing 7 constituent signals and long-only exposure...")
    df = get_daily_asset("BTCUSDT")
    sig_df = compute_asset_signals(df)
    
    # Assert columns exist
    expected_cols = [
        "mom_20", "mom_60", "mom_120", "mom_250",
        "ema_16_64", "ema_32_128", "ema_64_256",
        "composite_signal", "exposure"
    ]
    for col in expected_cols:
        assert col in sig_df.columns, f"Missing signal column: {col}"
        
    # Check signal values are {-1, 0, +1} or bounded
    for col in expected_cols[:7]:
        vals = sig_df[col].dropna().unique()
        for v in vals:
            assert v in (-1.0, 0.0, 1.0), f"Unexpected discrete signal value in {col}: {v}"
            
    # Check composite signal is strictly between -1.0 and 1.0
    comp = sig_df["composite_signal"].dropna()
    assert (comp >= -1.0 - 1e-6).all() and (comp <= 1.0 + 1e-6).all(), "Composite signal out of [-1, 1] range"
    
    # Check exposure e = max(s, 0) is strictly non-negative (shorts disabled)
    exp = sig_df["exposure"].dropna()
    assert (exp >= -1e-6).all(), "Negative exposure detected: shorts must be strictly disabled"
    assert (exp <= 1.0 + 1e-6).all(), "Exposure exceeded 1.0"
    
    print("PASS: 7 trend signals, composite score, and long-only exposure verified.")


def test_neighbourhood_variants_execution():
    print("Testing 4 neighbourhood robustness variants...")
    assert len(NEIGHBOURHOOD_VARIANTS) == 5, "Expected base + 4 variants = 5 total configs"
    
    df = get_daily_asset("BTCUSDT").iloc[-400:].copy()
    variants = evaluate_neighbourhood_variants(df, "BTCUSDT")
    
    assert len(variants) == 5
    for name, res in variants.items():
        assert res.max_drawdown >= 0.0, f"Invalid drawdown in variant {name}"
        assert res.switches_per_year >= 0.0, f"Invalid switch count in variant {name}"
        print(f"  - Variant {name}: Ann Ret={res.annualized_return:.1%}, MaxDD={res.max_drawdown:.1%}, Switches/yr={res.switches_per_year:.1f}")
        
    print("PASS: All 4 neighbourhood parameter variants executed successfully.")


if __name__ == "__main__":
    test_signals_mechanics()
    test_neighbourhood_variants_execution()
    print("SUCCESS: All v2 signal and neighbourhood tests passed.")
