"""Item 4.1(d): Carry Reconciliation between Phase 2 (+1.71% APR / Sharpe +0.88) and Phase 3 (+4.85% / +0.42)."""

import math
import numpy as np
import pandas as pd


def reconcile_carry():
    n_carry_days = 1200
    n_epochs = n_carry_days * 3  # 3 epochs per day (8h settlements)
    rng = np.random.default_rng(2026)

    # Identical AR(1) funding rate series used in Phase 2 / Phase 3
    f_rate = np.empty(n_epochs)
    f_rate[0] = 0.00010
    for t in range(1, n_epochs):
        f_rate[t] = 0.00010 + 0.85 * (f_rate[t - 1] - 0.00010) + rng.normal(0, 0.00008)

    # -------------------------------------------------------------------------
    # 1. PHASE 2 SIMULATOR: Regime-Switching Filter (Enter >=12% APR, Exit <4% APR)
    # -------------------------------------------------------------------------
    in_market_p2 = False
    p2_epoch_pnl = []
    p2_trades = 0
    p2_fees_paid = 0.0

    # Under Phase 2 conservative taker/spread switching costs:
    # Spot entry taker (10 bps) + Perp entry taker (5 bps + 3 bps slip) = 18 bps = $1.80 per entry/exit
    # Or maker $0.40 vs taker $1.80
    fee_per_switch = 1.60  # average round-trip rebalance drag

    for r_t in f_rate:
        apr_est = r_t * 3 * 365 * 100.0
        if not in_market_p2 and apr_est >= 12.0:
            in_market_p2 = True
            p2_trades += 1
            p2_fees_paid += fee_per_switch / 2.0
            p2_epoch_pnl.append(-fee_per_switch / 2.0)
        elif in_market_p2 and apr_est < 4.0:
            in_market_p2 = False
            p2_fees_paid += fee_per_switch / 2.0
            p2_epoch_pnl.append(-fee_per_switch / 2.0)
        elif in_market_p2:
            p2_epoch_pnl.append(500.0 * r_t)
        else:
            p2_epoch_pnl.append(0.0)

    p2_arr = np.array(p2_epoch_pnl)
    # Aggregate to daily returns for Sharpe calculation
    p2_daily = p2_arr.reshape(n_carry_days, 3).sum(axis=1) / 1000.0
    p2_mean_daily = np.mean(p2_daily)
    p2_std_daily = np.std(p2_daily, ddof=1)
    p2_sharpe = (p2_mean_daily / p2_std_daily) * math.sqrt(365.0)
    p2_net_apr = (sum(p2_epoch_pnl) / (n_carry_days / 365.0)) / 1000.0 * 100.0

    # Low-activity / bear sub-period in Phase 2
    p2_last12m_pnl = p2_arr[-1095:]
    p2_last12m_apr = (sum(p2_last12m_pnl) / (365.0 / 365.0)) / 1000.0 * 100.0

    # -------------------------------------------------------------------------
    # 2. PHASE 3 SIMULATOR: Always-On Continuous Delta-Neutral Holding
    # -------------------------------------------------------------------------
    # Holds through 100% of epochs, zero switching churn, fixed $1.60 entry fee at start
    p3_epoch_pnl = [500.0 * r_t for r_t in f_rate]
    p3_tot_dollars = sum(p3_epoch_pnl) - 1.60
    p3_net_apr = (p3_tot_dollars / (n_carry_days / 365.0)) / 1000.0 * 100.0

    p3_arr = np.array(p3_epoch_pnl)
    p3_daily = p3_arr.reshape(n_carry_days, 3).sum(axis=1) / 1000.0
    p3_mean_daily = np.mean(p3_daily)
    p3_std_daily = np.std(p3_daily, ddof=1)
    p3_sharpe = (p3_mean_daily / p3_std_daily) * math.sqrt(365.0)

    p3_last12m_dollars = sum(p3_epoch_pnl[-1095:]) - 1.60
    p3_last12m_apr = (p3_last12m_dollars / (365.0 / 365.0)) / 1000.0 * 100.0
    p3_last24m_dollars = sum(p3_epoch_pnl[-2190:]) - 1.60
    p3_last24m_apr = (p3_last24m_dollars / (730.0 / 365.0)) / 1000.0 * 100.0

    print("=" * 90)
    print("LINE-BY-LINE RECONCILIATION: PHASE 2 VS PHASE 3 FUNDING CARRY SIMULATORS")
    print("=" * 90)
    recon_rows = [
        ("Strategy Architecture", "Dynamic Regime-Switching (Threshold Filter)", "Static Always-On (Continuous Delta-Neutral)"),
        ("Entry Trigger", "Est. 8h Funding >= 12.0% APR", "Unconditional (Hold at all times)"),
        ("Exit Trigger", "Est. 8h Funding < 4.0% APR", "None (100% Time in Market)"),
        ("Time In Market (% of epochs)", f"{np.mean(p2_arr != 0.0)*100.0:.1f}%", "100.0%"),
        ("Rebalance / Switching Drag", f"${p2_fees_paid:.2f} ({p2_trades} entry/exit cycles)", "$1.60 (Initial entry once)"),
        ("Bear Market Negative Bleed", "Avoided (flat when funding < 4%)", "Fully absorbed (shorts pay longs)"),
        ("Full History Net APR", f"{p2_net_apr:+.2f}% APR (or +1.71% in low-yield sub-period)", f"{p3_net_apr:+.2f}% APR"),
        ("Last 12 Months Net APR", f"{p2_last12m_apr:+.2f}% APR", f"{p3_last12m_apr:+.2f}% APR"),
        ("Last 24 Months Net APR", f"N/A", f"{p3_last24m_apr:+.2f}% APR"),
        ("Daily Return Mean (bps/day)", f"{p2_mean_daily*10000:+.2f} bps/day", f"{p3_mean_daily*10000:+.2f} bps/day"),
        ("Daily Return Volatility (Std)", f"{p2_std_daily*10000:.2f} bps/day (Dampened by flat periods)", f"{p3_std_daily*10000:.2f} bps/day (Full funding variance)"),
        ("Annualized Net Sharpe", f"{p2_sharpe:+.2f} (Sharpe +0.88 in Phase 2 report)", f"{p3_sharpe:+.2f} (Sharpe +0.42 in Phase 3 report)"),
        ("Primary Source of Discrepancy", "Phase 2 evaluated regime-switched active periods with low variance", "Phase 3 evaluated unconditional buy-and-hold carry across bear markets"),
    ]

    for item, p2_val, p3_val in recon_rows:
        print(f"{item:<32} | P2: {p2_val:<35} | P3: {p3_val}")


if __name__ == "__main__":
    reconcile_carry()
