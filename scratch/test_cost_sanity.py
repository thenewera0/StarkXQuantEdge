import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv("backend/.env")

import pandas as pd
import numpy as np
from app import db
from app.costs import trade_cost

print("Connecting to DB...")
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

print(f"Loaded {len(df)} outcomes.")
for c in ['entry', 'stop', 'target', 'atr', 'pnl', 'r_net', 'cost_r', 'bars_held']:
    df[c] = pd.to_numeric(df[c], errors='coerce')

c4l = df[(df['strategy'] == 'core') & (df['interval'] == '4h') & (df['label'].isin(['Buy', 'Strong Buy']))]
trending_mask = c4l['regime'].isin(['strong_trend', 'weak_trend', 'trending'])
ranging_mask = c4l['regime'].isin(['range', 'ranging'])
choppy_mask = c4l['regime'].isin(['high_vol', 'squeeze', 'choppy', 'chop'])

cohort_subsets = {
    'core_4h_long_all': c4l,
    'core_4h_long_trending': c4l[trending_mask],
    'core_4h_long_ranging': c4l[ranging_mask],
    'core_4h_long_choppy': c4l[choppy_mask],
    'flash_short_burst': df[(df['strategy'] == 'flash') & (df['label'].isin(['Sell', 'Strong Sell']))],
    'flash_long_burst': df[(df['strategy'] == 'flash') & (df['label'].isin(['Buy', 'Strong Buy']))],
    'core_short_all': df[(df['strategy'] == 'core') & (df['label'].isin(['Sell', 'Strong Sell']))],
}

print(f"{'Cohort':<24} | {'n':>4} | {'Ledger Mean R':>14} | {'Confirmed Mean R':>18} | {'Delta R':>10}")
print('-' * 75)

for cname, cdf in cohort_subsets.items():
    stored_mean = float(cdf['r_net'].mean())
    confirmed_r_list = []
    for _, row in cdf.iterrows():
        entry = float(row['entry']) if row['entry'] else 1.0
        stop = float(row['stop']) if row['stop'] else 0.98
        risk_dist = abs(entry - stop)
        stop_dist_pct = risk_dist / entry if entry > 0 else 0.01
        atr_val = float(row['atr']) if row['atr'] else 0.02 * entry
        bars = float(row['bars_held']) if row['bars_held'] else 12.0
        h_hours = bars * (4.0 if row['interval'] == '4h' else (1.0 if row['interval'] == '1h' else 0.25))
        
        entry_exec = 'maker' if row['strategy'] == 'core' else 'taker'
        res = row['result'] or 'stop'
        dir_str = 'long' if row['label'] in ('Buy', 'Strong Buy') else 'short'

        c_frac = trade_cost(
            market=row['market'],
            symbol=row['symbol'],
            atr_pct=atr_val / entry,
            is_perp=True,
            entry_execution=entry_exec,
            exit_result=res,
            direction=dir_str,
            holding_hours=h_hours,
        )
        c_r = c_frac / stop_dist_pct if stop_dist_pct > 0 else 0.0
        cr_val = float(row['cost_r']) if pd.notna(row['cost_r']) else 0.0
        gross_r = float(row['r_net']) + cr_val
        confirmed_r_list.append(gross_r - c_r)

    conf_mean = float(np.mean(confirmed_r_list))
    delta = conf_mean - stored_mean
    print(f"{cname:<24} | {len(cdf):>4} | {stored_mean:>+14.4f} | {conf_mean:>+18.4f} | {delta:>+10.4f}")
