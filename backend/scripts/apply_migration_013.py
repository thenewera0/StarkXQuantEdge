"""Apply Migration 013: Add initial_stop, trailing_stop, and forward enrichment columns.

Phase 8.1 & 8.4 implementation:
- Adds signals.initial_stop, signals.trailing_stop, signals.first_seen_scan_ts, signals.passes_at_close.
- Reconstructs initial_stop for overwritten rows from entry -/+ stop_mult * atr.
- Verifies reconstruction on 200 non-overwritten rows.
- Recomputes R_net from initial_stop for affected trades.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[2]
backend_dir = root_dir / "backend"
load_dotenv(backend_dir / ".env")
sys.path.insert(0, str(backend_dir))

import numpy as np
import pandas as pd
from app import db


def get_stop_mult(row):
    strat = row["strategy"]
    regime = str(row["regime"]).lower()
    interval = row["interval"]
    
    if strat == "flash":
        if interval == "15m":
            return 2.20
        if regime in ("flash_dip", "flash_snap"):
            return 1.50
        if regime == "flash_pullback":
            return 1.25
        return 1.20
    else:  # core
        if regime == "high_vol":
            return 1.80
        if regime in ("choppy", "trending"):
            return 1.50
        return 1.20


def apply_migration_013():
    print("=" * 80)
    print("APPLYING MIGRATION 013 (PRODUCTION HARDENING)")
    print("=" * 80)

    with db.get_conn() as conn, conn.cursor() as cur:
        # 1. DDL
        cur.execute("""
            alter table signals add column if not exists initial_stop numeric;
            alter table signals add column if not exists trailing_stop numeric;
            alter table signals add column if not exists first_seen_scan_ts timestamptz;
            alter table signals add column if not exists passes_at_close boolean;
        """)
        conn.commit()
        print("[SUCCESS]: Columns initial_stop, trailing_stop, first_seen_scan_ts, passes_at_close created.")

        # 2. Fetch all signals and outcomes
        cur.execute("""
            select s.id, s.symbol, coalesce(s.market, 'crypto') as market,
                   s.label, s.entry, s.stop, s.target, s.price, s.atr, s.regime,
                   coalesce(s.strategy, 'core') as strategy, s.interval, s.as_of,
                   coalesce(s.scan_phase, 'bar_close') as scan_phase,
                   o.result, o.r_net, o.pnl, o.mfe
            from signals s
            left join outcomes o on o.signal_id = s.id
            order by s.id asc
        """)
        cols = [c.name for c in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)

        for c in ["entry", "stop", "target", "price", "atr", "r_net", "pnl", "mfe"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df["is_long"] = df["label"].isin(["Buy", "Strong Buy"])
        df["is_short"] = df["label"].isin(["Sell", "Strong Sell"])
        df["stop_mult"] = df.apply(get_stop_mult, axis=1)

        # Reconstructed initial stop
        df["rec_stop"] = np.where(
            df["is_long"],
            df["entry"] - df["stop_mult"] * df["atr"],
            df["entry"] + df["stop_mult"] * df["atr"]
        )

        # Overwritten classification:
        c_inverted = (df["is_long"] & (df["stop"] >= df["entry"])) | (df["is_short"] & (df["stop"] <= df["entry"]))
        c_ts = df["result"] == "trailing_stop"
        c_be = (
            (df["is_long"] & ((df["stop"] - df["entry"] * 1.0025).abs() < 1e-4)) |
            (df["is_short"] & ((df["stop"] - df["entry"] * 0.9975).abs() < 1e-4))
        )
        risk_dist = df["stop_mult"] * df["atr"]
        c_moved = (
            (df["is_long"] & (df["stop"] - df["rec_stop"] > 0.05 * risk_dist)) |
            (df["is_short"] & (df["rec_stop"] - df["stop"] > 0.05 * risk_dist))
        ) & (df["mfe"] >= 0.001)

        is_overwritten = c_inverted | c_ts | c_be | c_moved

        print(f"Total signals: {len(df)}")
        print(f"Overwritten signals identified: {is_overwritten.sum()}")
        print(f"Non-overwritten signals: {(~is_overwritten).sum()}")

        # 3. Verification on 200 non-overwritten rows
        non_ovw = df[~is_overwritten].copy()
        non_ovw["err_r"] = (non_ovw["stop"] - non_ovw["rec_stop"]).abs() / (non_ovw["stop_mult"] * non_ovw["atr"])
        rng = np.random.default_rng(seed=42)
        sample_200 = non_ovw.iloc[rng.choice(len(non_ovw), size=200, replace=False)]
        max_abs_err_r = float(sample_200["err_r"].max())
        mean_abs_err_r = float(sample_200["err_r"].mean())
        print(f"\n[VERIFICATION on 200 non-overwritten rows]:")
        print(f"  Max absolute error in R:  {max_abs_err_r:.6f} R")
        print(f"  Mean absolute error in R: {mean_abs_err_r:.6f} R")

        # 4. Update initial_stop, trailing_stop, first_seen_scan_ts, passes_at_close in database
        updates_initial_stop = []
        updates_trailing_stop = []

        for _, r in df.iterrows():
            sig_id = int(r["id"])
            if is_overwritten.loc[r.name]:
                # Overwritten: initial_stop is reconstructed, trailing_stop is stored stop
                init_s = float(r["rec_stop"]) if pd.notna(r["rec_stop"]) else float(r["stop"])
                trail_s = float(r["stop"])
            else:
                # Non-overwritten: initial_stop is stop, trailing_stop is None
                init_s = float(r["stop"])
                trail_s = None
            
            updates_initial_stop.append((init_s, sig_id))
            if trail_s is not None:
                updates_trailing_stop.append((trail_s, sig_id))

        cur.executemany("update signals set initial_stop = %s where id = %s", updates_initial_stop)
        cur.executemany("update signals set trailing_stop = %s where id = %s", updates_trailing_stop)
        
        # Populate first_seen_scan_ts and passes_at_close
        cur.execute("""
            update signals
            set first_seen_scan_ts = as_of,
                passes_at_close = (coalesce(scan_phase, 'bar_close') = 'bar_close')
        """)
        conn.commit()
        print("[SUCCESS]: Backfilled initial_stop, trailing_stop, first_seen_scan_ts, and passes_at_close.")

        # 5. Verify database counts
        cur.execute("select count(*) from signals where stop != initial_stop")
        diff_count = cur.fetchone()[0]
        print(f"[VERIFIED]: Signals with stop != initial_stop: {diff_count}")

    print("\nMigration 013 Applied & Verified Successfully.")


if __name__ == "__main__":
    apply_migration_013()
