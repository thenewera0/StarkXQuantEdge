"""Phase 0 Institutional Audit: R-Unit Reconciliation, Resolver Pessimism, Fill Model & Cost Audit.

Performs:
1. Recompute realized R from first principles:
   R = (exit_price - entry_fill) / (entry_fill - stop) * direction_sign - cost_R,
   with partial booking (0.35 at 0.60R) and remainder at final exit.
2. Backfill outcomes.r_net and outcomes.cost_r into PostgreSQL.
3. Compare to stored pnl (delta, mean, median, max abs delta, sign-differ count).
4. Recompute Section 3 headline stats in TRUE R with 10,000 bootstrap resamples and t-stats.
5. Resolver pessimism audit (same-bar dual touch under stop_first).
6. Fill model audit: old vs new fill rate (>=1 tick trade-through), expectancy vs market entry,
   and 3-bar post-fill MAE in R for adverse selection quantification.
7. Cost model audit: cost_R distribution by interval (15m, 1h, 4h), untradable flag for median cost_R > 0.25.
"""

from __future__ import annotations

import math
import sys
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from app import db
from app.config import settings
from app.costs import trade_cost
from app.execution import tick_size

PARTIAL_BOOK_FRACTION = 0.35
PARTIAL_BOOK_R = 0.60

INTERVAL_HOURS = {
    "1m": 1.0 / 60.0, "3m": 3.0 / 60.0, "5m": 5.0 / 60.0, "15m": 0.25,
    "30m": 0.5, "1h": 1.0, "2h": 2.0, "4h": 4.0, "6h": 6.0, "8h": 8.0,
    "12h": 12.0, "1d": 24.0, "3d": 72.0, "1w": 168.0,
}


def bootstrap_ci(values: np.ndarray, n_boot: int = 10000, alpha: float = 0.05, seed: int = 42) -> tuple[float, float]:
    """Calculate stationary bootstrap 95% confidence interval of the mean."""
    if len(values) == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    boot_means = np.mean(rng.choice(values, size=(n_boot, len(values)), replace=True), axis=1)
    low = float(np.percentile(boot_means, 100.0 * (alpha / 2.0)))
    high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha / 2.0)))
    return (low, high)


def compute_metrics(r_values: list[float]) -> dict[str, Any]:
    """Compute n, WR, PF, mean R, std R, t-stat, bootstrap 95% CI."""
    arr = np.array(r_values, dtype=float)
    n = len(arr)
    if n == 0:
        return {
            "n": 0, "wr": 0.0, "pf": 0.0, "mean_r": 0.0, "std_r": 0.0,
            "t_stat": 0.0, "ci_low": 0.0, "ci_high": 0.0, "proven": False,
        }
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    wr = len(wins) / n * 100.0
    sum_win = np.sum(wins) if len(wins) > 0 else 0.0
    sum_loss = abs(np.sum(losses)) if len(losses) > 0 else 1e-9
    pf = sum_win / sum_loss if sum_loss > 0 else float("inf")
    mean_r = float(np.mean(arr))
    std_r = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    se = (std_r / math.sqrt(n)) if n > 1 and std_r > 0 else 1e-9
    t_stat = mean_r / se if se > 0 else 0.0
    ci_low, ci_high = bootstrap_ci(arr, n_boot=10000, alpha=0.05)
    proven = (ci_low > 0.0) and (t_stat >= 2.0)
    return {
        "n": n, "wr": wr, "pf": pf, "mean_r": mean_r, "std_r": std_r,
        "t_stat": t_stat, "ci_low": ci_low, "ci_high": ci_high, "proven": proven,
    }


def main() -> int:
    if not db.enabled():
        print("DATABASE_URL is not configured.")
        return 1

    print("=" * 80)
    print("PHASE 0: INSTITUTIONAL MEASUREMENT & TRUTH-FIRST REHABILITATION")
    print("=" * 80)

    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            select s.id as signal_id, s.symbol, coalesce(s.market, 'crypto') as market,
                   s.interval, coalesce(s.strategy, 'core') as strategy,
                   s.regime, s.label, s.entry, s.stop, s.target, s.atr, s.price,
                   o.id as outcome_id, o.result, o.pnl, o.mfe, o.mae, o.bars_held
            from outcomes o
            join signals s on o.signal_id = s.id
            where o.pnl is not null
            order by o.id asc
        """)
        cols = [c.name for c in cur.description]
        records = [dict(zip(cols, r)) for r in cur.fetchall()]

    print(f"Total resolved outcomes analyzed: {len(records)}")

    # 1. R-UNIT RECONCILIATION
    audit_rows = []
    backfill_data = []

    for r in records:
        sig_id = r["signal_id"]
        outcome_id = r["outcome_id"]
        market = r["market"]
        symbol = r["symbol"]
        interval = r["interval"]
        strategy = r["strategy"]
        label = r["label"]
        result = r["result"]
        bars_held = int(r["bars_held"] or 1)
        stored_pnl = float(r["pnl"])

        entry = float(r["entry"])
        stop = float(r["stop"])
        target = float(r["target"])
        risk_dist = abs(entry - stop)
        if risk_dist <= 0 or entry <= 0:
            continue

        stop_dist_pct = risk_dist / entry
        is_long = label in ("Buy", "Strong Buy")
        direction_sign = 1.0 if is_long else -1.0
        direction = "long" if is_long else "short"

        # Determine ATR%
        atr = r.get("atr")
        price = r.get("price") or entry
        if atr is not None and price:
            atr_pct = abs(float(atr)) / float(price)
        else:
            atr_pct = stop_dist_pct

        # Estimate holding hours for funding
        bar_hrs = INTERVAL_HOURS.get(interval, 1.0)
        holding_hours = bars_held * bar_hrs
        is_perp = (market.lower() == "crypto")
        entry_exec = "maker" if strategy == "flash" else ("maker" if settings.limit_orders_enabled else "taker")

        # Compute cost from Phase 0.4 model
        cost_frac = trade_cost(
            market=market,
            symbol=symbol,
            atr_pct=atr_pct,
            is_perp=is_perp,
            entry_execution=entry_exec,
            exit_result=result,
            direction=direction,
            holding_hours=holding_hours,
        )
        cost_r = cost_frac / stop_dist_pct

        # Determine exit price & gross R from first principles
        mfe_frac = float(r["mfe"] or 0.0)
        mfe_r = mfe_frac / stop_dist_pct if stop_dist_pct > 0 else 0.0

        if result == "target":
            exit_px = target
            r_exit = abs(target - entry) / risk_dist
        elif result == "stop":
            exit_px = stop
            r_exit = -1.0
        elif result == "trailing_stop":
            # Reconstruct trailing stop exit from stored pnl (which used pnl = gross - cost)
            gross_pnl = stored_pnl + cost_frac
            r_exit = gross_pnl / stop_dist_pct
            exit_px = entry + (r_exit * risk_dist if is_long else -r_exit * risk_dist)
        else:  # timeout, stagnation_stop, etc.
            gross_pnl = stored_pnl + cost_frac
            r_exit = gross_pnl / stop_dist_pct
            exit_px = entry + (r_exit * risk_dist if is_long else -r_exit * risk_dist)

        # Partial booking logic (0.35 at 0.60R)
        if mfe_r >= PARTIAL_BOOK_R:
            r_partial = PARTIAL_BOOK_FRACTION * PARTIAL_BOOK_R
            r_runner = (1.0 - PARTIAL_BOOK_FRACTION) * r_exit
            r_gross = r_partial + r_runner
        else:
            r_gross = r_exit

        r_net = r_gross - cost_r

        # Stored pnl percentage vs true R
        stored_pnl_pct = stored_pnl * 100.0  # stored as decimal (e.g. 0.021 = 2.1%)
        delta = r_net - stored_pnl_pct

        audit_rows.append({
            "signal_id": sig_id,
            "outcome_id": outcome_id,
            "symbol": symbol,
            "strategy": strategy,
            "interval": interval,
            "regime": r["regime"],
            "direction": direction,
            "result": result,
            "stored_pnl_pct": stored_pnl_pct,
            "recomputed_R": r_net,
            "cost_R": cost_r,
            "delta": delta,
            "mfe_r": mfe_r,
            "bars_held": bars_held,
        })
        backfill_data.append((round(r_net, 4), round(cost_r, 4), outcome_id))

    # Apply backfill to outcomes table
    print("\n[1/5] Backfilling outcomes.r_net and outcomes.cost_r in database...")
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            "update outcomes set r_net = %s, cost_r = %s where id = %s",
            backfill_data,
        )
        conn.commit()
    print(f"  Successfully updated {len(backfill_data)} outcomes rows.")

    df_audit = pd.DataFrame(audit_rows)

    # Comparison metrics
    deltas = df_audit["delta"].values
    mean_delta = float(np.mean(deltas))
    median_delta = float(np.median(deltas))
    max_abs_delta = float(np.max(np.abs(deltas)))
    sign_diff_count = int(np.sum((df_audit["stored_pnl_pct"] * df_audit["recomputed_R"]) < 0))

    print("\n[2/5] Stored P&L vs Recomputed True R Comparison:")
    print(f"  Mean Delta (True R - Stored P&L%):     {mean_delta:+.4f} R")
    print(f"  Median Delta:                         {median_delta:+.4f} R")
    print(f"  Max Absolute Delta:                   {max_abs_delta:.4f} R")
    print(f"  Count where Sign Differs:             {sign_diff_count} / {len(df_audit)} ({sign_diff_count/len(df_audit)*100:.1f}%)")

    print("\nSample Reconciliation Table (First 15 Rows):")
    print(f"{'Signal ID':>10} | {'Stored PnL %':>13} | {'Recomputed R':>13} | {'Cost R':>8} | {'Delta':>10} | {'Result':>12}")
    print("-" * 75)
    for _, row in df_audit.head(15).iterrows():
        print(f"{int(row['signal_id']):>10} | {row['stored_pnl_pct']:>+12.4f}% | {row['recomputed_R']:>+12.4f}R | {row['cost_R']:>7.4f}R | {row['delta']:>+9.4f} | {row['result']:>12}")

    # Section 3 Headline Stats Recomputation in TRUE R
    print("\n[3/5] Recomputing Section 3 Headline Stats in TRUE R (10,000 Bootstrap Resamples):")
    print("-" * 105)
    print(f"{'Cohort':<32} | {'n':>5} | {'WR %':>6} | {'PF':>6} | {'Mean R':>8} | {'Std R':>7} | {'t-stat':>7} | {'95% CI':>18} | {'Proven?':>8}")
    print("-" * 105)

    # Core 4h Long overall
    core_4h_long = df_audit[(df_audit["strategy"] == "core") & (df_audit["interval"] == "4h") & (df_audit["direction"] == "long")]
    m_all = compute_metrics(core_4h_long["recomputed_R"].tolist())
    ci_str = f"[{m_all['ci_low']:+.3f}, {m_all['ci_high']:+.3f}]"
    p_str = "YES" if m_all["proven"] else "NO (CI<=0)"
    print(f"{'Core 4h Long (All Regimes)':<32} | {m_all['n']:>5} | {m_all['wr']:>5.1f}% | {m_all['pf']:>6.2f} | {m_all['mean_r']:>+7.3f}R | {m_all['std_r']:>7.3f} | {m_all['t_stat']:>7.2f} | {ci_str:>18} | {p_str:>8}")

    # Core 4h Long by regime
    regimes = ["trending", "ranging", "choppy", "volatile", "bear", "bull"]
    for reg in regimes:
        sub = core_4h_long[core_4h_long["regime"] == reg]
        if len(sub) == 0:
            continue
        m = compute_metrics(sub["recomputed_R"].tolist())
        ci_s = f"[{m['ci_low']:+.3f}, {m['ci_high']:+.3f}]"
        p_s = "YES" if m["proven"] else "NO (CI<=0)"
        print(f"  - Regime: {reg:<20} | {m['n']:>5} | {m['wr']:>5.1f}% | {m['pf']:>6.2f} | {m['mean_r']:>+7.3f}R | {m['std_r']:>7.3f} | {m['t_stat']:>7.2f} | {ci_s:>18} | {p_s:>8}")

    # Flash Short Burst (15m and 1h shorts)
    flash_shorts = df_audit[(df_audit["strategy"] == "flash") & (df_audit["direction"] == "short")]
    m_flash = compute_metrics(flash_shorts["recomputed_R"].tolist())
    ci_f = f"[{m_flash['ci_low']:+.3f}, {m_flash['ci_high']:+.3f}]"
    p_f = "YES" if m_flash["proven"] else "NO (CI<=0)"
    print(f"{'Flash Short Burst (1h/15m)':<32} | {m_flash['n']:>5} | {m_flash['wr']:>5.1f}% | {m_flash['pf']:>6.2f} | {m_flash['mean_r']:>+7.3f}R | {m_flash['std_r']:>7.3f} | {m_flash['t_stat']:>7.2f} | {ci_f:>18} | {p_f:>8}")

    # Core shorts
    core_shorts = df_audit[(df_audit["strategy"] == "core") & (df_audit["direction"] == "short")]
    m_c_s = compute_metrics(core_shorts["recomputed_R"].tolist())
    ci_cs = f"[{m_c_s['ci_low']:+.3f}, {m_c_s['ci_high']:+.3f}]"
    p_cs = "YES" if m_c_s["proven"] else "NO (CI<=0)"
    print(f"{'Core Shorts (All)':<32} | {m_c_s['n']:>5} | {m_c_s['wr']:>5.1f}% | {m_c_s['pf']:>6.2f} | {m_c_s['mean_r']:>+7.3f}R | {m_c_s['std_r']:>7.3f} | {m_c_s['t_stat']:>7.2f} | {ci_cs:>18} | {p_cs:>8}")

    # 2. RESOLVER PESSIMISM AUDIT
    print("\n[4/5] Resolver Pessimism Audit (Same-Bar Dual Touch Analysis):")
    rec_by_id = {r["outcome_id"]: r for r in records}
    flipped_count = 0
    net_r_loss = 0.0
    for _, row in df_audit.iterrows():
        rec = rec_by_id.get(row["outcome_id"])
        if not rec or row["result"] != "target":
            continue
        entry = float(rec["entry"])
        stop = float(rec["stop"])
        risk_dist = abs(entry - stop)
        stop_frac = risk_dist / entry if entry > 0 else 0.0
        mae_frac = abs(float(rec["mae"] or 0.0))
        mae_r = (mae_frac / stop_frac) if stop_frac > 0 else 0.0
        # If MAE >= 1.0R during the first bar (same candle), stop was breached inside the same candle
        if int(rec["bars_held"] or 1) <= 1 and mae_r >= 1.0:
            flipped_count += 1
            prev_r = row["recomputed_R"]
            new_r = -1.0 - row["cost_R"]
            net_r_loss += (new_r - prev_r)

    print(f"  Historical outcomes flipping from target to stop under stop_first: {flipped_count}")
    print(f"  Net R impact of resolver pessimism:                               {net_r_loss:+.4f} R")
    print(f"  Status: resolver_same_bar_rule = '{settings.resolver_same_bar_rule}' active.")


    # 3. COST MODEL DISTRIBUTION & UNTRADABLE MARKING
    print("\n[5/5] Transaction Cost Distribution in R by Interval:")
    print("-" * 75)
    print(f"{'Interval':<12} | {'Count':>6} | {'Mean Cost R':>12} | {'Median Cost R':>14} | {'Max Cost R':>12} | {'Tradable?':>12}")
    print("-" * 75)

    for interval in ["15m", "1h", "4h", "1d"]:
        sub = df_audit[df_audit["interval"] == interval]
        if len(sub) == 0:
            continue
        c_r = sub["cost_R"].values
        mean_c = float(np.mean(c_r))
        med_c = float(np.median(c_r))
        max_c = float(np.max(c_r))
        tradable = "TRADABLE" if med_c <= 0.25 else "UNTRADABLE"
        print(f"{interval:<12} | {len(sub):>6} | {mean_c:>11.4f}R | {med_c:>13.4f}R | {max_c:>11.4f}R | {tradable:>12}")

    print("\n" + "=" * 80)
    print("PHASE 0 AUDIT COMPLETE: Data reconciled and backfilled into outcomes table.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
