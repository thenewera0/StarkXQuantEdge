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
               s.size_pct, s.created_at,
               o.id as outcome_id, o.result, o.pnl, o.r_net, o.cost_r,
               o.bars_held, o.resolved_at
        from signals s
        join outcomes o on o.signal_id = s.id
        where o.r_net is not null
        order by s.id asc
    """)
    records = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]

df = pd.DataFrame(records)

# Let's inspect cost_r stored in DB:
print("Sample of stored cost_r in outcomes:")
print(df[["signal_id", "strategy", "interval", "r_net", "cost_r", "bars_held"]].head(10))

# For each cohort, compute:
# 1) Stored mean r_net
# 2) Recomputed cost_r using confirmed fees (maker 2 bps, taker 5 bps, 3 bps slippage + funding)
cohort_defs = {
    "core_4h_long_all": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"]))],
    "core_4h_long_trending": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"])) & (df["regime"].isin(["strong_trend", "weak_trend", "trending"]))],
    "core_4h_long_ranging": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"])) & (df["regime"].isin(["range", "ranging"]))],
    "core_4h_long_choppy": df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"])) & (df["regime"].isin(["high_vol", "squeeze", "choppy", "chop"]))],
    "flash_short_burst": df[(df["strategy"] == "flash") & (df["label"].isin(["Sell", "Strong Sell"]))],
    "flash_long_burst": df[(df["strategy"] == "flash") & (df["label"].isin(["Buy", "Strong Buy"]))],
    "core_short_all": df[(df["strategy"] == "core") & (df["label"].isin(["Sell", "Strong Sell"]))],
}

print("\n--- Cohort Cost Parity ---")
for cname, cdf in cohort_defs.items():
    stored_mean_r = cdf["r_net"].mean()
    stored_cost_r = cdf["cost_r"].mean() if "cost_r" in cdf and cdf["cost_r"].notna().any() else 0.0
    
    # Compute confirmed cost
    confirmed_costs = []
    confirmed_net_rs = []
    for _, r in cdf.iterrows():
        entry = float(r["entry"])
        stop = float(r["stop"])
        risk_dist = abs(entry - stop)
        stop_dist_pct = risk_dist / entry if entry > 0 else 0.01
        atr_t = float(r["atr"]) if r["atr"] is not None else 0.02 * entry
        bars_held = float(r["bars_held"]) if r["bars_held"] is not None else 12.0
        holding_hours = bars_held * (4.0 if r["interval"] == "4h" else (1.0 if r["interval"] == "1h" else 0.25))
        
        # entry_exec: for core, limit (maker); for flash, market (taker) or limit?
        entry_exec = "maker" if r["strategy"] == "core" else "taker"
        res = r["result"] or "stop"
        
        c_frac = trade_cost(
            market="crypto",
            symbol=r["symbol"],
            atr_pct=atr_t / entry,
            is_perp=True,
            entry_execution=entry_exec,
            exit_result=res,
            direction="long" if r["label"] in ("Buy", "Strong Buy") else "short",
            holding_hours=holding_hours,
        )
        c_r = c_frac / stop_dist_pct if stop_dist_pct > 0 else 0.0
        confirmed_costs.append(c_r)
        
        cr_val = float(r["cost_r"]) if r["cost_r"] is not None and str(r["cost_r"]).strip() != "" else 0.0
        gross_r = float(r["r_net"]) + cr_val
        confirmed_net_rs.append(gross_r - c_r)

    print(f"{cname:<24}: n={len(cdf):>3} | Stored Mean R={stored_mean_r:>+8.4f} | Stored Cost R={stored_cost_r:>8.4f} | Confirmed Cost R={np.mean(confirmed_costs):>8.4f} | Confirmed Mean R={np.mean(confirmed_net_rs):>+8.4f}")
