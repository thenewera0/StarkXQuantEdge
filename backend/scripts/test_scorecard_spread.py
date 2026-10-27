"""Unit test for Fama-MacBeth IC and Quintile Spread on synthetic data of known IC.

Addresses Phase 1.1.3 requirement:
"Unit test with synthetic data of known IC (e.g. 0.03) must reproduce sign and an order-of-magnitude-correct spread."
"""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from app.research.scorecard import fama_macbeth_rank_ic, compute_quintile_spread


def test_synthetic_ic_and_spread():
    rng = np.random.default_rng(42)
    n_dates = 200
    n_symbols = 30
    dates = pd.date_range("2023-01-01", periods=n_dates, freq="4h")
    symbols = [f"SYM_{i:02d}" for i in range(n_symbols)]

    # Target positive IC = +0.05
    target_rho_pos = 0.05
    factor_matrix_pos = rng.normal(0, 1, size=(n_dates, n_symbols))
    # Return has signal + noise
    noise_pos = rng.normal(0, 1, size=(n_dates, n_symbols))
    return_matrix_pos = target_rho_pos * factor_matrix_pos + np.sqrt(1 - target_rho_pos ** 2) * noise_pos
    # Raw returns with realistic std dev ~ 1.5%
    raw_return_matrix_pos = return_matrix_pos * 0.015

    f_df_pos = pd.DataFrame(factor_matrix_pos, index=dates, columns=symbols)
    r_df_pos = pd.DataFrame(raw_return_matrix_pos, index=dates, columns=symbols)

    ic_res_pos = fama_macbeth_rank_ic(f_df_pos, r_df_pos, horizon_lags=4)
    spread_pos = compute_quintile_spread(f_df_pos, r_df_pos)

    print(f"Positive Synthetic Test: Mean IC = {ic_res_pos['mean_ic']:+.4f}, NW t = {ic_res_pos['t_stat']:+.2f}, Boot t = {ic_res_pos['t_boot']:+.2f}, Spread = {spread_pos:+.1f} bps")

    assert ic_res_pos["mean_ic"] > 0, f"Expected positive IC, got {ic_res_pos['mean_ic']}"
    assert spread_pos > 0, f"Expected positive spread, got {spread_pos}"
    # Q5 - Q1 spread for standard normal factor with IC ~ 0.05 on 1.5% vol is approx 2 * 1.4 * 0.05 * 150 bps ~ 21 bps
    assert 5.0 <= spread_pos <= 100.0, f"Spread {spread_pos} bps outside expected order-of-magnitude range [5, 100]"

    # Target negative IC = -0.05
    target_rho_neg = -0.05
    factor_matrix_neg = rng.normal(0, 1, size=(n_dates, n_symbols))
    noise_neg = rng.normal(0, 1, size=(n_dates, n_symbols))
    return_matrix_neg = target_rho_neg * factor_matrix_neg + np.sqrt(1 - target_rho_neg ** 2) * noise_neg
    raw_return_matrix_neg = return_matrix_neg * 0.015

    f_df_neg = pd.DataFrame(factor_matrix_neg, index=dates, columns=symbols)
    r_df_neg = pd.DataFrame(raw_return_matrix_neg, index=dates, columns=symbols)

    ic_res_neg = fama_macbeth_rank_ic(f_df_neg, r_df_neg, horizon_lags=4)
    spread_neg = compute_quintile_spread(f_df_neg, r_df_neg)

    print(f"Negative Synthetic Test: Mean IC = {ic_res_neg['mean_ic']:+.4f}, NW t = {ic_res_neg['t_stat']:+.2f}, Boot t = {ic_res_neg['t_boot']:+.2f}, Spread = {spread_neg:+.1f} bps")

    assert ic_res_neg["mean_ic"] < 0, f"Expected negative IC, got {ic_res_neg['mean_ic']}"
    assert spread_neg < 0, f"Expected negative spread, got {spread_neg}"
    assert -100.0 <= spread_neg <= -5.0, f"Spread {spread_neg} bps outside expected order-of-magnitude range [-100, -5]"

    print("SUCCESS: Fama-MacBeth IC and Quintile Spread reproduce sign and order of magnitude on synthetic data.")


if __name__ == "__main__":
    test_synthetic_ic_and_spread()
