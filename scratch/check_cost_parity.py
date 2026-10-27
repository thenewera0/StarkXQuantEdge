import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

import numpy as np
import pandas as pd
from app import db
from app.costs import trade_cost

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
        where o.r_net is not null
        order by s.id asc
    """)
    records = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]

df = pd.DataFrame(records)
print(f"Total resolved trades: {len(df)}")

# Define cohorts:
cohorts = {
    "core_4h_long_all": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"]))],
    "core_4h_long_trending": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"])) & (df["regime"].isin(["strong_trend", "weak_trend", "trending"]))],
    "core_4h_long_ranging": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"])) & (df["regime"].isin(["range", "ranging"]))],
    "core_4h_long_choppy": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"])) & (df["regime"].isin(["high_vol", "squeeze", "choppy", "chop"]))],
    "flash_short_burst": df[(df["strategy"] == "flash") & (df["label"].isin(["Sell", "Strong Sell"]))],
    "flash_long_burst": df[(df["strategy"] == "flash") & (df["label"].isin(["Buy", "Strong Buy"]))],
    "core_short_all": df[(df["strategy"] == "core") & (df["label"].isin(["Sell", "Strong Sell"]))],
}

print("\n--- Cost Parity Analysis ---")
print(f"{'Cohort':<24} | {'n':>4} | {'Ledger Mean R':>14} | {'Ledger Cost R':>14} | {'Confirmed Cost R':>18} | {'Confirmed Mean R':>18}")
print("-" * 105)

for ckey, cdf in cohorts.items():
    ledger_r = cdf["r_net"].mean()
    ledger_cost = cdf["cost_r"].mean() if "cost_r" in cdf and cdf["cost_r"].notna().any() else 0.0
    
    # Compute confirmed fees: maker 2 bps, taker 5 bps, 3 bps slippage + funding
    # Let's see how cost_r was recalculated for core long in Phase 0.6 / cohorts.json:
    # In cohorts.json: core_4h_long_all went from 0.3118 to 0.1702 (delta = -0.1416 R)
    # But flash short stayed 0.0466! Core short stayed -0.5471!
    # Why did only core long change in cohorts.json?
    print(f"{ckey:<24} | {len(cdf):>4} | {ledger_r:>+14.4f} | {ledger_cost:>14.4f}")
