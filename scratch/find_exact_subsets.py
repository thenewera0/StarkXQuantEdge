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

# Check all shorts:
# Total shorts = 259 (122 core + 137 flash).
# With r_net not null: 245 (120 core + 125 flash).
# Notice: 245 - 19 (15m flash) = 226!
# LOOK AT THAT!
# Total shorts with r_net not null on 1h, 4h, 1d (excluding 15m):
# 120 (core) + 106 (flash 1h) = 226!
print(f"Shorts with r_net not null excluding 15m: {len(df[df['label'].isin(['Sell', 'Strong Sell']) & df['r_net'].notna() & (df['interval'] != '15m')])}")
# EXACTLY 226!
# 120 Core shorts + 106 Flash 1h shorts = 226 shorts!

# Now what about 82?
# In flash shorts:
# Flash shorts total with r_net not null is 125.
# What subset of flash shorts has length 82?
flash_shorts = df[(df["strategy"] == "flash") & (df["label"].isin(["Sell", "Strong Sell"])) & df["r_net"].notna()]
print(f"Flash shorts total with r_net not null: {len(flash_shorts)}")
# Let's check subsets of flash_shorts:
for col in ["result", "regime", "symbol", "shadow"]:
    vc = flash_shorts[col].value_counts()
    print(f"Flash shorts by {col}:")
    print(vc)

# What if resolved_at date range?
# What if shadow is False or True? All flash paper trades are shadow=True:
print(f"Flash shorts shadow counts: {flash_shorts['shadow'].value_counts().to_dict()}")

# What about result != 'unfilled' or target / stop?
# 71 stop + 11 target = 82!
# LOOK AT THAT!
# result in ('stop', 'target') for flash shorts: 71 + 11 = 82!
# (125 total minus 43 timeouts = 82 barrier exits!)
print(f"Flash shorts with result in ('stop', 'target'): {len(flash_shorts[flash_shorts['result'].isin(['stop', 'target'])])}")
# EXACTLY 82!
