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

print(f"Total signals in DB: {len(df)}")

# What queries give 226 rows?
# Look for counts of 226 across any subset:
print("\nSearching for 226 rows:")
# Shorts
shorts = df[df["label"].isin(["Sell", "Strong Sell"])]
print(f"Total shorts in DB: {len(shorts)}")

# Could 226 be core shorts + something?
# What about resolved trades?
# What about intervals?
# Let's test combinations
for strat in [None, "core", "flash"]:
    for iv in [None, "1h", "4h", "15m", "1d"]:
        for shad in [None, True, False]:
            for r_notna in [None, True, False]:
                sub = df.copy()
                if strat:
                    sub = sub[sub["strategy"] == strat]
                if iv:
                    sub = sub[sub["interval"] == iv]
                if shad is not None:
                    sub = sub[sub["shadow"] == shad]
                if r_notna is not None:
                    if r_notna:
                        sub = sub[sub["r_net"].notna()]
                    else:
                        sub = sub[sub["r_net"].isna()]
                
                # Check shorts
                sub_shorts = sub[sub["label"].isin(["Sell", "Strong Sell"])]
                if len(sub_shorts) in (226, 82):
                    print(f"MATCH: len={len(sub_shorts)} | strat={strat}, iv={iv}, shad={shad}, r_notna={r_notna}")
                if len(sub) in (226, 82):
                    print(f"MATCH TOTAL: len={len(sub)} | strat={strat}, iv={iv}, shad={shad}, r_notna={r_notna}")

# What if we include both core and flash? Or what if there are 226 core shorts in some other table or view?
# Let's check other tables in DB:
with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\nTables in DB: {tables}")
    for t in tables:
        cur.execute(f"SELECT count(*) FROM {t}")
        cnt = cur.fetchone()[0]
        print(f"  Table {t}: {cnt} rows")

