import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))

from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

import json
import numpy as np
import pandas as pd
from app import db
from app.config import settings

def run_investigation():
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
        cols = [c.name for c in cur.description]
        records = [dict(zip(cols, r)) for r in cur.fetchall()]

    df = pd.DataFrame(records)
    print(f"Total rows fetched: {len(df)}")
    
    # Check 3.0(f): core shorts and flash shorts filters
    print("\n--- 3.0(f) Querying Core Shorts and Flash Shorts ---")
    core_shorts_all = df[(df["strategy"] == "core") & (df["label"].isin(["Sell", "Strong Sell"]))]
    print(f"Core Shorts Total: {len(core_shorts_all)}")
    print(f"  with outcome r_net not null: {len(core_shorts_all[core_shorts_all['r_net'].notna()])}")
    print(f"  shadow=True: {len(core_shorts_all[core_shorts_all['shadow'] == True])}")
    print(f"  shadow=False: {len(core_shorts_all[core_shorts_all['shadow'] == False])}")
    print(f"  by interval: {core_shorts_all['interval'].value_counts().to_dict()}")

    # Check how 226 might be produced
    # What filter produces exactly 226?
    # Maybe all short signals regardless of strategy or with certain intervals?
    all_shorts = df[df["label"].isin(["Sell", "Strong Sell"])]
    print(f"All shorts in DB: {len(all_shorts)}")
    print(f"All shorts with r_net not null: {len(all_shorts[all_shorts['r_net'].notna()])}")
    for strat in df["strategy"].unique():
        sub = df[(df["strategy"] == strat) & (df["label"].isin(["Sell", "Strong Sell"]))]
        print(f"  Strategy {strat} shorts: total={len(sub)}, r_net_notna={len(sub[sub['r_net'].notna()])}")

    # Check flash shorts
    flash_shorts = df[(df["strategy"] == "flash") & (df["label"].isin(["Sell", "Strong Sell"]))]
    print(f"Flash shorts total: {len(flash_shorts)}")
    print(f"  with r_net not null: {len(flash_shorts[flash_shorts['r_net'].notna()])}")
    print(f"  by interval: {flash_shorts['interval'].value_counts().to_dict()}")
    # Is there an interval with 82 rows?
    for iv in flash_shorts["interval"].unique():
        sub_iv = flash_shorts[flash_shorts["interval"] == iv]
        print(f"    Interval {iv}: total={len(sub_iv)}, r_net_notna={len(sub_iv[sub_iv['r_net'].notna()])}")

    # Check 3.0(d): Regime cohort drift
    print("\n--- 3.0(d) Regime Cohort Drift for Core 4h Long ---")
    c4l = df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"])) & (df["r_net"].notna())].copy()
    print(f"Core 4h Long (All): {len(c4l)}")
    print("Regime values present in c4l:")
    print(c4l["regime"].value_counts(dropna=False))
    
    # Let's inspect R_net sums by regime
    for reg, grp in c4l.groupby("regime"):
        print(f"Regime '{reg}': n={len(grp)}, sum_r_net={grp['r_net'].sum():.4f}, mean_r_net={grp['r_net'].mean():.4f}")

    # Check what Phase 0.5 used vs Phase 1.1:
    # Phase 0.5:
    # trending: regime in ["strong_trend", "weak_trend", "trending"]
    # ranging: regime in ["range", "ranging"]
    # choppy: regime in ["high_vol", "squeeze", "choppy", "chop"]
    c4l["reg_p05"] = "other"
    c4l.loc[c4l["regime"].isin(["strong_trend", "weak_trend", "trending"]), "reg_p05"] = "trending"
    c4l.loc[c4l["regime"].isin(["range", "ranging"]), "reg_p05"] = "ranging"
    c4l.loc[c4l["regime"].isin(["high_vol", "squeeze", "choppy", "chop"]), "reg_p05"] = "choppy"
    
    print("\nGrouped by p05 categories:")
    for cat, grp in c4l.groupby("reg_p05"):
        print(f"Cat '{cat}': n={len(grp)}, sum_r={grp['r_net'].sum():.4f}, mean_r={grp['r_net'].mean():.4f}")

    # What did Phase 0.5 report?
    # Phase 0.5 reported:
    # Trending: n=151, mean=0.169 R, sum=25.5 R
    # Ranging: n=29, mean=0.954 R, sum=27.67 R
    # Choppy: n=11, mean=0.579 R, sum=6.37 R
    # Notice: 25.5 + 27.67 + 6.37 = 59.54 R!
    # But today:
    # Let's see what the sum of r_net is for each of those groups!

if __name__ == "__main__":
    run_investigation()
