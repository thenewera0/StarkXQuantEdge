import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))
import pandas as pd
from app import db

with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("""
        select s.id, s.strategy, s.interval, s.regime, s.label, s.shadow, o.r_net
        from signals s
        left join outcomes o on o.signal_id = s.id
        where s.label in ('Sell', 'Strong Sell') and s.interval != '15m' and o.r_net is not null
    """)
    records = cur.fetchall()

df = pd.DataFrame(records, columns=['id', 'strategy', 'interval', 'regime', 'label', 'shadow', 'r_net'])
print(f"Count: {len(df)}")
print(f"Mean R net: {df['r_net'].mean():.4f}")
print(f"Sum R net: {df['r_net'].sum():.4f}")
