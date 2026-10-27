"""Factor scorecard, Fama-MacBeth cross-sectional IC, Mirror Test, and Orthogonalization (Phase 1.3 & Amendment D).

Evaluates F1..F8, Composite, Agreement, and Sub-inputs against vol-normalized forward returns.
Applies Newey-West HAC t-statistics, Mirror Test (score > 0 vs score < 0),
and computes effective number of independent factors.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def newey_west_t_stat(series: np.ndarray, lags: int) -> tuple[float, float, float]:
    """Computes time-series mean, Newey-West HAC standard error, and t-statistic."""
    x = series[~np.isnan(series)]
    n = len(x)
    if n <= lags + 1:
        return 0.0, 1e-9, 0.0

    mean = float(np.mean(x))
    demeaned = x - mean

    # Gamma 0 (sample variance)
    gamma0 = float(np.mean(demeaned ** 2))

    # Weighted autocovariances
    gamma_sum = 0.0
    for l in range(1, lags + 1):
        gamma_l = float(np.mean(demeaned[l:] * demeaned[:-l]))
        weight = 1.0 - (l / (lags + 1.0))
        gamma_sum += 2.0 * weight * gamma_l

    var_hac = (gamma0 + gamma_sum) / float(n)
    se_hac = math.sqrt(max(1e-12, var_hac))
    t_stat = mean / se_hac if se_hac > 0 else 0.0

    return mean, se_hac, t_stat


def fama_macbeth_rank_ic(
    factor_panel: pd.DataFrame,
    fwd_return_panel: pd.DataFrame,
    horizon_lags: int = 4,
) -> dict[str, Any]:
    """Computes Fama-MacBeth cross-sectional Spearman rank IC time-series."""
    common_dates = factor_panel.index.intersection(fwd_return_panel.index)
    daily_ics = []
    mirror_pos_ics = []
    mirror_neg_ics = []

    for dt in common_dates:
        f_row = factor_panel.loc[dt]
        r_row = fwd_return_panel.loc[dt]

        # Valid non-nan pairs across symbols
        valid = (~f_row.isna()) & (~r_row.isna())
        if valid.sum() >= 5:
            f_vals = f_row[valid]
            r_vals = r_row[valid]

            # Overall rank IC
            ic = float(f_vals.rank().corr(r_vals.rank()))
            if not np.isnan(ic):
                daily_ics.append(ic)

            # Mirror Test: score > 0 vs score < 0
            pos_mask = f_vals > 0
            if pos_mask.sum() >= 4:
                ic_pos = float(f_vals[pos_mask].rank().corr(r_vals[pos_mask].rank()))
                if not np.isnan(ic_pos):
                    mirror_pos_ics.append(ic_pos)

            neg_mask = f_vals < 0
            if neg_mask.sum() >= 4:
                ic_neg = float(f_vals[neg_mask].rank().corr(r_vals[neg_mask].rank()))
                if not np.isnan(ic_neg):
                    mirror_neg_ics.append(ic_neg)

    ic_arr = np.array(daily_ics)
    mean_ic, se_ic, t_stat = newey_west_t_stat(ic_arr, lags=horizon_lags)

    # Day-block bootstrap for Fama-MacBeth IC (Phase 1.1.3)
    n_days = len(ic_arr)
    if n_days > 5:
        rng = np.random.default_rng(42)
        boot_ic_means = np.empty(10000)
        for b in range(10000):
            idx = rng.choice(n_days, size=n_days, replace=True)
            boot_ic_means[b] = np.mean(ic_arr[idx])
        se_boot = float(np.std(boot_ic_means, ddof=1))
        t_boot = mean_ic / se_boot if se_boot > 1e-9 else 0.0
        ci_boot_low = float(np.percentile(boot_ic_means, 2.5))
        ci_boot_high = float(np.percentile(boot_ic_means, 97.5))
    else:
        se_boot = se_ic
        t_boot = t_stat
        ci_boot_low, ci_boot_high = mean_ic - 1.96 * se_ic, mean_ic + 1.96 * se_ic

    mean_pos_ic = float(np.mean(mirror_pos_ics)) if mirror_pos_ics else 0.0
    mean_neg_ic = float(np.mean(mirror_neg_ics)) if mirror_neg_ics else 0.0

    # Effective N from autocorrelation
    if len(ic_arr) > 1:
        autocorr = float(pd.Series(ic_arr).autocorr(lag=1))
        autocorr = 0.0 if np.isnan(autocorr) else autocorr
        n_eff = len(ic_arr) * (1.0 - autocorr) / (1.0 + autocorr) if abs(autocorr) < 0.99 else len(ic_arr)
    else:
        autocorr = 0.0
        n_eff = float(len(ic_arr))

    return {
        "n_periods": len(ic_arr),
        "n_eff": max(1.0, n_eff),
        "mean_ic": mean_ic,
        "se_ic": se_ic,
        "t_stat": t_stat,
        "se_boot": se_boot,
        "t_boot": t_boot,
        "ci_boot_low": ci_boot_low,
        "ci_boot_high": ci_boot_high,
        "mirror_pos_ic": mean_pos_ic,
        "mirror_neg_ic": mean_neg_ic,
        "autocorr": autocorr,
    }


def compute_quintile_spread(
    factor_panel: pd.DataFrame,
    fwd_return_panel: pd.DataFrame,
) -> float:
    """Computes Q5 - Q1 mean raw forward return spread in basis points (Phase 1.1.3).

    Per timestamp t:
        spread_t = (mean_raw_ret(Q5) - mean_raw_ret(Q1)) * 10,000 bps
    Then returns the time-series average over timestamps.
    """
    common_dates = factor_panel.index.intersection(fwd_return_panel.index)
    timestamp_spreads = []

    for dt in common_dates:
        f_row = factor_panel.loc[dt]
        r_row = fwd_return_panel.loc[dt]
        valid = (~f_row.isna()) & (~r_row.isna())
        if valid.sum() >= 10:
            f_vals = f_row[valid]
            r_vals = r_row[valid]
            try:
                ranks = f_vals.rank(pct=True)
                q5_ret = float(r_vals[ranks >= 0.80].mean())
                q1_ret = float(r_vals[ranks <= 0.20].mean())
                if not np.isnan(q5_ret) and not np.isnan(q1_ret):
                    # Spread at timestamp dt in basis points
                    spread_t = (q5_ret - q1_ret) * 10000.0
                    timestamp_spreads.append(spread_t)
            except Exception:
                continue

    if not timestamp_spreads:
        return 0.0

    return float(np.mean(timestamp_spreads))


def compute_effective_factors(factor_corr_matrix: np.ndarray) -> float:
    """Computes effective number of independent factors N_eff = (sum lambda)^2 / sum (lambda^2)."""
    eigenvalues = np.linalg.eigvalsh(factor_corr_matrix)
    eigenvalues = np.maximum(0.0, eigenvalues)
    sum_lambda = float(np.sum(eigenvalues))
    sum_lambda_sq = float(np.sum(eigenvalues ** 2))
    if sum_lambda_sq <= 1e-12:
        return 1.0
    return (sum_lambda ** 2) / sum_lambda_sq
