import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

import pandas as pd
from app import db

with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id as signal_id, s.symbol, s.regime, o.r_net, o.pnl
        from signals s
        join outcomes o on o.signal_id = s.id
        where s.strategy = 'core' and s.interval = '4h' and s.label in ('Buy', 'Strong Buy') and o.r_net is not null
        order by s.id asc
    """)
    records = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]

df = pd.DataFrame(records)

trending_ids = df[df["regime"].isin(["strong_trend", "weak_trend", "trending"])]["signal_id"].tolist()
ranging_ids = df[df["regime"].isin(["range", "ranging"])]["signal_id"].tolist()
choppy_ids = df[df["regime"].isin(["high_vol", "squeeze", "choppy", "chop"])]["signal_id"].tolist()

print(f"Trending (n={len(trending_ids)}): {trending_ids[:10]}... (total {len(trending_ids)})")
print(f"Ranging (n={len(ranging_ids)}): {ranging_ids}")
print(f"Choppy (n={len(choppy_ids)}): {choppy_ids}")

# Look at choppy trades and their r_net:
choppy_df = df[df["signal_id"].isin(choppy_ids)]
print("\nChoppy Trades:")
for _, r in choppy_df.iterrows():
    print(f"  Signal {r['signal_id']} ({r['symbol']}, {r['regime']}): r_net = {r['r_net']:+.4f}")
print(f"Choppy Sum R: {choppy_df['r_net'].sum():+.4f}")

trending_df = df[df["signal_id"].isin(trending_ids)]
print(f"\nTrending Sum R: {trending_df['r_net'].sum():+.4f}")
ranging_df = df[df["signal_id"].isin(ranging_ids)]
print(f"Ranging Sum R: {ranging_df['r_net'].sum():+.4f}")
