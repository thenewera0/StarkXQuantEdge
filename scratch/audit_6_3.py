"""Forensic script for 6.3: Market composition of core_4h_long_all (stored vs unique) and crypto-only unique stats."""

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
               s.label, s.as_of, o.r_net, o.pnl
        from signals s
        join outcomes o on o.signal_id = s.id
        where s.strategy = 'core' and s.interval = '4h' and s.label in ('Buy', 'Strong Buy') and o.r_net is not null
        order by s.id asc
    """)
    signals = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]

df = pd.DataFrame(signals)
df['r_net'] = df['r_net'].astype(float)
df['pnl'] = df['pnl'].astype(float)
df['direction'] = 'long'

def to_bar_open(as_of, interval):
    td = timedelta(hours=4)
    clean_close = as_of + timedelta(milliseconds=1000 - as_of.microsecond // 1000) if as_of.microsecond > 500000 else as_of
    return clean_close - td

df['bar_open_time'] = df.apply(lambda r: to_bar_open(r['as_of'], r['interval']), axis=1)
df['fingerprint'] = list(zip(df['symbol'], df['interval'], df['strategy'], df['direction'], df['bar_open_time']))

print("=" * 80)
print("6.3 MARKET COMPOSITION (CORE_4H_LONG_ALL)")
print("=" * 80)

# Stored (n=191)
stored_by_market = {}
for m, grp in df.groupby('market'):
    stored_by_market[m] = {
        'n': len(grp),
        'sum_r': grp['r_net'].sum(),
        'mean_r': grp['r_net'].mean(),
        'pnl': grp['pnl'].sum()
    }

# Unique (n=184)
df_u = df.sort_values(by='id').drop_duplicates(subset=['fingerprint'], keep='first').copy()
unique_by_market = {}
for m, grp in df_u.groupby('market'):
    unique_by_market[m] = {
        'n': len(grp),
        'sum_r': grp['r_net'].sum(),
        'mean_r': grp['r_net'].mean(),
        'pnl': grp['pnl'].sum()
    }

print(f"{'Market':12s} | {'Stored n':8s} | {'Unique n':8s} | {'Stored Sum R':12s} | {'Unique Sum R':12s} | {'Stored Mean R':13s} | {'Unique Mean R':13s}")
print("-" * 90)
all_markets = sorted(list(set(stored_by_market.keys()) | set(unique_by_market.keys())))
for m in all_markets:
    s_m = stored_by_market.get(m, {'n': 0, 'sum_r': 0.0, 'mean_r': 0.0, 'pnl': 0.0})
    u_m = unique_by_market.get(m, {'n': 0, 'sum_r': 0.0, 'mean_r': 0.0, 'pnl': 0.0})
    print(f"{m:12s} | {s_m['n']:8d} | {u_m['n']:8d} | {s_m['sum_r']:+12.4f} | {u_m['sum_r']:+12.4f} | {s_m['mean_r']:+13.4f} | {u_m['mean_r']:+13.4f}")

# Crypto-only unique statistics
crypto_u = df_u[df_u['market'] == 'crypto'].copy()
crypto_u['date'] = pd.to_datetime(crypto_u['as_of']).dt.date
dates = crypto_u['date'].unique()
date_groups = {d: crypto_u[crypto_u['date'] == d]['r_net'].values for d in dates}

rng = np.random.default_rng(42)
boot_means = []
for _ in range(10000):
    s_dates = rng.choice(dates, size=len(dates), replace=True)
    s_r = np.concatenate([date_groups[d] for d in s_dates])
    boot_means.append(s_r.mean())

ci_l = np.percentile(boot_means, 2.5)
ci_u = np.percentile(boot_means, 97.5)
r_vals = crypto_u['r_net'].values
rho = float(np.corrcoef(r_vals[:-1], r_vals[1:])[0, 1]) if len(r_vals) > 1 else 0.0
n_eff = len(crypto_u) * (1.0 - rho) / (1.0 + rho) if abs(1.0 + rho) > 1e-6 else len(crypto_u)

print("\n" + "=" * 80)
print("CRYPTO-ONLY UNIQUE TRADES STATISTICS")
print("=" * 80)
print(f"  Trades (n):              {len(crypto_u)}")
print(f"  Sum R_net:               {crypto_u['r_net'].sum():+.4f} R")
print(f"  Mean R_net:              {crypto_u['r_net'].mean():+.4f} R")
print(f"  95% Day-Block CI:        [{ci_l:+.4f}, {ci_u:+.4f}]")
print(f"  Autocorrelation (rho):   {rho:.4f}")
print(f"  N_eff:                   {n_eff:.1f}")
print(f"  Dollar P&L:              ${crypto_u['pnl'].sum():+.2f} USD")
