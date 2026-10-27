import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

import pandas as pd
from app import db

with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id as signal_id, s.symbol, s.regime, s.label, s.entry, s.stop, s.target,
               o.id as outcome_id, o.result, o.pnl, o.r_net, o.cost_r
        from signals s
        join outcomes o on o.signal_id = s.id
        where s.strategy = 'core' and s.interval = '4h' and s.label in ('Buy', 'Strong Buy') and o.r_net is not null
        order by s.id asc
    """)
    cols = [c.name for c in cur.description]
    records = [dict(zip(cols, r)) for r in cur.fetchall()]

df = pd.DataFrame(records)
print(f"Total rows: {len(df)}")
df["reg_cat"] = "other"
df.loc[df["regime"].isin(["strong_trend", "weak_trend", "trending"]), "reg_cat"] = "trending"
df.loc[df["regime"].isin(["range", "ranging"]), "reg_cat"] = "ranging"
df.loc[df["regime"].isin(["high_vol", "squeeze", "choppy", "chop"]), "reg_cat"] = "choppy"

print("\nActual DB r_net by reg_cat:")
print(df.groupby("reg_cat")["r_net"].agg(["count", "sum", "mean"]))

print("\nActual DB pnl by reg_cat:")
print(df.groupby("reg_cat")["pnl"].agg(["count", "sum", "mean"]))

# What about cost_adjusted_r?
# What if cost was subtracted?
# What if someone computed r_net under the new fee schedule (2 bps maker, 5 bps taker, 3 bps slip)?
# Let's check if there is another table or script that generated 42.128 and -10.24!
