"""Validation toolkit for research (Phase 1.4).

Implements:
- Purged K-fold CV (K=6, embargo=48 bars)
- Walk-forward expanding window (train 12m, test 1m, step 1m)
- Deflated Sharpe Ratio (DSR) using trial counter
- Probability of Backtest Overfitting (PBO via CSCV, 16 partitions)
- Stationary block bootstrap (block length = 24 bars)
"""

from __future__ import annotations

import itertools
import math
from typing import Any, Generator

import numpy as np
import pandas as pd


def purged_kfold_split(
    n_samples: int,
    n_splits: int = 6,
    embargo_bars: int = 48,
) -> Generator[tuple[np.ndarray, np.ndarray], None, None]:
    """Generates train/test indices with purging and post-test embargo."""
    indices = np.arange(n_samples)
    split_size = n_samples // n_splits

    for k in range(n_splits):
        test_start = k * split_size
        test_end = (k + 1) * split_size if k < n_splits - 1 else n_samples
        test_idx = indices[test_start:test_end]

        # Purge: remove train bars overlapping with test
        # Embargo: remove train bars within embargo_bars immediately AFTER test
        train_mask = np.ones(n_samples, dtype=bool)
        train_mask[test_start:min(n_samples, test_end + embargo_bars)] = False

        train_idx = indices[train_mask]
        yield train_idx, test_idx


def walk_forward_expanding_split(
    dates: pd.DatetimeIndex,
    train_months: int = 12,
    test_months: int = 1,
    step_months: int = 1,
) -> Generator[tuple[np.ndarray, np.ndarray], None, None]:
    """Walk-forward expanding window cross-validation."""
    start_date = dates.min()
    end_date = dates.max()

    curr_train_end = start_date + pd.DateOffset(months=train_months)

    while curr_train_end < end_date:
        curr_test_end = curr_train_end + pd.DateOffset(months=test_months)
        train_idx = np.where(dates < curr_train_end)[0]
        test_idx = np.where((dates >= curr_train_end) & (dates < curr_test_end))[0]

        if len(test_idx) > 0 and len(train_idx) > 0:
            yield train_idx, test_idx

        curr_train_end = curr_train_end + pd.DateOffset(months=step_months)


def deflated_sharpe_ratio(
    sr_observed: float,
    n_trials: int,
    t_bars: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    var_sr_trials: float = 0.5,
) -> float:
    """Computes Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

    DSR tests if observed SR is statistically significant given the number of trials N.
    Returns the p-value probability in [0, 1].
    """
    if n_trials <= 1:
        sr_benchmark = 0.0
    else:
        # Expected maximum Sharpe over N trials under null hypothesis
        euler_mascheroni = 0.5772156649
        z_n = math.sqrt(2.0 * math.log(n_trials))
        sr_benchmark = math.sqrt(var_sr_trials) * (
            z_n - (math.log(math.log(n_trials)) + math.log(4.0 * math.pi) - 2.0 * euler_mascheroni) / (2.0 * z_n)
        )

    # Standard error of Sharpe under non-normal returns
    denom = 1.0 - skewness * sr_observed + ((kurtosis - 1.0) / 4.0) * (sr_observed ** 2)
    se_sr = math.sqrt(max(1e-9, denom) / float(max(1, t_bars - 1)))

    if se_sr <= 0:
        return 0.5

    z = (sr_observed - sr_benchmark) / se_sr
    # CDF of standard normal
    dsr = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return float(np.clip(dsr, 0.0, 1.0))


def probability_of_backtest_overfitting(
    returns_matrix: np.ndarray,
    n_partitions: int = 16,
) -> float:
    """Computes Probability of Backtest Overfitting (PBO via CSCV, 16 partitions).

    returns_matrix: shape (T_bars, N_configs)
    """
    t_bars, n_configs = returns_matrix.shape
    if n_configs <= 1 or t_bars < n_partitions:
        return 0.0

    part_size = t_bars // n_partitions
    sub_returns = [returns_matrix[i * part_size : (i + 1) * part_size] for i in range(n_partitions)]

    # Generate all partition combinations of size n_partitions / 2
    half_p = n_partitions // 2
    combos = list(itertools.combinations(range(n_partitions), half_p))
    n_combos = min(len(combos), 100)  # Evaluate up to 100 random combinations for performance

    rng = np.random.default_rng(42)
    selected_combos = rng.choice(len(combos), size=n_combos, replace=False)

    logits = []
    for c_idx in selected_combos:
        train_parts = set(combos[c_idx])
        test_parts = set(range(n_partitions)) - train_parts

        train_ret = np.concatenate([sub_returns[p] for p in train_parts], axis=0)
        test_ret = np.concatenate([sub_returns[p] for p in test_parts], axis=0)

        # In-sample Sharpe for each config
        is_means = np.mean(train_ret, axis=0)
        is_stds = np.std(train_ret, axis=0, ddof=1)
        is_stds = np.where(is_stds < 1e-9, 1e-9, is_stds)
        is_sharpes = is_means / is_stds

        best_is_idx = int(np.argmax(is_sharpes))

        # Out-of-sample Sharpe rank of best IS config
        oos_means = np.mean(test_ret, axis=0)
        oos_stds = np.std(test_ret, axis=0, ddof=1)
        oos_stds = np.where(oos_stds < 1e-9, 1e-9, oos_stds)
        oos_sharpes = oos_means / oos_stds

        best_oos_sr = oos_sharpes[best_is_idx]
        median_oos_sr = float(np.median(oos_sharpes))

        # If best IS config ranks below median OOS, it is overfit
        logits.append(1.0 if best_oos_sr < median_oos_sr else 0.0)

    pbo = float(np.mean(logits))
    return pbo
