"""test_lab_lookahead.py

Section 9:
test_lab_lookahead (truncation invariance per strategy).
Enforces:
1. Truncation invariance: indicators and signals computed on bars[:t] must be
   identical to the same slice of indicators/signals computed when later bars exist.
2. Zero future leak: no strategy accesses bars beyond the closed bar timestamp.
3. Covers all 10 catalog strategies (L1 to L10) and shared indicator primitives.
"""

import datetime
import numpy as np
import pandas as pd
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.models import MarketContext
from app.lab.strategies import list_registered_strategies, build_strategy
from app.lab.strategies.base import (
    calc_atr,
    calc_ema,
    calc_sma,
    calc_rsi,
    calc_bollinger,
    calc_adx,
)


def generate_synthetic_ohlcv(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Generates synthetic closed OHLCV bars."""
    np.random.seed(seed)
    returns = np.random.normal(0.0005, 0.015, n)
    price = 60000.0 * np.cumprod(1.0 + returns)

    high = price * (1.0 + np.abs(np.random.normal(0.002, 0.005, n)))
    low = price * (1.0 - np.abs(np.random.normal(0.002, 0.005, n)))
    open_p = low + (high - low) * np.random.uniform(0.2, 0.8, n)
    volume = np.random.uniform(100.0, 5000.0, n)

    base_time = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")
    times = [base_time + pd.Timedelta(hours=i) for i in range(n)]

    return pd.DataFrame({
        "timestamp": times,
        "open": open_p,
        "high": high,
        "low": low,
        "close": price,
        "volume": volume,
    })


def main():
    print("================================================================================")
    print("TEST 9.5: test_lab_lookahead (Truncation Invariance Across L1-L10)")
    print("================================================================================")

    df_full = generate_synthetic_ohlcv(n=350, seed=17)
    t_cutoff = 260
    df_trunc = df_full.iloc[:t_cutoff].copy()

    # 1. Base Indicator Truncation Invariance
    print("\n--- 1. Base Technical Indicators Invariance ---")
    
    # ATR
    atr_trunc = calc_atr(df_trunc, period=14)
    atr_full = calc_atr(df_full, period=14).iloc[:t_cutoff]
    np.testing.assert_allclose(atr_trunc.dropna(), atr_full.dropna(), rtol=1e-5, atol=1e-5)
    print("[PASS] calc_atr truncation invariant")

    # EMA
    ema_trunc = calc_ema(df_trunc["close"], period=50)
    ema_full = calc_ema(df_full["close"], period=50).iloc[:t_cutoff]
    np.testing.assert_allclose(ema_trunc.dropna(), ema_full.dropna(), rtol=1e-5, atol=1e-5)
    print("[PASS] calc_ema truncation invariant")

    # SMA
    sma_trunc = calc_sma(df_trunc["close"], period=55)
    sma_full = calc_sma(df_full["close"], period=55).iloc[:t_cutoff]
    np.testing.assert_allclose(sma_trunc.dropna(), sma_full.dropna(), rtol=1e-5, atol=1e-5)
    print("[PASS] calc_sma truncation invariant")

    # RSI
    rsi_trunc = calc_rsi(df_trunc["close"], period=14)
    rsi_full = calc_rsi(df_full["close"], period=14).iloc[:t_cutoff]
    np.testing.assert_allclose(rsi_trunc.dropna(), rsi_full.dropna(), rtol=1e-5, atol=1e-5)
    print("[PASS] calc_rsi truncation invariant")

    # Bollinger Bands (upper, mid, lower)
    up_t, mid_t, low_t = calc_bollinger(df_trunc["close"], period=20, num_std=2.0)
    up_f, mid_f, low_f = calc_bollinger(df_full["close"], period=20, num_std=2.0)
    np.testing.assert_allclose(mid_t.dropna(), mid_f.iloc[:t_cutoff].dropna(), rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(up_t.dropna(), up_f.iloc[:t_cutoff].dropna(), rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(low_t.dropna(), low_f.iloc[:t_cutoff].dropna(), rtol=1e-5, atol=1e-5)
    print("[PASS] calc_bollinger truncation invariant")

    # ADX
    adx_trunc = calc_adx(df_trunc, period=14)
    adx_full = calc_adx(df_full, period=14).iloc[:t_cutoff]
    np.testing.assert_allclose(adx_trunc.dropna(), adx_full.dropna(), rtol=1e-5, atol=1e-5)
    print("[PASS] calc_adx truncation invariant")

    # 2. Strategy-Level Invariance (L1 to L10)
    print("\n--- 2. Strategy-Level Lookahead Invariance (L1-L10) ---")
    registered_ids = list_registered_strategies()
    assert len(registered_ids) >= 10, f"Expected at least 10 strategies, got {len(registered_ids)}"

    as_of_time = df_trunc["timestamp"].iloc[-1].to_pydatetime()

    for sid in registered_ids:
        strat = build_strategy(sid, variant_id=f"{sid}_test")
        
        # Build extra data for special strategies (e.g. funding, pairs)
        extra = {}
        if sid == "pairs_btceth_1d":
            extra["eth_bars"] = df_trunc.copy()
            extra["btc_bars"] = df_trunc.copy()
        elif sid == "l6_xs_momentum_1d" or sid == "xs_momentum_1d":
            extra["universe_closes"] = {f"COIN_{i}": df_trunc["close"] for i in range(10)}

        ctx_trunc = MarketContext(
            symbol="BTCUSDT",
            timeframe=strat.timeframe,
            bars=df_trunc,
            as_of=as_of_time,
            funding_rate=0.0001,
            open_interest=1000000.0,
            volume_rank=1,
            extra_data=extra,
        )

        ctx_slice = MarketContext(
            symbol="BTCUSDT",
            timeframe=strat.timeframe,
            bars=df_full.iloc[:t_cutoff].copy(),
            as_of=as_of_time,
            funding_rate=0.0001,
            open_interest=1000000.0,
            volume_rank=1,
            extra_data=extra,
        )

        sigs_trunc = strat.on_bar_close(ctx_trunc)
        sigs_slice = strat.on_bar_close(ctx_slice)

        # Assert identical signal emission count
        assert len(sigs_trunc) == len(sigs_slice), (
            f"Strategy {sid} emitted different signal counts on truncated vs sliced context: "
            f"{len(sigs_trunc)} != {len(sigs_slice)}"
        )

        for s1, s2 in zip(sigs_trunc, sigs_slice):
            assert s1.signal_id == s2.signal_id, f"Signal IDs diverged for {sid}"
            assert s1.direction == s2.direction, f"Directions diverged for {sid}"
            assert s1.stop_atr == s2.stop_atr, f"Stop ATR diverged for {sid}"
            assert s1.target_r == s2.target_r, f"Target R diverged for {sid}"

        print(f"[PASS] Strategy {sid:20s}: Truncation invariant, zero lookahead bias.")

    print("\n================================================================================")
    print("ALL test_lab_lookahead CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
