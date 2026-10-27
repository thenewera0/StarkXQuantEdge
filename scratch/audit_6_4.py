"""Forensic script for 6.4: Partial-Book Parity audit across 20 trades under (0.20R, 50%) vs (0.60R, 35%)."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")
from app import db

# Fetch the 20 trades used in Phase 5 table
with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id as signal_id, s.symbol, coalesce(s.market, 'crypto') as market,
               s.interval, coalesce(s.strategy, 'core') as strategy,
               s.regime, s.label, s.entry, s.stop, s.target, s.atr, s.as_of,
               o.id as outcome_id, o.result, o.pnl, o.r_net, o.cost_r,
               o.bars_held, o.mfe, o.mae
        from signals s
        join outcomes o on o.signal_id = s.id
        where s.strategy = 'core' and s.interval = '4h' and s.label in ('Buy', 'Strong Buy') and o.r_net is not null
        order by s.id asc
    """)
    cols = [c.name for c in cur.description]
    records = [dict(zip(cols, r)) for r in cur.fetchall()]

df = pd.DataFrame(records)
for c in ['entry', 'stop', 'target', 'atr', 'pnl', 'r_net', 'cost_r', 'bars_held', 'mfe', 'mae']:
    df[c] = pd.to_numeric(df[c], errors='coerce')

# Seed 42 20-trade sample
rng = np.random.default_rng(42)
sample_idx = rng.choice(len(df), size=20, replace=False)
sample_df = df.iloc[sample_idx]

print("=" * 80)
print("6.4 PARTIAL-BOOK RECOMPUTATIONS FOR 20 TRADES")
print("=" * 80)

rows = []
for _, r in sample_df.iterrows():
    sig_id = int(r['signal_id'])
    sym = r['symbol']
    entry = float(r['entry'])
    stop = float(r['stop'])
    target = float(r['target'])
    risk_dist = abs(entry - stop)
    stop_dist_pct = risk_dist / entry if entry > 0 else 0.01
    res = r['result'] or "stop"
    stored_r_net = float(r['r_net'])
    cost_r = float(r['cost_r']) if pd.notna(r['cost_r']) else 0.0
    stored_gross_r = stored_r_net + cost_r
    mfe = float(r['mfe']) if pd.notna(r['mfe']) else 0.0
    mfe_r = mfe / stop_dist_pct if stop_dist_pct > 0 else 0.0
    
    # Target multiple R
    target_r = (target - entry) / risk_dist if risk_dist > 0 else 2.0
    
    # What was the final exit gross R without partial booking?
    # If target: +target_r. If stop: -1.0. If timeout/other: deduce
    if res.lower() == 'target':
        final_leg_r = target_r
    elif res.lower() == 'stop':
        final_leg_r = -1.0
    else:
        # deduce final leg from stored gross
        final_leg_r = stored_gross_r

    # Rule A: (0.20R, 50%)
    # Partial triggers if MFE >= 0.20R
    if mfe_r >= 0.20:
        gross_rule_A = 0.50 * 0.20 + 0.50 * final_leg_r
        booked_A = "Booked 50% @ +0.20R"
    else:
        gross_rule_A = final_leg_r
        booked_A = "None (< +0.20R)"

    # Rule B: (0.60R, 35%)
    # Partial triggers if MFE >= 0.60R
    if mfe_r >= 0.60:
        gross_rule_B = 0.35 * 0.60 + 0.65 * final_leg_r
        booked_B = "Booked 35% @ +0.60R"
    else:
        gross_rule_B = final_leg_r
        booked_B = "None (< +0.60R)"

    rows.append({
        'signal_id': sig_id,
        'symbol': sym,
        'result': res,
        'target_r': f"{target_r:.2f}R",
        'mfe_r': f"{mfe_r:+.2f}R",
        'stored_gross_r': f"{stored_gross_r:+.4f}R",
        'gross_rule_A_20_50': f"{gross_rule_A:+.4f}R",
        'gross_rule_B_60_35': f"{gross_rule_B:+.4f}R",
        'booked_A': booked_A,
        'booked_B': booked_B
    })

res_df = pd.DataFrame(rows)
print(res_df.to_string())
