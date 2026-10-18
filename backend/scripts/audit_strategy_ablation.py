"""Phase 5 & 6 Strategy Confluence Ablation & ML Validation Script."""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from app import db

def load_confluence_data():
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                s.id, s.symbol, coalesce(s.market, 'crypto') as market, s.interval, 
                s.label, s.composite, s.confidence, s.agreement,
                s.win_prob, s.meta_p, s.ev_r,
                coalesce(s.regime, 'unknown') as regime,
                coalesce(s.strategy, 'core') as strategy,
                s.shadow,
                f.trend, f.momentum, f.volatility, f.structure,
                f.flow, f.sentiment, f.macro, f.consensus,
                o.result, o.pnl, o.bars_held
            FROM signals s
            JOIN outcomes o ON o.signal_id = s.id
            JOIN factor_logs f ON f.signal_id = s.id
            WHERE o.result IS NOT NULL AND o.pnl IS NOT NULL;
        """)
        cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)

    # Cast numeric columns
    numeric_cols = [
        'composite', 'confidence', 'agreement', 'win_prob', 'meta_p', 'ev_r',
        'trend', 'momentum', 'volatility', 'structure', 'flow', 'sentiment', 'macro', 'consensus', 'pnl'
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    df['is_win'] = (df['pnl'] > 0).astype(int)
    df['direction'] = df['label'].apply(lambda x: 'long' if 'Buy' in x else ('short' if 'Sell' in x else 'flat'))
    return df

def analyze_factor_predictive_power(df):
    core_longs = df[(df['strategy'] == 'core') & (~df['shadow']) & (df['direction'] == 'long')].copy()
    factors = ['trend', 'momentum', 'volatility', 'structure', 'flow', 'sentiment', 'macro', 'consensus', 'composite', 'confidence', 'agreement']
    
    records = []
    for f in factors:
        valid = core_longs[[f, 'pnl', 'is_win']].dropna()
        n = len(valid)
        if n < 10:
            continue
        corr_pnl = valid[f].rank().corr(valid['pnl'].rank())
        corr_win = valid[f].corr(valid['is_win'])
        
        # Average return when factor is strongly bullish (> 30) vs neutral/bearish (<= 30)
        high_group = valid[valid[f] > 30]
        low_group = valid[valid[f] <= 30]
        wr_high = high_group['is_win'].mean() if len(high_group) else np.nan
        wr_low = low_group['is_win'].mean() if len(low_group) else np.nan
        pnl_high = high_group['pnl'].mean() * 1000.0 if len(high_group) else np.nan
        pnl_low = low_group['pnl'].mean() * 1000.0 if len(low_group) else np.nan

        records.append({
            "Factor": f,
            "Sample (N)": n,
            "Spearman (PnL)": round(corr_pnl, 4) if pd.notna(corr_pnl) else 0.0,
            "PointBiserial (Win)": round(corr_win, 4) if pd.notna(corr_win) else 0.0,
            "WinRate (f > 30)": f"{wr_high*100:.1f}%" if pd.notna(wr_high) else "N/A",
            "WinRate (f <= 30)": f"{wr_low*100:.1f}%" if pd.notna(wr_low) else "N/A",
            "Avg PnL (f > 30)": f"${pnl_high:.2f}" if pd.notna(pnl_high) else "N/A",
            "Avg PnL (f <= 30)": f"${pnl_low:.2f}" if pd.notna(pnl_low) else "N/A",
        })
    return pd.DataFrame(records)

def conviction_tier_analysis(df):
    core_longs = df[(df['strategy'] == 'core') & (~df['shadow']) & (df['direction'] == 'long')].copy()
    # Bins for composite score: 20-40, 40-60, 60-80, 80-100
    bins = [20, 40, 60, 80, 100]
    labels = ['20-40 (Low)', '40-60 (Moderate)', '60-80 (High)', '80-100 (Very High)']
    core_longs['conviction_bin'] = pd.cut(core_longs['composite'].abs(), bins=bins, labels=labels)
    
    res = []
    for b_label, grp in core_longs.groupby('conviction_bin', observed=False):
        n = len(grp)
        if n == 0:
            continue
        wr = grp['is_win'].mean()
        pnl = grp['pnl'].sum() * 1000.0
        exp = grp['pnl'].mean() * 1000.0
        res.append({
            "Conviction Bin": b_label,
            "Trades": n,
            "Win Rate": f"{wr*100:.1f}%",
            "Net P&L ($1k)": f"${pnl:.2f}",
            "Expectancy ($)": f"${exp:.2f}",
        })
    return pd.DataFrame(res)

def meta_model_audit(df):
    core = df[(df['strategy'] == 'core') & (~df['shadow'])].copy()
    valid = core[['win_prob', 'meta_p', 'pnl', 'is_win']].dropna()
    n = len(valid)
    if n == 0:
        return "No meta_p records found"
    
    auc_base = valid['win_prob'].corr(valid['is_win'])
    auc_meta = valid['meta_p'].corr(valid['is_win'])
    brier_base = ((valid['win_prob'] - valid['is_win']) ** 2).mean()
    brier_meta = ((valid['meta_p'] - valid['is_win']) ** 2).mean()
    
    return {
        "Sample Size": n,
        "Base Win Prob Correlation with Outcome": round(auc_base, 4),
        "Meta P Correlation with Outcome": round(auc_meta, 4),
        "Base Brier Score (lower is better)": round(brier_base, 4),
        "Meta Brier Score (lower is better)": round(brier_meta, 4),
        "Mean Base Win Prob": round(valid['win_prob'].mean(), 4),
        "Mean Meta P": round(valid['meta_p'].mean(), 4),
        "Percent Pegged to >= 0.95": f"{(valid['meta_p'] >= 0.95).mean()*100:.1f}%",
    }

if __name__ == "__main__":
    df = load_confluence_data()
    print("=== 1. PREDICTIVE CORRELATION OF CONFLUENCE FACTORS (Crypto Longs) ===")
    factor_df = analyze_factor_predictive_power(df)
    print(factor_df.to_string(index=False))

    print("\n=== 2. CONVICTION SCORE VS NET RETURNS ===")
    tier_df = conviction_tier_analysis(df)
    print(tier_df.to_string(index=False))

    print("\n=== 3. META-MODEL VALIDATION & CALIBRATION METRICS ===")
    meta_res = meta_model_audit(df)
    for k, v in meta_res.items():
        print(f"  {k}: {v}")
