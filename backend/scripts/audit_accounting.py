"""Comprehensive Trade-Ledger Reconciliation & Forensic Accounting Script."""

import math
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from app import db, costs
from app.config import settings

def run_accounting_audit():
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                s.id, s.symbol, coalesce(s.market, 'crypto') as market, s.interval, 
                s.label, s.entry, s.stop, s.target, s.reward_risk, s.atr, s.price,
                coalesce(s.regime, 'unknown') as regime,
                coalesce(s.strategy, 'core') as strategy,
                s.shadow,
                o.result, o.pnl, o.mfe, o.mae, o.bars_held, o.resolved_at,
                s.created_at as signal_created_at
            FROM signals s
            JOIN outcomes o ON o.signal_id = s.id
            WHERE o.result IS NOT NULL AND o.pnl IS NOT NULL
            ORDER BY o.resolved_at ASC;
        """)
        cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)

        # Also get open signals
        cur.execute("""
            SELECT s.id, s.symbol, coalesce(s.market, 'crypto') as market, s.interval, 
                   s.label, s.entry, s.stop, s.target, coalesce(s.strategy, 'core') as strategy,
                   s.shadow, s.created_at
            FROM signals s
            WHERE NOT EXISTS (SELECT 1 FROM outcomes o WHERE o.signal_id = s.id)
              AND s.entry IS NOT NULL AND s.label <> 'Neutral'
            ORDER BY s.created_at ASC;
        """)
        open_cols = [desc[0] for desc in cur.description]
        open_df = pd.DataFrame(cur.fetchall(), columns=open_cols)

    df['pnl'] = df['pnl'].astype(float)
    df['entry'] = df['entry'].astype(float)
    df['stop'] = df['stop'].astype(float)
    df['target'] = df['target'].astype(float)
    df['direction'] = df['label'].apply(lambda x: 'long' if 'Buy' in x else ('short' if 'Sell' in x else 'flat'))

    # Stop distance and R-multiple
    df['stop_frac'] = (df['entry'] - df['stop']).abs() / df['entry']
    df['r_multiple'] = np.where(df['stop_frac'] > 1e-6, df['pnl'] / df['stop_frac'], np.nan)

    # Round trip cost estimation
    def get_cost(row):
        atr_pct = (abs(float(row['atr'])) / float(row['price'])) if (row['atr'] and row['price']) else 0.02
        exec_mode = "maker" if settings.limit_orders_enabled else "taker"
        if row['strategy'] == 'flash':
            exec_mode = settings.flash_execution
        return costs.round_trip_cost(row['market'], row['symbol'], atr_pct, exec_mode)

    df['est_cost_frac'] = df.apply(get_cost, axis=1)
    df['gross_pnl_frac'] = df['pnl'] + df['est_cost_frac']

    return df, open_df

def detailed_group_breakdown(core_df, group_col):
    out = []
    for val, grp in core_df.groupby(group_col):
        n = len(grp)
        wins = grp[grp['pnl'] > 0]
        losses = grp[grp['pnl'] <= 0]
        w_cnt = len(wins)
        l_cnt = len(losses)
        wr = w_cnt / n if n else 0.0
        pnl_usd = grp['pnl'].sum() * 1000.0
        gross_w = wins['pnl'].sum() * 1000.0
        gross_l = losses['pnl'].sum() * 1000.0
        pf = abs(gross_w / gross_l) if gross_l != 0 else float('inf')
        total_r = grp['r_multiple'].sum()
        mean_r = grp['r_multiple'].mean()
        avg_w = wins['pnl'].mean() * 1000.0 if w_cnt else 0.0
        avg_l = losses['pnl'].mean() * 1000.0 if l_cnt else 0.0
        out.append({
            group_col: val,
            "trades": n,
            "wins": w_cnt,
            "losses": l_cnt,
            "win_rate": round(wr, 4),
            "pnl_usd": round(pnl_usd, 2),
            "profit_factor": round(pf, 2),
            "avg_win_usd": round(avg_w, 2),
            "avg_loss_usd": round(avg_l, 2),
            "total_r": round(total_r, 2),
            "mean_r": round(mean_r, 4),
        })
    res_df = pd.DataFrame(out)
    return res_df.sort_values(by="pnl_usd", ascending=False)

def simulate_compounded_equity(core_df, start_equity=1000.0, risk_pct=0.0075):
    """Simulate equity curve if risking exactly risk_pct of current equity per trade."""
    equity = start_equity
    history = [equity]
    for _, row in core_df.iterrows():
        r_mult = row['r_multiple']
        if pd.isna(r_mult):
            history.append(equity)
            continue
        dollar_risk = equity * risk_pct
        trade_pnl_usd = dollar_risk * r_mult
        equity += trade_pnl_usd
        history.append(equity)
    return history

if __name__ == "__main__":
    df, open_df = run_accounting_audit()
    core = df[(df['strategy'] == 'core') & (~df['shadow'])].copy()
    
    print("==================================================")
    print("1. BREAKDOWN BY MARKET (Core non-shadow)")
    print(detailed_group_breakdown(core, "market").to_string(index=False))

    print("\n==================================================")
    print("2. BREAKDOWN BY DIRECTION (Core non-shadow)")
    print(detailed_group_breakdown(core, "direction").to_string(index=False))

    print("\n==================================================")
    print("3. BREAKDOWN BY MARKET x DIRECTION (Core non-shadow)")
    core['mkt_dir'] = core['market'] + " " + core['direction']
    print(detailed_group_breakdown(core, "mkt_dir").to_string(index=False))

    print("\n==================================================")
    print("4. BREAKDOWN BY REGIME (Core non-shadow)")
    print(detailed_group_breakdown(core, "regime").to_string(index=False))

    print("\n==================================================")
    print("5. BREAKDOWN BY TIMEFRAME (Core non-shadow)")
    print(detailed_group_breakdown(core, "interval").to_string(index=False))

    print("\n==================================================")
    print("6. TOP 10 PROFITABLE SYMBOLS (Core non-shadow)")
    sym_df = detailed_group_breakdown(core, "symbol")
    print(sym_df.head(10).to_string(index=False))

    print("\n==================================================")
    print("7. TOP 10 LOSING SYMBOLS (Core non-shadow)")
    print(sym_df.tail(10).to_string(index=False))

    print("\n==================================================")
    print("8. COMPOUNDED EQUITY SIMULATION ($1,000 account, 0.75% risk)")
    comp_eq = simulate_compounded_equity(core, start_equity=1000.0, risk_pct=0.0075)
    final_eq = comp_eq[-1]
    peak_eq = max(comp_eq)
    dd_comp = [(eq - pk) / pk for eq, pk in zip(comp_eq, pd.Series(comp_eq).cummax())]
    max_dd_comp = min(dd_comp)
    print(f"Starting Equity: $1,000.00")
    print(f"Final Compounded Equity: ${final_eq:.2f} (Total Return: {(final_eq/1000.0 - 1)*100:.2f}%)")
    print(f"Peak Equity: ${peak_eq:.2f}")
    print(f"Max Compounded Drawdown: {max_dd_comp*100:.2f}%")

    print("\n==================================================")
    print("9. FIXED RISK SIMULATION ($7.50 fixed R per trade)")
    fixed_r_pnl = core['r_multiple'].sum() * 7.50
    print(f"Total R: {core['r_multiple'].sum():.2f} R")
    print(f"Net P&L at $7.50/R: ${fixed_r_pnl:.2f}")

    print("\n==================================================")
    print("10. ESTIMATED FEES & SLIPPAGE DEDUCTIONS")
    total_cost_usd = (core['est_cost_frac'] * 1000.0).sum()
    gross_pnl_usd = (core['gross_pnl_frac'] * 1000.0).sum()
    net_pnl_usd = (core['pnl'] * 1000.0).sum()
    print(f"Gross P&L ($1,000 notional): ${gross_pnl_usd:.2f}")
    print(f"Modelled Round-Trip Costs: ${total_cost_usd:.2f}")
    print(f"Net Realized P&L: ${net_pnl_usd:.2f}")
    print(f"Costs as % of Gross Profit: {total_cost_usd / (core[core['pnl'] > 0]['pnl'].sum() * 1000.0) * 100:.2f}%")
