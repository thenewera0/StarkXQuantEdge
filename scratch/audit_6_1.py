"""Forensic script for 6.1: Duplicate fingerprint analysis, unique recomputations, sizing, and meta split check."""

import math
import sys
from datetime import timedelta
from pathlib import Path
import numpy as np
import pandas as pd

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")
from app import db

with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id, s.symbol, coalesce(s.market, 'crypto') as market,
               s.interval, coalesce(s.strategy, 'core') as strategy,
               s.label, s.as_of, s.created_at,
               s.entry, s.stop, s.target, s.size_pct, s.reward_risk, s.win_prob,
               s.shadow, s.price,
               o.id as outcome_id, o.r_net, o.pnl, o.cost_r, o.result, o.bars_held,
               o.resolved_at, o.mfe, o.mae
        from signals s
        left join outcomes o on o.signal_id = s.id
        order by s.id asc
    """)
    cols = [c.name for c in cur.description]
    signals = [dict(zip(cols, r)) for r in cur.fetchall()]

df = pd.DataFrame(signals)
for c in ['entry', 'stop', 'target', 'size_pct', 'reward_risk', 'win_prob', 'price', 'r_net', 'pnl', 'cost_r', 'bars_held', 'mfe', 'mae']:
    df[c] = pd.to_numeric(df[c], errors='coerce')

df['direction'] = df['label'].apply(lambda l: 'long' if 'Buy' in str(l) else ('short' if 'Sell' in str(l) else 'neutral'))

def to_bar_open(as_of, interval):
    if interval == '15m': td = timedelta(minutes=15)
    elif interval == '1h': td = timedelta(hours=1)
    elif interval == '4h': td = timedelta(hours=4)
    elif interval == '1d': td = timedelta(days=1)
    else: td = timedelta(hours=4)
    
    if as_of.microsecond > 500000:
        clean_close = as_of + timedelta(milliseconds=1000 - as_of.microsecond // 1000)
    else:
        clean_close = as_of
    return clean_close - td

df['bar_open_time'] = df.apply(lambda r: to_bar_open(r['as_of'], r['interval']), axis=1)
df['fingerprint'] = list(zip(df['symbol'], df['interval'], df['strategy'], df['direction'], df['bar_open_time']))

print("=" * 80)
print("6.1 DUPLICATE FORENSICS SUMMARY")
print("=" * 80)

# 1. ALL SIGNALS
all_n = len(df)
all_unique_fp = df['fingerprint'].nunique()
all_counts = df['fingerprint'].value_counts()
print(f"ALL SIGNALS: rows = {all_n}, unique fingerprints = {all_unique_fp}")
print(f"Distribution of copies: min = {all_counts.min()}, median = {all_counts.median()}, max = {all_counts.max()}")
print(f"Total duplicate fingerprints: {(all_counts > 1).sum()} (involving {(all_counts > 1).sum() * 2} rows)")

# Check differences in fields for duplicate fingerprints
dup_fps = all_counts[all_counts > 1].index
diff_as_of = 0
diff_entry = 0
diff_stop = 0
diff_target = 0
diff_size = 0

for fp in dup_fps:
    group = df[df['fingerprint'] == fp]
    if group['as_of'].nunique() > 1: diff_as_of += 1
    if group['entry'].nunique() > 1: diff_entry += 1
    if group['stop'].nunique() > 1: diff_stop += 1
    if group['target'].nunique() > 1: diff_target += 1
    if group['size_pct'].nunique() > 1: diff_size += 1

print(f"Duplicate pairs differences: diff_as_of={diff_as_of}/{len(dup_fps)}, diff_entry={diff_entry}/{len(dup_fps)}, diff_stop={diff_stop}/{len(dup_fps)}, diff_target={diff_target}/{len(dup_fps)}, diff_size={diff_size}/{len(dup_fps)}")

# 2. CORE_4H_LONG_ALL COHORT
c4l = df[(df['strategy'] == 'core') & (df['interval'] == '4h') & (df['direction'] == 'long') & (df['r_net'].notna())].copy()
c4l_n = len(c4l)
c4l_unique_fp = c4l['fingerprint'].nunique()
c4l_counts = c4l['fingerprint'].value_counts()
print(f"\nCORE_4H_LONG_ALL: rows = {c4l_n}, unique fingerprints = {c4l_unique_fp}")
print(f"Distribution of copies: min = {c4l_counts.min()}, median = {c4l_counts.median()}, max = {c4l_counts.max()}")

c4l_dup_fps = c4l_counts[c4l_counts > 1].index
c4l_diff_as_of = sum(c4l[c4l['fingerprint'] == fp]['as_of'].nunique() > 1 for fp in c4l_dup_fps)
c4l_diff_entry = sum(c4l[c4l['fingerprint'] == fp]['entry'].nunique() > 1 for fp in c4l_dup_fps)
c4l_diff_stop = sum(c4l[c4l['fingerprint'] == fp]['stop'].nunique() > 1 for fp in c4l_dup_fps)
c4l_diff_target = sum(c4l[c4l['fingerprint'] == fp]['target'].nunique() > 1 for fp in c4l_dup_fps)
c4l_diff_size = sum(c4l[c4l['fingerprint'] == fp]['size_pct'].nunique() > 1 for fp in c4l_dup_fps)
print(f"c4l duplicate pairs differences: diff_as_of={c4l_diff_as_of}/{len(c4l_dup_fps)}, diff_entry={c4l_diff_entry}/{len(c4l_dup_fps)}, diff_stop={c4l_diff_stop}/{len(c4l_dup_fps)}, diff_target={c4l_diff_target}/{len(c4l_dup_fps)}, diff_size={c4l_diff_size}/{len(c4l_dup_fps)}")

# 3. RECOMPUTE FOR UNIQUE TRADES ONLY (keep earliest per fingerprint, lowest id)
c4l_unique = c4l.sort_values(by='id').drop_duplicates(subset=['fingerprint'], keep='first').copy()

u_n = len(c4l_unique)
u_sum_r = c4l_unique['r_net'].sum()
u_mean_r = c4l_unique['r_net'].mean()
u_sum_pnl = c4l_unique['pnl'].sum()

# Day-block bootstrap CI (B=10,000) of trade mean:
c4l_unique['date'] = pd.to_datetime(c4l_unique['as_of']).dt.date
unique_dates = c4l_unique['date'].unique()
date_to_trades = {d: c4l_unique[c4l_unique['date'] == d]['r_net'].values for d in unique_dates}

rng = np.random.default_rng(42)
B = 10000
boot_trade_means = []
for _ in range(B):
    s_dates = rng.choice(unique_dates, size=len(unique_dates), replace=True)
    s_trades = np.concatenate([date_to_trades[d] for d in s_dates])
    boot_trade_means.append(s_trades.mean())

ci_lower = np.percentile(boot_trade_means, 2.5)
ci_upper = np.percentile(boot_trade_means, 97.5)

# N_eff via Breusch-Godfrey autocorrelation
r_series = c4l_unique['r_net'].values
rho = float(np.corrcoef(r_series[:-1], r_series[1:])[0, 1]) if len(r_series) > 1 else 0.0
n_eff = u_n * (1.0 - rho) / (1.0 + rho) if abs(1.0 + rho) > 1e-6 else u_n

print(f"\nUNIQUE TRADES ONLY RECOMPUTATION (c4l):")
print(f"  n = {u_n}")
print(f"  sum R_net = {u_sum_r:+.4f} R")
print(f"  mean R_net = {u_mean_r:+.4f} R")
print(f"  Day-block CI (B=10,000): [{ci_lower:+.4f}, {ci_upper:+.4f}]")
print(f"  Autocorrelation rho: {rho:.4f}")
print(f"  N_eff: {n_eff:.1f}")
print(f"  Dollar P&L: ${u_sum_pnl:+.2f} USD")

# Compare with stored c4l (n=191)
print(f"\nORIGINAL STORED c4l (n=191):")
print(f"  n = {c4l_n}")
print(f"  sum R_net = {c4l['r_net'].sum():+.4f} R")
print(f"  mean R_net = {c4l['r_net'].mean():+.4f} R")
print(f"  Dollar P&L = ${c4l['pnl'].sum():+.2f} USD")

# 4. SIZING & CONCURRENT EXPOSURE
# How many duplicates were sized (risk_usd > 0 or size_pct > 0) at the same time?
# Max concurrent exposure per symbol in R and in % equity
print("\n" + "=" * 80)
print("SIZING & CONCURRENT EXPOSURE ANALYSIS")
print("=" * 80)
# Check open windows for duplicate pairs
dup_rows = df[df['fingerprint'].isin(dup_fps)].copy()
dup_rows['entry_time'] = pd.to_datetime(dup_rows['as_of'])
dup_rows['exit_time'] = pd.to_datetime(dup_rows['resolved_at'])

# Check overlapping holding periods for identical symbols
concurrent_sized = []
for fp in dup_fps:
    grp = dup_rows[dup_rows['fingerprint'] == fp].sort_values(by='id')
    # check if size_pct > 0 on both
    sizes = grp['size_pct'].fillna(0.0).values
    both_sized = (sizes > 0).all()
    # check overlap
    t_start = grp['entry_time'].values
    t_end = grp['exit_time'].values
    # if both exist
    overlap = False
    if len(t_start) == 2 and pd.notna(t_end[0]) and pd.notna(t_end[1]):
        overlap = not (t_end[0] < t_start[1] or t_end[1] < t_start[0])
    concurrent_sized.append({
        'fingerprint': fp,
        'both_sized': both_sized,
        'overlap': overlap,
        'sizes': sizes,
        'r_nets': grp['r_net'].values
    })

n_both_sized = sum(1 for c in concurrent_sized if c['both_sized'])
n_both_sized_overlap = sum(1 for c in concurrent_sized if c['both_sized'] and c['overlap'])
print(f"Total duplicate fingerprints: {len(dup_fps)}")
print(f"Duplicate pairs where both had size_pct > 0: {n_both_sized}")
print(f"Duplicate pairs concurrent (overlapping in market) & sized: {n_both_sized_overlap}")

# Max concurrent exposure per symbol
# For each symbol, compute rolling concurrent position exposure
print("\nMax concurrent exposure per symbol:")
for sym in ['AVAXUSDT', 'BNBUSDT', 'BTCUSDT', 'SOLUSDT', 'ATOMUSDT', 'XLMUSDT', 'RUNEUSDT', 'GRTUSDT', 'FILUSDT']:
    sym_df = df[df['symbol'] == sym]
    print(f"  {sym}: total signals = {len(sym_df)}, max size_pct = {sym_df['size_pct'].max()}")

# 5. CHECK LEARNING / META TABLES FOR DUPLICATE ROWS ACROSS TRAIN AND TEST
print("\n" + "=" * 80)
print("META-MODEL & FACTOR LOGS SPLIT INTEGRITY")
print("=" * 80)
with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select count(*) from factor_logs
    """)
    print("Factor logs count:", cur.fetchone()[0])
    cur.execute("""
        select s.id, s.symbol, s.interval, s.strategy, s.label, s.as_of, f.signal_id
        from factor_logs f
        join signals s on s.id = f.signal_id
    """)
    f_rows = cur.fetchall()
    print("Factor logs joined to signals count:", len(f_rows))

# Check if any duplicate signals exist in factor_logs
f_sig_ids = [r[0] for r in f_rows]
f_df = df[df['id'].isin(f_sig_ids)]
f_dups = f_df[f_df.duplicated(subset=['fingerprint'], keep=False)]
print(f"Factor logs signals that belong to duplicate fingerprints: {len(f_dups)} rows ({len(f_dups) // 2} pairs)")
