#!/usr/bin/env python3
"""Phase 7.4 — Forward Evaluation Script.

Reads only post-freeze (>= 2026-10-26T12:45:00Z) crypto core_4h_long unique rows,
hybrid entry, confirmed fees, day-block bootstrap (B=10,000).
Reports n, N_eff, mean R, CI, top-5 share, split by scan_phase.
Applies pre-registered rule:
  PASS needs: mean >= +0.15 AND lower bound > 0 AND top-5 <= 20%
  Evaluate at the earlier of N_eff >= 85 or 2027-04-26.
  Outputs ONLY INCONCLUSIVE / PASS / FAIL on the evaluation date; NO interim decisions.
Appends output weekly to docs/FORWARD_LOG.md.
"""

from __future__ import annotations

import argparse
import datetime
import math
import sys
from pathlib import Path
from dotenv import load_dotenv

# Path resolution
cur_path = Path(__file__).resolve()
backend_dir = cur_path.parents[1] if (cur_path.parents[1] / "app").exists() else (cur_path.parents[1] / "backend")
load_dotenv(backend_dir / ".env")
sys.path.insert(0, str(backend_dir))

import numpy as np
import pandas as pd
from app import db

FREEZE_TIMESTAMP = "2026-10-26T12:45:00Z"
TARGET_EVAL_DATE = "2027-04-26"
TARGET_N_EFF = 85
BOOTSTRAP_ROUNDS = 10000


def run_day_block_bootstrap(df: pd.DataFrame, rounds: int = BOOTSTRAP_ROUNDS) -> tuple[float, float]:
    """Perform day-block bootstrap for trade R returns."""
    if len(df) == 0:
        return 0.0, 0.0
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["as_of"]).dt.date
    dates = df["date"].unique()
    n_dates = len(dates)
    if n_dates < 2:
        mean_val = float(df["r_net"].mean())
        return mean_val, mean_val

    date_groups = {d: group["r_net"].values for d, group in df.groupby("date")}
    rng = np.random.default_rng(seed=42)

    boot_means = np.empty(rounds, dtype=np.float64)
    for i in range(rounds):
        sampled_dates = rng.choice(dates, size=n_dates, replace=True)
        sampled_trades = np.concatenate([date_groups[d] for d in sampled_dates])
        boot_means[i] = sampled_trades.mean()

    lower = float(np.percentile(boot_means, 2.5))
    upper = float(np.percentile(boot_means, 97.5))
    return lower, upper


def evaluate_forward(append_log: bool = False) -> dict:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    now_date_str = now_utc.strftime("%Y-%m-%d")

    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            select s.id, s.symbol, s.as_of, coalesce(s.scan_phase, 'unknown') as scan_phase,
                   coalesce(s.passes_at_close, false) as passes_at_close, s.first_seen_scan_ts,
                   o.r_net, o.pnl, o.cost_r
            from signals s
            join outcomes o on o.signal_id = s.id
            where s.as_of >= %s
              and coalesce(s.market, 'crypto') = 'crypto'
              and coalesce(s.strategy, 'core') = 'core'
              and s.interval = '4h'
              and s.label in ('Buy', 'Strong Buy')
              and coalesce(s.is_duplicate, false) = false
              and o.r_net is not null
            order by s.as_of asc
        """, (FREEZE_TIMESTAMP,))
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)

    n_trades = len(df)
    
    if n_trades > 0:
        df["r_net"] = pd.to_numeric(df["r_net"], errors="coerce")
        df["date"] = pd.to_datetime(df["as_of"]).dt.date
        mean_r = float(df["r_net"].mean())
        sum_r = float(df["r_net"].sum())

        # Effective N calculation based on daily clustering
        day_counts = df["date"].value_counts().values
        n_eff = int(round((day_counts.sum() ** 2) / (day_counts ** 2).sum()))

        # Day-block bootstrap CI
        ci_lower, ci_upper = run_day_block_bootstrap(df, rounds=BOOTSTRAP_ROUNDS)

        # Top 5 share of positive R
        pos_trades = df[df["r_net"] > 0]["r_net"].sort_values(ascending=False)
        pos_sum = pos_trades.sum()
        if pos_sum > 0:
            top5_share = float(pos_trades.head(5).sum() / pos_sum * 100.0)
        else:
            top5_share = 0.0

        # Scan phase breakdown
        mid_bar_df = df[df["scan_phase"] == "mid_bar"]
        bar_close_df = df[df["scan_phase"] == "bar_close"]
        n_mid = len(mid_bar_df)
        n_close = len(bar_close_df)
        mean_mid = float(mid_bar_df["r_net"].mean()) if n_mid > 0 else 0.0
        mean_close = float(bar_close_df["r_net"].mean()) if n_close > 0 else 0.0

        # Passes at close breakdown (8.4)
        passes_true_df = df[df["passes_at_close"] == True]
        passes_false_df = df[df["passes_at_close"] == False]
        n_pass_true = len(passes_true_df)
        n_pass_false = len(passes_false_df)
        mean_pass_true = float(passes_true_df["r_net"].mean()) if n_pass_true > 0 else 0.0
        mean_pass_false = float(passes_false_df["r_net"].mean()) if n_pass_false > 0 else 0.0
        ci_pass_true = run_day_block_bootstrap(passes_true_df, rounds=BOOTSTRAP_ROUNDS) if n_pass_true > 0 else (0.0, 0.0)
        ci_pass_false = run_day_block_bootstrap(passes_false_df, rounds=BOOTSTRAP_ROUNDS) if n_pass_false > 0 else (0.0, 0.0)
    else:
        mean_r = 0.0
        sum_r = 0.0
        n_eff = 0
        ci_lower = 0.0
        ci_upper = 0.0
        top5_share = 0.0
        n_mid = 0
        n_close = 0
        mean_mid = 0.0
        mean_close = 0.0
        n_pass_true = 0
        n_pass_false = 0
        mean_pass_true = 0.0
        mean_pass_false = 0.0
        ci_pass_true = (0.0, 0.0)
        ci_pass_false = (0.0, 0.0)

    # Decision rule:
    # Evaluate ONLY at earlier of N_eff >= 85 or date >= 2027-04-26
    # Before that point, output ONLY INCONCLUSIVE. Pre-registered PASS rule stays on all unique rows.
    is_eval_horizon = (n_eff >= TARGET_N_EFF) or (now_date_str >= TARGET_EVAL_DATE)
    
    if is_eval_horizon:
        if (mean_r >= 0.15) and (ci_lower > 0.0) and (top5_share <= 20.0):
            status = "PASS"
        else:
            status = "FAIL"
    else:
        status = "INCONCLUSIVE"

    result = {
        "timestamp": now_str,
        "n_trades": n_trades,
        "n_eff": n_eff,
        "mean_r": mean_r,
        "sum_r": sum_r,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "top5_share": top5_share,
        "scan_phase_breakdown": {
            "mid_bar": {"n": n_mid, "mean_r": mean_mid},
            "bar_close": {"n": n_close, "mean_r": mean_close},
        },
        "passes_at_close_breakdown": {
            "passes_true": {"n": n_pass_true, "mean_r": mean_pass_true, "ci": ci_pass_true},
            "passes_false": {"n": n_pass_false, "mean_r": mean_pass_false, "ci": ci_pass_false},
        },
        "is_eval_horizon": is_eval_horizon,
        "status": status,
    }

    print("=" * 80)
    print("PHASE 8.4 — FORWARD EVALUATION RUN (ENRICHED LOGGING)")
    print(f"Timestamp (UTC): {now_str}")
    print(f"Post-Freeze Filter: as_of >= {FREEZE_TIMESTAMP}")
    print(f"Target Evaluation Date: {TARGET_EVAL_DATE} | Target N_eff: {TARGET_N_EFF}")
    print("=" * 80)
    print(f"Unique Trades (n):           {n_trades} (pre-registered PASS rule cohort)")
    print(f"Effective Trades (N_eff):    {n_eff} / {TARGET_N_EFF}")
    print(f"Mean Net R (All Unique):     {mean_r:+.4f} R (Required: >= +0.1500 R)")
    print(f"95% Day-Block CI:            [{ci_lower:+.4f}, {ci_upper:+.4f}] (Required: lower > 0)")
    print(f"Top-5 Positive R Share:      {top5_share:.1f}% (Required: <= 20.0%)")
    print("-" * 80)
    print("Passes-at-Close Breakdown (8.4):")
    print(f"  - passes_at_close = True:  n={n_pass_true:<3} | Mean R={mean_pass_true:+.4f} R | CI=[{ci_pass_true[0]:+.4f}, {ci_pass_true[1]:+.4f}]")
    print(f"  - passes_at_close = False: n={n_pass_false:<3} | Mean R={mean_pass_false:+.4f} R | CI=[{ci_pass_false[0]:+.4f}, {ci_pass_false[1]:+.4f}]")
    print("-" * 80)
    print("Scan Phase Breakdown:")
    print(f"  - mid_bar:   n={n_mid:<3} | Mean R={mean_mid:+.4f} R")
    print(f"  - bar_close: n={n_close:<3} | Mean R={mean_close:+.4f} R")
    print("-" * 80)
    print(f"Decision Status:             {status}")
    if not is_eval_horizon:
        print("Reason: Evaluation horizon not yet reached (N_eff < 85 and current date < 2027-04-26).")
        print("Rule R6 Pre-Registration: STRICTLY NO INTERIM DECISIONS PERMITTED.")
    print("=" * 80)

    if append_log:
        append_to_forward_log(result)

    return result


def append_to_forward_log(res: dict) -> None:
    forward_log_path = root_dir / "docs" / "FORWARD_LOG.md"
    if not forward_log_path.exists():
        return

    ci_str = f"[{res['ci_lower']:+.4f}, {res['ci_upper']:+.4f}]" if res["n_trades"] > 0 else "N/A"
    mean_str = f"{res['mean_r']:+.4f} R" if res["n_trades"] > 0 else "N/A"
    top5_str = f"{res['top5_share']:.1f}%" if res["n_trades"] > 0 else "N/A"

    table_row = (
        f"| {res['timestamp'][:19]} | Post-Freeze Forward | {res['n_trades']} | {res['n_eff']} | "
        f"{mean_str} | {ci_str} | Top5: {top5_str} (mid:{res['scan_phase_breakdown']['mid_bar']['n']}, close:{res['scan_phase_breakdown']['bar_close']['n']}) | {res['status']} |\n"
    )

    with open(forward_log_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Insert under Forward Evaluation Summary table
    if "## Forward Evaluation Summary" in content:
        parts = content.split("## Forward Evaluation Summary\n\n")
        header_and_table = parts[1].split("\n\n---\n\n")
        table_lines = header_and_table[0].strip().split("\n")
        table_lines.append(table_row.strip())
        new_table = "\n".join(table_lines) + "\n\n---\n\n" + header_and_table[1]
        new_content = parts[0] + "## Forward Evaluation Summary\n\n" + new_table
        
        # Add log history entry
        history_entry = (
            f"\n### Forward Audit Run: {res['timestamp'][:19]}Z\n"
            f"- **Sample Size:** $n={res['n_trades']}$ unique post-freeze trades ($N_{{\\text{{eff}}}}={res['n_eff']}$ / 85 target)\n"
            f"- **Performance:** Mean Net $R={mean_str}$, 95% Day-Block CI $={ci_str}$\n"
            f"- **Concentration:** Top-5 positive trade share $={top5_str}$\n"
            f"- **Execution Scan Phases:** `mid_bar` $n={res['scan_phase_breakdown']['mid_bar']['n']}$, `bar_close` $n={res['scan_phase_breakdown']['bar_close']['n']}$\n"
            f"- **Operational Evaluation Decision:** `{res['status']}` (Evaluation horizon date: {TARGET_EVAL_DATE})\n"
        )
        new_content = new_content.strip() + "\n" + history_entry

        with open(forward_log_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Successfully appended weekly evaluation run to {forward_log_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Post-Freeze Forward Trades")
    parser.add_argument("--append", action="store_true", help="Append run output to docs/FORWARD_LOG.md")
    args = parser.parse_args()
    evaluate_forward(append_log=args.append)
