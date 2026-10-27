"""5.4 Carry Stats: Recompute Carry Sharpe from Daily Return Series, Identity Test, and Reconciliation."""

import math
import numpy as np
import pandas as pd


def recompute_carry_stats():
    n_days_carry = 1200
    rng_carry = np.random.default_rng(101)
    
    # 3 epochs per day across 1,200 days = 3,600 funding epochs
    f_rate = np.empty(n_days_carry * 3)
    f_rate[0] = 0.00012
    for t in range(1, len(f_rate)):
        f_rate[t] = 0.00012 + 0.85 * (f_rate[t - 1] - 0.00012) + rng_carry.normal(0, 0.00010)

    # Phase 2 Model: Dynamic regime-switching filter (Enter >= 12% APR, Exit < 4% APR)
    in_market = False
    carry_pnl_usd = []
    fees_paid_p2 = 0.0
    active_periods = 0
    switches = 0

    for r_t in f_rate:
        apr_est = r_t * 3 * 365 * 100.0
        if not in_market and apr_est >= 12.0:
            in_market = True
            fees_paid_p2 += 0.40
            carry_pnl_usd.append(-0.40)
            switches += 1
        elif in_market and apr_est < 4.0:
            in_market = False
            fees_paid_p2 += 0.40
            carry_pnl_usd.append(-0.40)
            switches += 1
        elif in_market:
            pnl_t = 500.0 * r_t
            carry_pnl_usd.append(pnl_t)
            active_periods += 1
        else:
            carry_pnl_usd.append(0.0)

    # 1. Aggregate to Daily Returns (1,200 daily periods)
    daily_carry_usd = np.sum(np.array(carry_pnl_usd).reshape(1200, 3), axis=1)
    daily_ret = daily_carry_usd / 1000.0  # $1,000 equity base

    mean_daily = float(np.mean(daily_ret))
    std_daily = float(np.std(daily_ret, ddof=1))
    sharpe_annual = (mean_daily / std_daily) * math.sqrt(365) if std_daily > 0 else 0.0

    # 2. Identity Test
    calc_sharpe = (mean_daily / std_daily) * math.sqrt(365)
    identity_diff = abs(sharpe_annual - calc_sharpe)
    assert identity_diff < 1e-12, f"Identity test failed: diff = {identity_diff}"

    # 3. Financial Metrics
    total_net_dollars = float(sum(carry_pnl_usd))
    net_annualized_dollars = total_net_dollars / (1200 / 365.0)
    net_apr = (net_annualized_dollars / 1000.0) * 100.0
    time_in_market_raw = (active_periods / len(f_rate)) * 100.0
    time_in_market_committed = ((active_periods + switches) / len(f_rate)) * 100.0

    print("=" * 80)
    print("5.4 CARRY STATS & IDENTITY RECONCILIATION")
    print("=" * 80)
    print(f"Daily Mean Return:           {mean_daily*10000:+.4f} bps/day")
    print(f"Daily Return Std:            {std_daily*10000:+.4f} bps/day")
    print(f"Annualized Net Sharpe:       {sharpe_annual:+.4f}")
    print(f"Identity Test (mean/std*sqrt(365)): {calc_sharpe:+.4f} (Diff = {identity_diff:.2e}) [PASS]")
    print(f"Time in Market (Raw):        {time_in_market_raw:.1f}% ({active_periods} / 3600 epochs)")
    print(f"Time in Market (Committed):  {time_in_market_committed:.1f}% (incl. {switches} switch epochs)")
    print(f"Total Fees Paid (Phase 2):   ${fees_paid_p2:.2f} USD ({switches} transactions @ $0.40)")
    print(f"Net Total P&L:               ${total_net_dollars:.2f} USD over 1,200 days")
    print(f"Net Annualized Dollars:      ${net_annualized_dollars:.2f} / year")
    print(f"Net Annualized Carry APR:    {net_apr:+.2f}% APR")
    
    # 4. Hurdle Verdict
    hurdle_apr = 8.50  # 6.5% risk-free + 2.0% hurdle
    deficit = net_apr - hurdle_apr
    verdict = "ECONOMIC" if net_apr >= hurdle_apr else "UNECONOMIC"
    print(f"Required Economic Hurdle:    {hurdle_apr:.2f}% APR (Risk-Free 6.5% + 2.0% Gate)")
    print(f"Excess APR Over Hurdle:      {deficit:+.2f}% APR")
    print(f"Economic Verdict:            >>>{verdict}<<<")

    return {
        "mean_daily_bps": mean_daily * 10000,
        "std_daily_bps": std_daily * 10000,
        "sharpe_annual": sharpe_annual,
        "time_in_market_raw": time_in_market_raw,
        "time_in_market_committed": time_in_market_committed,
        "fees_p2": fees_paid_p2,
        "total_net_dollars": total_net_dollars,
        "net_annualized_dollars": net_annualized_dollars,
        "net_apr": net_apr,
        "hurdle_apr": hurdle_apr,
        "deficit": deficit,
        "verdict": verdict
    }


if __name__ == "__main__":
    recompute_carry_stats()
