import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir / 'backend'))
from dotenv import load_dotenv
load_dotenv(root_dir / 'backend' / '.env')
from app import db
import pandas as pd

with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute('''
        select s.id, s.symbol, coalesce(s.market, 'crypto') as market, s.strategy, s.interval, s.label, s.regime, s.shadow, o.r_net
        from signals s
        join outcomes o on o.signal_id = s.id
        where o.r_net is not null
    ''')
    cols = [c.name for c in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)

for col in ['r_net']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

print('--- CORE 4H LONGS ---')
c4l = df[(df['strategy'] == 'core') & (df['interval'] == '4h') & (df['label'].isin(['Buy', 'Strong Buy']))]
print(f'Total n={len(c4l)}, sum={c4l["r_net"].sum():.4f}')
print('Markets:', c4l['market'].value_counts().to_dict())

trending = c4l[c4l['regime'].isin(['strong_trend', 'weak_trend', 'trending'])]
ranging = c4l[c4l['regime'].isin(['range', 'ranging'])]
choppy = c4l[c4l['regime'].isin(['high_vol', 'squeeze', 'choppy', 'chop'])]
print(f'Trending: n={len(trending)}, sum={trending["r_net"].sum():.4f}')
print(f'Ranging: n={len(ranging)}, sum={ranging["r_net"].sum():.4f}')
print(f'Choppy: n={len(choppy)}, sum={choppy["r_net"].sum():.4f}')

print('\n--- FLASH SHORT BURST ---')
fs = df[(df['strategy'] == 'flash') & (df['label'].isin(['Sell', 'Strong Sell']))]
print(f'Total n={len(fs)}, sum={fs["r_net"].sum():.4f}, markets={fs["market"].value_counts().to_dict()}, intervals={fs["interval"].value_counts().to_dict()}')

print('\n--- FLASH LONG BURST ---')
fl = df[(df['strategy'] == 'flash') & (df['label'].isin(['Buy', 'Strong Buy']))]
print(f'Total n={len(fl)}, sum={fl["r_net"].sum():.4f}, markets={fl["market"].value_counts().to_dict()}, intervals={fl["interval"].value_counts().to_dict()}')

print('\n--- CORE SHORT ALL ---')
cs = df[(df['strategy'] == 'core') & (df['label'].isin(['Sell', 'Strong Sell']))]
print(f'Total n={len(cs)}, sum={cs["r_net"].sum():.4f}, markets={cs["market"].value_counts().to_dict()}, intervals={cs["interval"].value_counts().to_dict()}')
