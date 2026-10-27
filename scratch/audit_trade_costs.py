import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv("backend/.env")

import pandas as pd
import numpy as np
from app import db
from app.costs import trade_cost, cost_in_r, _crypto_tier, _CRYPTO_TIERS

print("Fetching trades from database...")
with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id as signal_id, s.symbol, coalesce(s.market, 'crypto') as market,
               s.interval, coalesce(s.strategy, 'core') as strategy,
               s.regime, s.label, s.entry, s.stop, s.target, s.atr,
               o.id as outcome_id, o.result, o.pnl, o.r_net, o.cost_r,
               o.bars_held, o.resolved_at
        from signals s
        left join outcomes o on o.signal_id = s.id
        where o.r_net is not null
        order by s.id asc
    """)
    df = pd.DataFrame([dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()])

for c in ['entry', 'stop', 'target', 'atr', 'pnl', 'r_net', 'cost_r', 'bars_held']:
    df[c] = pd.to_numeric(df[c], errors='coerce')

def decompose_costs(row, entry_exec="maker"):
    entry = float(row['entry']) if row['entry'] else 1.0
    stop = float(row['stop']) if row['stop'] else 0.98
    risk_dist = abs(entry - stop)
    stop_dist_pct = risk_dist / entry if entry > 0 else 0.01
    atr_val = float(row['atr']) if row['atr'] else 0.02 * entry
    atr_pct = atr_val / entry if entry > 0 else 0.02
    bars = float(row['bars_held']) if row['bars_held'] else 12.0
    
    interval = row['interval']
    if interval == '4h':
        h_hours = bars * 4.0
    elif interval == '1h':
        h_hours = bars * 1.0
    elif interval == '15m':
        h_hours = bars * 0.25
    elif interval == '1d':
        h_hours = bars * 24.0
    else:
        h_hours = bars * 4.0

    is_long = row['label'] in ('Buy', 'Strong Buy')
    dir_str = "long" if is_long else "short"
    res = row['result'] or "stop"

    # Confirmed fee model:
    # Maker: 2.0 bps (0.0002)
    # Taker: 5.0 bps (0.0005)
    # Stop slippage: 3.0 bps (0.0003)
    # Tier slippage:
    tier = _crypto_tier(row['symbol'])
    base_slip, vol_coef, spread = _CRYPTO_TIERS[tier]
    depth_slip = base_slip + vol_coef * min(max(atr_pct, 0.0), 0.15)
    taker_slip = max(depth_slip, 0.5 * spread)

    # 1. Entry leg fee & slippage
    if entry_exec == "maker":
        fee_entry = 0.0002
        slip_entry = 0.0
    else:
        fee_entry = 0.0005
        slip_entry = taker_slip

    # 2. Exit leg fee & slippage
    if res.lower() == "target":
        fee_exit = 0.0002
        slip_exit = 0.0
    else:
        fee_exit = 0.0005
        slip_exit = taker_slip + 0.0003

    # 3. Funding
    periods = h_hours / 8.0
    funding_rate = 0.0001
    funding_sign = +1.0 if is_long else -1.0 # Long pays positive rate, Short receives positive rate
    funding_pct = funding_sign * funding_rate * periods

    total_fee_pct = fee_entry + fee_exit
    total_slip_pct = slip_entry + slip_exit
    total_funding_pct = funding_pct
    total_cost_pct = max(0.0, total_fee_pct + total_slip_pct + total_funding_pct)

    fee_r = total_fee_pct / stop_dist_pct
    slip_r = total_slip_pct / stop_dist_pct
    funding_r = total_funding_pct / stop_dist_pct
    total_cost_r = total_cost_pct / stop_dist_pct

    db_r_net = float(row['r_net'])
    db_cost_r = float(row['cost_r']) if pd.notna(row['cost_r']) else 0.0
    gross_r = db_r_net + db_cost_r

    return {
        "signal_id": int(row['signal_id']),
        "symbol": row['symbol'],
        "interval": row['interval'],
        "regime": row['regime'],
        "result": res,
        "bars_held": int(bars),
        "stop_dist_pct": stop_dist_pct,
        "fee_r": fee_r,
        "slip_r": slip_r,
        "funding_r": funding_r,
        "total_cost_r": total_cost_r,
        "db_cost_r": db_cost_r,
        "gross_r": gross_r,
        "db_r_net": db_r_net,
        "r_net_recomputed": gross_r - total_cost_r,
        "comp_A_double_deduct": db_r_net - total_cost_r, # subtracting cost twice
    }

# Analyze Core 4h Longs
c4l = df[(df['strategy'] == 'core') & (df['interval'] == '4h') & (df['label'].isin(['Buy', 'Strong Buy']))].copy()
rng = np.random.default_rng(42)
sample_10_longs = c4l.iloc[rng.choice(len(c4l), size=10, replace=False)]

print("\n" + "="*80)
print("10 RANDOM CORE 4H LONG TRADES: COST DECOMPOSITION")
print("="*80)
decomp_longs = [decompose_costs(row, entry_exec="maker") for _, row in sample_10_longs.iterrows()]
df_dl = pd.DataFrame(decomp_longs)
print(df_dl[['signal_id', 'symbol', 'result', 'bars_held', 'stop_dist_pct', 'fee_r', 'slip_r', 'funding_r', 'total_cost_r', 'db_cost_r', 'gross_r', 'db_r_net', 'r_net_recomputed', 'comp_A_double_deduct']].to_string(index=False))

print("\nMean across all 191 core 4h longs:")
all_dl = [decompose_costs(row, entry_exec="maker") for _, row in c4l.iterrows()]
df_all_dl = pd.DataFrame(all_dl)
print(f"Gross R Mean:                  {df_all_dl['gross_r'].mean():+.4f} R")
print(f"DB Cost R Mean:                {df_all_dl['db_cost_r'].mean():.4f} R")
print(f"Total Cost R Mean (Confirmed): {df_all_dl['total_cost_r'].mean():.4f} R")
print(f"  Fee Component Mean R:        {df_all_dl['fee_r'].mean():.4f} R")
print(f"  Slippage Component Mean R:   {df_all_dl['slip_r'].mean():.4f} R")
print(f"  Funding Component Mean R:    {df_all_dl['funding_r'].mean():.4f} R")
print(f"DB r_net Mean (Published):     {df_all_dl['db_r_net'].mean():+.4f} R")
print(f"Correct Confirmed r_net Mean:  {df_all_dl['r_net_recomputed'].mean():+.4f} R")
print(f"Double-Deduct Mean (Phase 0.6):{df_all_dl['comp_A_double_deduct'].mean():+.4f} R")

# Analyze 10 Core Shorts and 10 Ranging Longs
core_shorts = df[(df['strategy'] == 'core') & (df['label'].isin(['Sell', 'Strong Sell']))].copy()
sample_10_shorts = core_shorts.iloc[rng.choice(len(core_shorts), size=10, replace=False)]
decomp_shorts = [decompose_costs(row, entry_exec="maker") for _, row in sample_10_shorts.iterrows()]
df_ds = pd.DataFrame(decomp_shorts)

ranging_longs = df[(df['strategy'] == 'core') & (df['interval'] == '4h') & (df['label'].isin(['Buy', 'Strong Buy'])) & (df['regime'].isin(['range', 'ranging']))].copy()
sample_10_ranging = ranging_longs.iloc[rng.choice(len(ranging_longs), size=10, replace=False)]
decomp_ranging = [decompose_costs(row, entry_exec="maker") for _, row in sample_10_ranging.iterrows()]
df_dr = pd.DataFrame(decomp_ranging)

print("\n" + "="*80)
print("10 CORE SHORTS: COST BREAKDOWN")
print("="*80)
print(df_ds[['signal_id', 'symbol', 'result', 'bars_held', 'stop_dist_pct', 'fee_r', 'slip_r', 'funding_r', 'total_cost_r', 'db_cost_r', 'gross_r', 'db_r_net', 'r_net_recomputed']].to_string(index=False))

print("\nMean across all 120 Core Shorts:")
all_ds = [decompose_costs(row, entry_exec="maker") for _, row in core_shorts.iterrows()]
df_all_ds = pd.DataFrame(all_ds)
print(f"Gross R Mean:                  {df_all_ds['gross_r'].mean():+.4f} R")
print(f"DB Cost R Mean:                {df_all_ds['db_cost_r'].mean():.4f} R")
print(f"Total Cost R Mean (Confirmed): {df_all_ds['total_cost_r'].mean():.4f} R")
print(f"  Fee Component Mean R:        {df_all_ds['fee_r'].mean():.4f} R")
print(f"  Slippage Component Mean R:   {df_all_ds['slip_r'].mean():.4f} R")
print(f"  Funding Component Mean R:    {df_all_ds['funding_r'].mean():.4f} R")
print(f"DB r_net Mean (Published):     {df_all_ds['db_r_net'].mean():+.4f} R")
print(f"Correct Confirmed r_net Mean:  {df_all_ds['r_net_recomputed'].mean():+.4f} R")

print("\n" + "="*80)
print("10 RANGING LONGS: COST BREAKDOWN")
print("="*80)
print(df_dr[['signal_id', 'symbol', 'result', 'bars_held', 'stop_dist_pct', 'fee_r', 'slip_r', 'funding_r', 'total_cost_r', 'db_cost_r', 'gross_r', 'db_r_net', 'r_net_recomputed']].to_string(index=False))

print("\nMean across all 29 Ranging Longs:")
all_dr = [decompose_costs(row, entry_exec="maker") for _, row in ranging_longs.iterrows()]
df_all_dr = pd.DataFrame(all_dr)
print(f"Gross R Mean:                  {df_all_dr['gross_r'].mean():+.4f} R")
print(f"DB Cost R Mean:                {df_all_dr['db_cost_r'].mean():.4f} R")
print(f"Total Cost R Mean (Confirmed): {df_all_dr['total_cost_r'].mean():.4f} R")
print(f"  Fee Component Mean R:        {df_all_dr['fee_r'].mean():.4f} R")
print(f"  Slippage Component Mean R:   {df_all_dr['slip_r'].mean():.4f} R")
print(f"  Funding Component Mean R:    {df_all_dr['funding_r'].mean():.4f} R")
print(f"DB r_net Mean (Published):     {df_all_dr['db_r_net'].mean():+.4f} R")
print(f"Correct Confirmed r_net Mean:  {df_all_dr['r_net_recomputed'].mean():+.4f} R")
