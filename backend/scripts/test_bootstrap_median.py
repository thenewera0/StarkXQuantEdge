"""Unit test verifying that cluster bootstrap median is within 0.1*SE of sample mean for symmetric synthetic data.

Addresses Phase 1.1.1 requirement.
"""

from __future__ import annotations
import math
import numpy as np


def cluster_bootstrap_mean(
    clusters: list[np.ndarray],
    n_boot: int = 10000,
    seed: int = 42,
) -> tuple[float, float, float, float, tuple[float, float]]:
    """Unbiased cluster bootstrap for trade-level mean with unequal cluster sizes.

    For K clusters with trades {X_{ij}}, sample mean is:
        X_bar = (1/N) * sum_i sum_j X_{ij}

    Resampling K clusters with replacement S* gives resample mean:
        X_bar* = sum_{i in S*} sum_j X_{ij} / N_total

    Because E[X_bar*] = (1/N) * sum_{i=1}^K (K/K) T_i = X_bar, the bootstrap mean is strictly unbiased.
    """
    k = len(clusters)
    cluster_sums = np.array([float(np.sum(c)) for c in clusters])
    cluster_sizes = np.array([len(c) for c in clusters])
    n_total = float(np.sum(cluster_sizes))
    sample_mean = float(np.sum(cluster_sums)) / n_total

    # Sample standard error of cluster mean
    all_trades = np.concatenate(clusters)
    sample_std = float(np.std(all_trades, ddof=1)) if len(all_trades) > 1 else 1e-9
    se_approx = sample_std / math.sqrt(k)

    rng = np.random.default_rng(seed)
    # Resample cluster sums
    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(k, size=k, replace=True)
        boot_means[b] = np.sum(cluster_sums[idx]) / n_total

    boot_mean = float(np.mean(boot_means))
    boot_median = float(np.median(boot_means))
    ci_95 = (float(np.percentile(boot_means, 2.5)), float(np.percentile(boot_means, 97.5)))

    return sample_mean, se_approx, boot_mean, boot_median, ci_95


def test_bootstrap_median_on_symmetric_synthetic():
    rng = np.random.default_rng(101)
    k = 40
    # Symmetric normal distribution with unequal cluster sizes
    clusters = [rng.normal(loc=0.50, scale=1.0, size=rng.integers(2, 25)) for _ in range(k)]

    sample_mean, se, boot_mean, boot_median, ci = cluster_bootstrap_mean(clusters, n_boot=10000, seed=42)

    diff = abs(boot_median - sample_mean)
    threshold = 0.10 * se

    print(f"Sample Mean:     {sample_mean:.5f}")
    print(f"Cluster SE:      {se:.5f}")
    print(f"Bootstrap Mean:  {boot_mean:.5f}")
    print(f"Bootstrap Median:{boot_median:.5f}")
    print(f"|Median - Mean|: {diff:.5f}")
    print(f"0.10 * SE:       {threshold:.5f}")
    print(f"CI 95%:          [{ci[0]:.5f}, {ci[1]:.5f}]")

    assert diff <= threshold, f"Bootstrap median {boot_median} deviates from sample mean {sample_mean} by {diff} > {threshold}"
    print("SUCCESS: Bootstrap median is within 0.1*SE of sample mean. Test passed.")


if __name__ == "__main__":
    test_bootstrap_median_on_symmetric_synthetic()
