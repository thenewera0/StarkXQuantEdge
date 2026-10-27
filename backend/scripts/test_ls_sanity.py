"""Unit tests for Long/Short sanity, Sharpe consistency, and Drawdown calculations (Phase 3.0b)."""

import math
import numpy as np

def compute_ls_metrics(returns: np.ndarray, periods_per_year: float):
    """Computes mean, std, annualized Sharpe, cumulative net, and max drawdown."""
    n = len(returns)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    
    mean_ret = float(np.mean(returns))
    std_ret = float(np.std(returns, ddof=1)) if n > 1 else 1e-9
    sharpe = (mean_ret / std_ret * math.sqrt(periods_per_year)) if std_ret > 1e-9 else 0.0
    
    cum_path = np.cumsum(returns)
    cum_net = float(cum_path[-1])
    peak = np.maximum.accumulate(cum_path)
    drawdowns = cum_path - peak
    max_dd = float(np.min(drawdowns))
    
    return mean_ret, std_ret, sharpe, cum_net, max_dd


def test_sharpe_formula_identity():
    """Assert Sharpe = (mean / std) * sqrt(periods_per_year) within 1% across various periods."""
    rng = np.random.default_rng(42)
    synthetic_returns = rng.normal(loc=0.0015, scale=0.0120, size=500) # 15 bps mean, 120 bps vol
    
    for p_yr in [252.0, 365.0, 547.5, 2190.0]:
        m, s, sr, cum, mdd = compute_ls_metrics(synthetic_returns, periods_per_year=p_yr)
        expected_sr = (m / s) * math.sqrt(p_yr)
        rel_diff = abs(sr - expected_sr) / max(1e-9, abs(expected_sr))
        assert rel_diff < 0.01, f"Sharpe formula disparity {rel_diff:.4%} exceeded 1%"


def test_unit_invariance_bps_vs_fraction():
    """Assert Sharpe ratio is completely invariant to units (bps vs fractional decimal)."""
    returns_frac = np.array([0.0010, -0.0005, 0.0020, 0.0015, -0.0010, 0.0030])
    returns_bps = returns_frac * 10000.0
    
    _, _, sr_frac, _, _ = compute_ls_metrics(returns_frac, periods_per_year=365.0)
    _, _, sr_bps, _, _ = compute_ls_metrics(returns_bps, periods_per_year=365.0)
    
    assert abs(sr_frac - sr_bps) < 1e-9, f"Unit error: sr_frac={sr_frac} vs sr_bps={sr_bps}"


def test_drawdown_cumulative_consistency():
    """Assert max drawdown is strictly consistent with cumulative return trajectory."""
    # Constructed known path:
    # returns: [+5, +5, -4, -3, +2, -8, +1]
    # cum:     [+5, +10, +6, +3, +5, -3, -2]
    # peak:    [+5, +10, +10, +10, +10, +10, +10]
    # dd:      [ 0,   0, -4,  -7, -5, -13, -12]
    # max_dd:  -13
    returns = np.array([5.0, 5.0, -4.0, -3.0, 2.0, -8.0, 1.0])
    m, s, sr, cum_net, max_dd = compute_ls_metrics(returns, periods_per_year=365.0)
    
    assert cum_net == -2.0, f"Expected cumulative net -2.0, got {cum_net}"
    assert max_dd == -13.0, f"Expected max drawdown -13.0, got {max_dd}"
    assert max_dd <= 0.0, "Max drawdown cannot be positive"


def test_known_synthetic_reversal():
    """Assert that forward reversal properly captures known negative autocorrelation."""
    # Known AR(1) process with negative autocorrelation phi = -0.50
    rng = np.random.default_rng(101)
    n = 1000
    p = np.empty(n)
    p[0] = 0.0
    for t in range(1, n):
        p[t] = -0.50 * p[t - 1] + rng.normal(0, 1.0)
        
    # Today's signal: p[t]
    # Tomorrow's forward return: p[t+1] - p[t]
    # Strategy: long when p[t] < 0, short when p[t] > 0
    signals = -np.sign(p[:-1])
    fwd_ret = np.diff(p)
    strat_ret = signals * fwd_ret
    
    m, s, sr, cum_net, max_dd = compute_ls_metrics(strat_ret, periods_per_year=365.0)
    assert m > 0.0, "Reversal on negative AR(1) should have positive gross return"
    assert sr > 0.0, "Reversal on negative AR(1) should have positive Sharpe"


if __name__ == "__main__":
    test_sharpe_formula_identity()
    test_unit_invariance_bps_vs_fraction()
    test_drawdown_cumulative_consistency()
    test_known_synthetic_reversal()
    print("ALL LS SANITY UNIT TESTS PASSED SUCCESSFULLY.")
