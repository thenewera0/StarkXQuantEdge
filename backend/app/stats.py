"""StarkX QuantEdge: Canonical Statistical Estimators & Stationary Block Bootstrap.

Phase 8.3: Single source of truth for day_block_bootstrap across the entire codebase.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def day_block_bootstrap(
    series: pd.Series | np.ndarray | list[float],
    cluster_key: pd.Series | np.ndarray | list[any],
    B: int = 10000,
    seed: int = 17,
) -> tuple[float, float]:
    """Stationary day-block bootstrap for trade returns clustered by date.

    Resamples unique calendar dates with replacement B times, pools the trades on
    each sampled date, and returns the 2.5th and 97.5th percentiles of the bootstrap
    sample means.
    """
    s = pd.Series(series, dtype=float).reset_index(drop=True)
    c = pd.Series(cluster_key).reset_index(drop=True)

    # Clean missing values
    valid_mask = s.notna() & c.notna()
    s = s[valid_mask]
    c = c[valid_mask]

    n_trades = len(s)
    if n_trades == 0:
        return 0.0, 0.0

    unique_clusters = c.unique()
    n_clusters = len(unique_clusters)
    if n_clusters < 2:
        mean_val = round(float(s.mean()), 4)
        return mean_val, mean_val

    # Group trades by cluster
    cluster_groups = {k: s[c == k].values for k in unique_clusters}

    rng = np.random.default_rng(seed=seed)
    boot_means = np.empty(B, dtype=np.float64)

    for i in range(B):
        sampled_keys = rng.choice(unique_clusters, size=n_clusters, replace=True)
        sampled_trades = np.concatenate([cluster_groups[k] for k in sampled_keys])
        boot_means[i] = sampled_trades.mean()

    lower = round(float(np.percentile(boot_means, 2.5)), 4)
    upper = round(float(np.percentile(boot_means, 97.5)), 4)
    return lower, upper


def effective_sample_size_daily(cluster_key: pd.Series | np.ndarray | list[any]) -> int:
    """Computes effective degrees of freedom from daily cluster counts."""
    c = pd.Series(cluster_key).dropna()
    if len(c) == 0:
        return 0
    counts = c.value_counts().values
    return int(round((counts.sum() ** 2) / (counts ** 2).sum()))
