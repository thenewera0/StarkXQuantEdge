"""Phase 4 Transaction Cost Sensitivity & Execution Realism Analysis."""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from app import db

def load_crypto_longs():
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                s.id, s.symbol, s.interval, s.entry, s.stop, s.target,
                o.result, o.pnl, o.bars_held, s.atr, s.price
            FROM signals s
            JOIN outcomes o ON o.signal_id = s.id
            WHERE coalesce(s.market, 'crypto') = 'crypto'
              AND s.label IN ('Buy', 'Strong Buy')
              AND s.shadow = false
              AND o.result IS NOT NULL AND o.pnl IS NOT NULL;
        """)
        cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)

    df['entry'] = df['entry'].astype(float)
    df['stop'] = df['stop'].astype(float)
    df['pnl'] = df['pnl'].astype(float)
    # Recover gross return: current pnl has ~0.04% maker cost deducted
    # gross_return = pnl + 0.0004
    df['gross_ret'] = df['pnl'] + 0.0004
    df['stop_frac'] = (df['entry'] - df['stop']).abs() / df['entry']
    return df

def run_cost_scenarios():
    df = load_crypto_longs()
    n = len(df)
    
    scenarios = {
        "Gross (Zero Costs)": 0.0,
        "Optimistic Maker (0.04% RT)": 0.0004,
        "Base Case (Maker entry + Taker stop: 0.09% RT)": 0.0009,
        "Adverse Taker (Full taker + slippage: 0.20% RT)": 0.0020,
        "Extreme Stress (Wide spread + slippage: 0.40% RT)": 0.0040,
    }

    results = []
    notional = 1000.0

    for name, rt_cost in scenarios.items():
        net_ret = df['gross_ret'] - rt_cost
        wins = net_ret > 0
        losses = net_ret <= 0
        w_cnt = wins.sum()
        l_cnt = losses.sum()
        wr = w_cnt / n
        
        gross_profit = net_ret[wins].sum() * notional
        gross_loss = abs(net_ret[losses].sum() * notional)
        pf = gross_profit / gross_loss if gross_loss != 0 else float('inf')
        
        net_pnl = net_ret.sum() * notional
        exp_usd = net_pnl / n
        
        r_mult = net_ret / df['stop_frac']
        total_r = r_mult.sum()
        mean_r = r_mult.mean()

        results.append({
            "Scenario": name,
            "RT Cost (bps)": int(rt_cost * 10000),
            "Win Rate": f"{wr*100:.1f}%",
            "Net P&L ($1k)": f"${net_pnl:.2f}",
            "Profit Factor": f"{pf:.2f}",
            "Expectancy ($)": f"${exp_usd:.2f}",
            "Total R": f"{total_r:.2f} R",
            "Mean R": f"{mean_r:.4f} R",
        })

    # Break-even transaction cost calculation
    # Sum(gross_ret - cost) = 0 => cost = mean(gross_ret)
    be_cost_fraction = df['gross_ret'].mean()
    be_cost_bps = be_cost_fraction * 10000

    print("=== TRANSACTION COST SENSITIVITY TABLE (Crypto Longs, n=162) ===")
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    print(f"\nBreak-even Round-Trip Cost: {be_cost_fraction*100:.3f}% ({be_cost_bps:.1f} bps)")

if __name__ == "__main__":
    run_cost_scenarios()
