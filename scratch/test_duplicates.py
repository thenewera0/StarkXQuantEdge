import sys
from pathlib import Path
from datetime import timedelta
import pandas as pd
import numpy as np

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
               o.r_net, o.pnl, o.result, o.bars_held, o.mfe, o.mae
        from signals s
        left join outcomes o on o.signal_id = s.id
        order by s.id asc
    """)
    cols = [c.name for c in cur.description]
    signals = [dict(zip(cols, r)) for r in cur.fetchall()]

df = pd.DataFrame(signals)
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

dups = df[df.duplicated(subset=['fingerprint'], keep=False)].sort_values(by=['symbol', 'bar_open_time', 'id'])
print(f"Total duplicate rows: {len(dups)}")
for fp, group in dups.groupby('fingerprint'):
    print(f"\nFingerprint: {fp}")
    for idx, r in group.iterrows():
        print(f"  ID {r['id']}: as_of={r['as_of']}, created_at={r['created_at']}, entry={r['entry']}, stop={r['stop']}, target={r['target']}, size={r['size_pct']}, r_net={r['r_net']}")
