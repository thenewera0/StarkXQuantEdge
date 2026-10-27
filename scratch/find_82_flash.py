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
        join outcomes o on o.signal_id = s.id
        where s.strategy = 'flash' and s.label in ('Sell', 'Strong Sell') and o.r_net is not null
        order by s.id asc
    """)
    records = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]

df = pd.DataFrame(records)
print(f"Total flash shorts: {len(df)}")

# Check dates:
# How many before a certain date?
df["date"] = df["resolved_at"].astype(str).str[:10]
date_counts = df["date"].value_counts().sort_index()
print("Dates:")
print(date_counts)
cum_dates = date_counts.cumsum()
print("Cumulative by date:")
print(cum_dates)

# What if certain symbols?
# What if interval == '1h' and certain results?
# Let's check all combinations of filters
for col in ["result", "interval", "regime"]:
    for val in df[col].unique():
        sub = df[df[col] == val]
        if len(sub) == 82:
            print(f"MATCH: {col} == '{val}' -> 82 rows")
        sub_not = df[df[col] != val]
        if len(sub_not) == 82:
            print(f"MATCH: {col} != '{val}' -> 82 rows")

# Check multi-column
for r_val in df["result"].unique():
    sub = df[df["result"] != r_val]
    for iv in df["interval"].unique():
        sub2 = sub[sub["interval"] == iv]
        if len(sub2) == 82:
            print(f"MATCH: result != '{r_val}' and interval == '{iv}' -> 82 rows")

# What about trailing_stop + target? 64 + 20 = 84
# What about trailing_stop + stop? 64 + 37 = 101
# What about interval == '1h'? 106
# 106 - 24 = 82? Which 24?
sub_1h = df[df["interval"] == "1h"]
print(f"1h flash shorts: {len(sub_1h)}")
print(sub_1h["result"].value_counts())
# In 1h flash shorts:
# trailing_stop: 54, stop: 33, target: 16, timeout: 2, stagnation: 1
# 54 trailing_stop + 16 target + 12 stop = 82?
# Or date cutoff?
for dt in df["date"].unique():
    c_before = len(df[df["date"] <= dt])
    c_after = len(df[df["date"] >= dt])
    if c_before == 82:
        print(f"MATCH DATE <= {dt} -> 82 rows")
    if c_after == 82:
        print(f"MATCH DATE >= {dt} -> 82 rows")
