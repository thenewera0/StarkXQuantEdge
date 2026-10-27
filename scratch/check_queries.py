import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))
import pandas as pd
from app import db

with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id, s.strategy, s.interval, s.regime, s.label, s.shadow, o.r_net, o.pnl, o.cost_r
        from signals s
        join outcomes o on o.signal_id = s.id
        where o.r_net is not null
    """)
    records = cur.fetchall()

df = pd.DataFrame(records, columns=['id', 'strategy', 'interval', 'regime', 'label', 'shadow', 'r_net', 'pnl', 'cost_r'])

# Check what has mean around -0.088 R:
print(f"Total sized rows: {len(df)}")
# Check all shorts:
shorts = df[df["label"].isin(["Sell", "Strong Sell"])]
print(f"Total shorts: {len(shorts)}, mean: {shorts['r_net'].mean():.4f}")

# What if 226 shorts was:
# What if shadow was included / excluded?
for strat in [None, "core", "flash"]:
    for iv in [None, "1h", "4h", "15m", "1d"]:
        sub = df.copy()
        if strat: sub = sub[sub["strategy"] == strat]
        if iv: sub = sub[sub["interval"] == iv]
        # check if len is 226 or 82
        if len(sub) in (226, 82):
            print(f"Count {len(sub)}: strat={strat}, iv={iv}, mean={sub['r_net'].mean():.4f}")

# What about flash shorts:
f_shorts = df[(df["strategy"] == "flash") & (df["label"].isin(["Sell", "Strong Sell"]))]
print(f"Flash shorts: len={len(f_shorts)}, mean={f_shorts['r_net'].mean():.4f}")
# How can flash shorts be 82?
# What if 82 was:
for iv in f_shorts["interval"].unique():
    sub = f_shorts[f_shorts["interval"] == iv]
    print(f"  iv={iv}: len={len(sub)}, mean={sub['r_net'].mean():.4f}")

# What about by date?
# If date is <= some date:
for d in ["2026-09-20", "2026-09-23", "2026-09-24", "2026-10-01"]:
    pass
