import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

import pandas as pd
from app import db

with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id as signal_id, s.symbol, coalesce(s.market, 'crypto') as market,
               s.interval, coalesce(s.strategy, 'core') as strategy,
               s.regime, s.label, s.entry, s.stop, s.target, s.atr, s.price,
               s.size_pct, s.win_prob, s.reward_risk, s.shadow, s.created_at,
               o.id as outcome_id, o.result, o.pnl, o.r_net, o.cost_r, o.mfe, o.mae,
               o.bars_held, o.resolved_at
        from signals s
        left join outcomes o on o.signal_id = s.id
        order by s.id asc
    """)
    records = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]

df = pd.DataFrame(records)

# Check all possible queries in DB that give count 82:
print("Searching entire DB for any query returning 82:")
for col in ["strategy", "interval", "regime", "result", "label", "shadow"]:
    for val in df[col].dropna().unique():
        sub = df[df[col] == val]
        if len(sub) == 82:
            print(f"  Single filter: {col} == '{val}' -> 82")
        for col2 in ["strategy", "interval", "regime", "result", "label", "shadow"]:
            if col2 != col:
                for val2 in sub[col2].dropna().unique():
                    sub2 = sub[sub[col2] == val2]
                    if len(sub2) == 82:
                        print(f"  Double filter: {col} == '{val}' & {col2} == '{val2}' -> 82")

# What about with r_net notna?
df_sized = df[df["r_net"].notna()]
for col in ["strategy", "interval", "regime", "result", "label", "shadow"]:
    for val in df_sized[col].dropna().unique():
        sub = df_sized[df_sized[col] == val]
        if len(sub) == 82:
            print(f"  Sized single filter: {col} == '{val}' -> 82")
        for col2 in ["strategy", "interval", "regime", "result", "label", "shadow"]:
            if col2 != col:
                for val2 in sub[col2].dropna().unique():
                    sub2 = sub[sub[col2] == val2]
                    if len(sub2) == 82:
                        print(f"  Sized double filter: {col} == '{val}' & {col2} == '{val2}' -> 82")

