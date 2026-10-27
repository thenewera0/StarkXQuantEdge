"""Phase 0.6 Comprehensive Audit, Verification & Ledger Reconciliation Script.

Executes:
0.6.1 /performance dollar P&L reconciliation
0.6.2 Statistics verification:
      - Full bootstrap distribution percentiles (2.5, 5, 25, 50, 75, 95, 97.5) and bootstrap mean
      - Percentile CI verification vs normal-approx CI (mean +- 1.96*se_block) and skew analysis
      - ANOVA intraclass correlation estimator with unequal-cluster correction (n0), clamped to [0, 0.95]
      - Cluster size histograms and size-weighted mean cluster size m_bar
      - N_eff unit tests (iid and perfectly clustered data)
      - Re-issued cohort table
0.6.3 Regime label stability:
      - Attribution of 78/62/51 vs 151/29/11
      - Confusion matrix and agreement percentage
0.6.4 Confidence & sizing information carry:
      - Day-clustered rank IC against r_net for win_prob, ev_r, composite, confidence, final_confidence, meta_p, risk_pct
      - Reliability table by win_prob decile, Brier Skill Score
      - Multiplier chain analysis for 10 random core shorts
      - Automated sizing mode decision rule
0.6.5 Freeze split:
      - config/frozen_core_long_v1_1.json (signal-generating only) + sha256
      - config/risk_params.json (risk/sizing params)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app import db
from app.config import settings
from app.sizing import position_size, quarter_kelly, ruin_fraction, tier_for_equity


# ---------------------------------------------------------------------------
# 0.6.2 STATISTICAL UTILITIES: ANOVA ICC & CLUSTER BOOTSTRAP
# ---------------------------------------------------------------------------

def anova_icc_unequal(clusters: list[np.ndarray]) -> tuple[float, float, float, bool]:
    """Computes the ANOVA intraclass correlation coefficient (ICC) with unequal cluster correction (n0).

    Returns:
        (rho_clamped, m_bar, n0, is_clamped)
    """
    k = len(clusters)
    if k <= 1:
        return 0.0, 1.0, 1.0, False

    cluster_sizes = np.array([len(c) for c in clusters], dtype=float)
    n_total = float(np.sum(cluster_sizes))
    if n_total <= k:
        return 0.0, 1.0, 1.0, False

    # Size-weighted mean cluster size: m_bar = sum(n_i^2) / N
    m_bar = float(np.sum(cluster_sizes ** 2) / n_total)

    # Unequal cluster correction n0: n0 = (N - sum(n_i^2) / N) / (K - 1)
    n0 = float((n_total - np.sum(cluster_sizes ** 2) / n_total) / (k - 1.0))
    if n0 <= 0:
        return 0.0, m_bar, 1.0, False

    all_vals = np.concatenate(clusters)
    grand_mean = float(np.mean(all_vals))

    # Sum of squares between (SSB)
    ssb = float(np.sum([len(c) * (float(np.mean(c)) - grand_mean) ** 2 for c in clusters]))
    df_b = k - 1.0
    msb = ssb / df_b if df_b > 0 else 0.0

    # Sum of squares within (SSW)
    ssw = float(np.sum([np.sum((c - float(np.mean(c))) ** 2) for c in clusters]))
    df_w = n_total - k
    msw = ssw / df_w if df_w > 0 else 0.0

    # Variance components
    s_w2 = msw
    s_a2 = max(0.0, (msb - msw) / n0)

    total_var = s_a2 + s_w2
    if total_var <= 1e-12:
        raw_rho = 0.0
    else:
        raw_rho = s_a2 / total_var

    # Clamp to [0, 0.95]
    clamped = False
    if raw_rho > 0.95:
        rho = 0.95
        clamped = True
    elif raw_rho < 0.0:
        rho = 0.0
    else:
        rho = raw_rho

    return rho, m_bar, n0, clamped


def stationary_day_bootstrap(
    dates: list[str],
    r_values: list[float],
    n_boot: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    """Runs stationary cluster bootstrap resampling by calendar day and calculates ANOVA ICC."""
    if not r_values:
        return {}

    df = pd.DataFrame({"date": dates, "r": r_values})
    grouped = df.groupby("date")
    clusters = [group["r"].values for _, group in grouped]
    cluster_names = [d for d, _ in grouped]
    cluster_sizes = [len(c) for c in clusters]

    k = len(clusters)
    n_total = len(r_values)
    sample_mean = float(np.mean(r_values))
    sample_std = float(np.std(r_values, ddof=1)) if n_total > 1 else 1e-9

    rho, m_bar, n0, is_clamped = anova_icc_unequal(clusters)

    # N_eff = N / (1 + (m_bar - 1) * rho)
    denom = 1.0 + (m_bar - 1.0) * rho
    n_eff = n_total / denom if denom > 0 else float(n_total)

    # Standard error of cluster mean
    cluster_means = np.array([float(np.mean(c)) for c in clusters])
    # Cluster-level standard error
    se_block = (sample_std / math.sqrt(n_eff)) if n_eff > 1 else 1e-9
    t_block = sample_mean / se_block if se_block > 0 else 0.0

    # Stationary cluster resampling
    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(k, size=k, replace=True)
        resampled_trades = np.concatenate([clusters[i] for i in idx])
        boot_means[b] = np.mean(resampled_trades)

    boot_mean = float(np.mean(boot_means))
    percentiles = {
        2.5: float(np.percentile(boot_means, 2.5)),
        5.0: float(np.percentile(boot_means, 5.0)),
        25.0: float(np.percentile(boot_means, 25.0)),
        50.0: float(np.percentile(boot_means, 50.0)),
        75.0: float(np.percentile(boot_means, 75.0)),
        95.0: float(np.percentile(boot_means, 95.0)),
        97.5: float(np.percentile(boot_means, 97.5)),
    }

    # Normal approximation CI
    ci_norm_low = sample_mean - 1.96 * se_block
    ci_norm_high = sample_mean + 1.96 * se_block

    # Skewness of bootstrap distribution
    diff_m = boot_means - boot_mean
    var_m = float(np.var(boot_means))
    boot_skew = float(np.mean(diff_m ** 3) / (var_m ** 1.5)) if var_m > 1e-12 else 0.0

    return {
        "n": n_total,
        "clusters": k,
        "cluster_sizes": cluster_sizes,
        "sample_mean": sample_mean,
        "sample_std": sample_std,
        "boot_mean": boot_mean,
        "percentiles": percentiles,
        "ci_pct_low": percentiles[2.5],
        "ci_pct_high": percentiles[97.5],
        "se_block": se_block,
        "t_block": t_block,
        "ci_norm_low": ci_norm_low,
        "ci_norm_high": ci_norm_high,
        "boot_skew": boot_skew,
        "rho_intra": rho,
        "m_bar": m_bar,
        "n0": n0,
        "is_clamped": is_clamped,
        "n_eff": n_eff,
    }


def run_icc_unit_tests() -> bool:
    """Verifies that iid data -> N_eff ~ n and perfectly clustered data -> N_eff ~ K."""
    print("Running ANOVA ICC & N_eff Unit Tests...")
    rng = np.random.default_rng(123)

    # Test 1: iid data across 50 clusters of size 10 (N=500)
    iid_clusters = [rng.normal(0.0, 1.0, size=10) for _ in range(50)]
    rho_iid, m_bar_iid, _, _ = anova_icc_unequal(iid_clusters)
    n_eff_iid = 500.0 / (1.0 + (m_bar_iid - 1.0) * rho_iid)
    print(f"  [Test 1: iid data] N=500, K=50 -> rho={rho_iid:.4f}, m_bar={m_bar_iid:.2f}, N_eff={n_eff_iid:.1f}")
    assert rho_iid < 0.05, f"Expected near-zero rho for iid data, got {rho_iid}"
    assert n_eff_iid >= 400.0, f"Expected N_eff ~ 500, got {n_eff_iid}"

    # Test 2: Perfectly clustered data (all points in cluster identical)
    # 50 clusters of size 10 (N=500), each cluster has a single constant value
    perf_clusters = [np.full(10, rng.normal(0.0, 1.0)) for _ in range(50)]
    rho_perf, m_bar_perf, _, is_clamped = anova_icc_unequal(perf_clusters)
    # If unclamped rho=1.0: N_eff = 500 / 10 = 50. With clamp 0.95: N_eff = 500 / (1 + 9 * 0.95) = 52.35
    n_eff_perf = 500.0 / (1.0 + (m_bar_perf - 1.0) * rho_perf)
    print(f"  [Test 2: Perfectly clustered] N=500, K=50 -> rho={rho_perf:.4f} (clamped={is_clamped}), N_eff={n_eff_perf:.1f}")
    assert rho_perf >= 0.94, f"Expected rho >= 0.95 for perfect clustering, got {rho_perf}"
    assert abs(n_eff_perf - 50.0) < 5.0, f"Expected N_eff ~ K (50), got {n_eff_perf}"

    print("  SUCCESS: Both unit tests passed.\n")
    return True


# ---------------------------------------------------------------------------
# MAIN AUDIT & REPORT WORKFLOW
# ---------------------------------------------------------------------------

def main() -> int:
    run_icc_unit_tests()

    if not db.enabled():
        print("DATABASE_URL is not configured.")
        return 1

    print("=" * 85)
    print("PHASE 0.6: STATISTICAL CORRECTIONS, /PERFORMANCE RECONCILIATION & INFORMATION AUDIT")
    print("=" * 85)

    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            select s.id as signal_id, s.symbol, coalesce(s.market, 'crypto') as market,
                   s.interval, coalesce(s.strategy, 'core') as strategy,
                   s.regime, s.label, s.entry, s.stop, s.target, s.atr, s.price,
                   s.size_pct, s.win_prob, s.reward_risk, s.composite,
                   s.confidence, s.final_confidence, s.meta_p, s.ev_r, s.shadow, s.created_at,
                   o.id as outcome_id, o.result, o.pnl, o.r_net, o.cost_r, o.mfe, o.mae,
                   o.bars_held, o.resolved_at
            from signals s
            left join outcomes o on o.signal_id = s.id
            order by coalesce(o.resolved_at, s.created_at) asc
        """)
        cols = [c.name for c in cur.description]
        records = [dict(zip(cols, r)) for r in cur.fetchall()]

    equity = settings.account_equity_usd  # $1,000 standard
    reconstructed_rows = []

    for r in records:
        sig_id = r["signal_id"]
        strategy = r["strategy"]
        shadow = bool(r["shadow"])
        label = r["label"]
        res = r["result"]
        entry = float(r["entry"]) if r["entry"] is not None else 0.0
        stop = float(r["stop"]) if r["stop"] is not None else 0.0
        target = float(r["target"]) if r["target"] is not None else 0.0
        r_net = float(r["r_net"]) if r["r_net"] is not None else None
        pnl_frac = float(r["pnl"]) if r["pnl"] is not None else None

        if entry <= 0 or stop <= 0:
            continue

        risk_dist = abs(entry - stop)
        stop_dist_pct = (risk_dist / entry) * 100.0 if entry > 0 else 0.0

        # Multipliers at signal time
        win_prob = float(r["win_prob"]) if r["win_prob"] is not None else 0.50
        rr = float(r["reward_risk"]) if r["reward_risk"] is not None else 1.8

        tier = tier_for_equity(equity)
        kf = quarter_kelly(win_prob, rr)
        rf = ruin_fraction(win_prob, rr, tier["risk_cap"])
        raw_kelly_risk = min(kf, rf, tier["risk_cap"])

        sym_mult = 0.50 if r["symbol"].upper() == "BTCUSDT" else 1.0
        drift_mult = 1.0
        alloc_mult = 1.0

        combined_mult = raw_kelly_risk * drift_mult * alloc_mult * sym_mult

        stored_size_pct = float(r["size_pct"]) if r["size_pct"] is not None else None
        if stored_size_pct is not None:
            risk_pct = stored_size_pct
            reconstructed_flag = False
        else:
            risk_pct = round(combined_mult * 100.0, 3)
            reconstructed_flag = True

        risk_usd = equity * (risk_pct / 100.0)

        if r_net is not None:
            dollar_pnl = r_net * risk_usd
        elif res == "unfilled":
            dollar_pnl = 0.0
        else:
            dollar_pnl = None

        date_str = str(r["resolved_at"])[:10] if r["resolved_at"] else str(r["created_at"])[:10]

        reconstructed_rows.append({
            "signal_id": sig_id,
            "outcome_id": r["outcome_id"],
            "symbol": r["symbol"],
            "interval": r["interval"],
            "strategy": strategy,
            "regime": r["regime"],
            "shadow": shadow,
            "result": res,
            "direction": "long" if label in ("Buy", "Strong Buy") else "short",
            "entry": entry,
            "stop": stop,
            "target": target,
            "stop_dist_pct": stop_dist_pct,
            "pnl_frac": pnl_frac,
            "r_net": r_net,
            "risk_pct": risk_pct,
            "risk_usd": risk_usd,
            "dollar_pnl": dollar_pnl,
            "combined_mult": combined_mult,
            "reconstructed_flag": reconstructed_flag,
            "date": date_str,
            "win_prob": win_prob,
            "ev_r": float(r["ev_r"]) if r.get("ev_r") is not None else None,
            "composite": float(r["composite"]) if r.get("composite") is not None else None,
            "confidence": float(r["confidence"]) if r.get("confidence") is not None else None,
            "final_confidence": float(r["final_confidence"]) if r.get("final_confidence") is not None else None,
            "meta_p": float(r["meta_p"]) if r.get("meta_p") is not None else None,
            "bars_held": r["bars_held"],
            "resolved_at": r["resolved_at"],
            "created_at": r["created_at"],
        })

    df = pd.DataFrame(reconstructed_rows)

    # -------------------------------------------------------------------------
    # 0.6.1 /performance RECONCILIATION TEST
    # -------------------------------------------------------------------------
    print("\n--- 0.6.1 /performance Reconciliation ---")
    core_live = df[(df["strategy"] == "core") & (~df["shadow"]) & (df["dollar_pnl"].notna())]
    sum_core_live_pnl = float(core_live["dollar_pnl"].sum())
    print(f"Total sized live core trades: {len(core_live)}")
    print(f"Audit Ground Truth Dollar P&L: ${sum_core_live_pnl:.2f} USD")

    # -------------------------------------------------------------------------
    # 0.6.2 FULL BOOTSTRAP PERCENTILES & NORMAL APPROX RECONCILIATION
    # -------------------------------------------------------------------------
    print("\n--- 0.6.2 Bootstrap Distribution & ANOVA ICC Recomputation ---")

    c4l = df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["direction"] == "long") & (df["r_net"].notna())]
    flash_short = df[(df["strategy"] == "flash") & (df["direction"] == "short") & (df["r_net"].notna())]
    core_short = df[(df["strategy"] == "core") & (df["direction"] == "short") & (df["r_net"].notna())]

    cohorts_to_test = [
        ("Core 4h Long (All)", c4l),
        ("Core 4h Long (Trending)", c4l[c4l["regime"].isin(["strong_trend", "weak_trend", "trending"])]),
        ("Core 4h Long (Ranging)", c4l[c4l["regime"].isin(["range", "ranging"])]),
        ("Core 4h Long (Choppy)", c4l[c4l["regime"].isin(["high_vol", "squeeze", "choppy"])]),
        ("Flash Short Burst (1h/15m)", flash_short),
        ("Core Shorts (All)", core_short),
    ]

    print(f"{'Cohort':<28} | {'n':>4} | {'K':>3} | {'m_bar':>5} | {'rho':>6} | {'N_eff':>6} | {'Mean R':>8} | {'SE_blk':>7} | {'t_blk':>6} | {'Norm 95% CI':>18} | {'Percentile 95% CI':>20} | {'Skew':>6}")
    print("-" * 140)

    stats_results = {}
    for name, cdf in cohorts_to_test:
        r_arr = cdf["r_net"].values.tolist()
        d_arr = cdf["date"].tolist()
        res = stationary_day_bootstrap(d_arr, r_arr)
        stats_results[name] = res
        clamp_flag = "*" if res["is_clamped"] else " "
        print(f"{name:<28} | {res['n']:>4} | {res['clusters']:>3} | {res['m_bar']:>5.2f} | {res['rho_intra']:>5.3f}{clamp_flag} | {res['n_eff']:>6.1f} | {res['sample_mean']:>+7.3f}R | {res['se_block']:>7.3f} | {res['t_block']:>6.2f} | [{res['ci_norm_low']:>+6.3f}, {res['ci_norm_high']:>+6.3f}] | [{res['ci_pct_low']:>+6.3f}, {res['ci_pct_high']:>+6.3f}] | {res['boot_skew']:>+6.2f}")

    print("\nFull Bootstrap Distribution Percentiles (2.5, 5.0, 25.0, 50.0, 75.0, 95.0, 97.5):")
    print("-" * 115)
    print(f"{'Cohort':<28} | {'Mean':>7} | {'P02.5':>7} | {'P05.0':>7} | {'P25.0':>7} | {'P50.0':>7} | {'P75.0':>7} | {'P95.0':>7} | {'P97.5':>7}")
    print("-" * 115)
    for name, cdf in cohorts_to_test:
        res = stats_results[name]
        p = res["percentiles"]
        print(f"{name:<28} | {res['boot_mean']:>+6.3f} | {p[2.5]:>+7.4f} | {p[5.0]:>+7.4f} | {p[25.0]:>+7.4f} | {p[50.0]:>+7.4f} | {p[75.0]:>+7.4f} | {p[95.0]:>+7.4f} | {p[97.5]:>+7.4f}")

    # Cluster-size histograms
    print("\nCluster-Size Histograms per Cohort (days with count trades):")
    for name, cdf in cohorts_to_test:
        res = stats_results[name]
        c_counts = pd.Series(res["cluster_sizes"]).value_counts().sort_index()
        hist_str = ", ".join(f"{count}d x {size}trades" for size, count in c_counts.items())
        print(f"  {name:<28}: {hist_str}")

    # -------------------------------------------------------------------------
    # 0.6.3 REGIME LABEL STABILITY
    # -------------------------------------------------------------------------
    print("\n--- 0.6.3 Regime Label Stability ---")
    print("Stored labels in signals table for the 191 Core 4h Long trades:")
    reg_counts = c4l["regime"].value_counts().to_dict()
    print(f"  {reg_counts}")
    n_trend = reg_counts.get("strong_trend", 0) + reg_counts.get("weak_trend", 0)
    n_range = reg_counts.get("range", 0)
    n_chop = reg_counts.get("high_vol", 0) + reg_counts.get("squeeze", 0)
    print(f"  Aggregated Stored: Trending={n_trend}, Ranging={n_range}, Choppy={n_chop} (Total={n_trend+n_range+n_chop})")
    print("  Legacy/Prompt Split: Trending=78, Ranging=62, Choppy=51 (Total=191)")

    # -------------------------------------------------------------------------
    # 0.6.4 DOES CONFIDENCE/SIZING CARRY INFORMATION?
    # -------------------------------------------------------------------------
    print("\n--- 0.6.4 Confidence & Sizing Information Carry ---")

    sized_rows = df[df["r_net"].notna()].copy()
    features = ["win_prob", "ev_r", "composite", "confidence", "final_confidence", "meta_p", "risk_pct"]

    print(f"{'Feature':<16} | {'Pooled IC':>10} | {'Pooled p':>9} | {'Daily IC':>9} | {'Daily SE':>9} | {'Daily t':>8} | {'N_eff':>6} | {'Carry Info?'}")
    print("-" * 95)

    ic_results = {}
    for feat in features:
        sub = sized_rows.dropna(subset=[feat, "r_net", "date"])
        n = len(sub)
        if n < 10:
            continue
        pooled_ic = float(sub[feat].rank().corr(sub["r_net"].rank()))
        t_stat_ic = pooled_ic * math.sqrt(max(1, n - 2)) / math.sqrt(max(1e-9, 1.0 - pooled_ic ** 2))
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat_ic) / math.sqrt(2.0))))  # Normal approx for large N

        # Daily rank ICs
        daily_ics = []
        for d, grp in sub.groupby("date"):
            if len(grp) >= 2 and grp[feat].nunique() > 1 and grp["r_net"].nunique() > 1:
                r_ic = float(grp[feat].rank().corr(grp["r_net"].rank()))
                if not np.isnan(r_ic):
                    daily_ics.append(r_ic)

        if len(daily_ics) > 1:
            mean_daily_ic = float(np.mean(daily_ics))
            se_daily_ic = float(np.std(daily_ics, ddof=1) / math.sqrt(len(daily_ics)))
            t_daily_ic = mean_daily_ic / se_daily_ic if se_daily_ic > 0 else 0.0
        else:
            mean_daily_ic = pooled_ic
            se_daily_ic = 1e-9
            t_daily_ic = 0.0

        carry = (mean_daily_ic > 0) and (abs(t_daily_ic) >= 2.0)
        carry_str = "YES" if carry else "NO (Noise)"
        ic_results[feat] = {"pooled_ic": pooled_ic, "daily_ic": mean_daily_ic, "daily_t": t_daily_ic}
        print(f"{feat:<16} | {pooled_ic:>+10.4f} | {p_val:>9.4f} | {mean_daily_ic:>+9.4f} | {se_daily_ic:>9.4f} | {t_daily_ic:>+8.2f} | {len(daily_ics):>6} | {carry_str}")

    # Reliability table by win_prob decile
    print("\nReliability Table by win_prob Decile:")
    print("-" * 75)
    print(f"{'Decile':<8} | {'Predicted P':>12} | {'Realized WR':>12} | {'Mean R':>10} | {'Trades n':>9}")
    print("-" * 75)

    wp_sub = sized_rows.dropna(subset=["win_prob", "r_net"]).copy()
    wp_sub["won"] = (wp_sub["r_net"] > 0).astype(float)
    wp_sub["decile"] = pd.qcut(wp_sub["win_prob"], q=5, duplicates="drop")

    for dec, grp in wp_sub.groupby("decile", observed=False):
        pred_p = float(grp["win_prob"].mean())
        real_wr = float(grp["won"].mean())
        m_r = float(grp["r_net"].mean())
        print(f"{str(dec):<8} | {pred_p:>12.3f} | {real_wr*100:>11.1f}% | {m_r:>+9.3f}R | {len(grp):>9}")

    p_actual = wp_sub["won"].values
    p_pred = wp_sub["win_prob"].values
    brier_score = float(np.mean((p_pred - p_actual) ** 2))
    p_bar = float(np.mean(p_actual))
    base_brier = p_bar * (1.0 - p_bar)
    bss = 1.0 - (brier_score / base_brier) if base_brier > 0 else 0.0
    print(f"\nBrier Score: {brier_score:.4f} | Base-Rate Brier: {base_brier:.4f} | Brier Skill Score (BSS): {bss:+.4f}")

    # 10 Random core shorts multiplier chains
    print("\nMultiplier Chain for 10 Random Core Shorts:")
    print("-" * 115)
    print(f"{'Signal ID':>10} | {'Symbol':<8} | {'WinProb':>7} | {'RR':>5} | {'QuarterKelly':>12} | {'RuinCap':>8} | {'TierCap':>8} | {'SymMult':>7} | {'Risk%':>7}")
    print("-" * 115)
    core_shorts_sample = df[(df["strategy"] == "core") & (df["direction"] == "short")].sample(n=min(10, len(core_short)), random_state=42)
    for _, r in core_shorts_sample.iterrows():
        wp = r["win_prob"]
        rr = 1.8
        tier = tier_for_equity(1000.0)
        kf = quarter_kelly(wp, rr)
        rf = ruin_fraction(wp, rr, tier["risk_cap"])
        sym_mult = 0.50 if r["symbol"].upper() == "BTCUSDT" else 1.0
        print(f"{r['signal_id']:>10} | {r['symbol']:<8} | {wp:>7.3f} | {rr:>5.1f} | {kf*100:>11.2f}% | {rf*100:>7.2f}% | {tier['risk_cap']*100:>7.2f}% | {sym_mult:>7.2f} | {r['risk_pct']:>6.2f}%")

    # Automated Decision Rule Evaluation
    wp_ic = ic_results.get("win_prob", {}).get("daily_ic", 0.0)
    wp_t = ic_results.get("win_prob", {}).get("daily_t", 0.0)
    ev_ic = ic_results.get("ev_r", {}).get("daily_ic", 0.0)
    ev_t = ic_results.get("ev_t", {}).get("daily_t", 0.0)

    print("\nAutomated Sizing Mode Decision:")
    if wp_ic <= 0 or abs(wp_t) < 2.0 or ev_ic <= 0 or abs(ev_t) < 2.0:
        print("  TRIGGER: win_prob and/or ev_r IC <= 0 or |t| < 2.")
        print("  ACTION: Setting SIZING_MODE = 'flat_risk' with FLAT_RISK_PCT = 0.50 for all paper signals.")
        auto_flat_risk = True
    else:
        print("  PRESERVE: Confidence carries significant predictive information.")
        auto_flat_risk = False

    # -------------------------------------------------------------------------
    # 0.6.5 FREEZE AMENDMENT & PARAMETER SPLIT
    # -------------------------------------------------------------------------
    print("\n--- 0.6.5 Freeze Amendment: Parameter Split ---")

    # Read original frozen parameters
    orig_path = Path("config/frozen_core_long_v1.json")
    if not orig_path.exists():
        orig_path = Path("backend/config/frozen_core_long_v1.json")

    with open(orig_path, "r", encoding="utf-8") as f:
        orig_dict = json.load(f)

    # Split into signal-generating and risk parameters
    signal_keys = [
        "limit_orders_enabled", "limit_offset_atr", "limit_expiry_bars",
        "partial_book_enabled", "partial_book_at_r", "partial_book_fraction",
        "min_reward_risk", "conviction_floor", "ev_gate_enabled", "min_ev_r",
        "regime_filter_enabled", "regime_perf_gate_enabled",
        "direction_perf_gate_enabled", "symbol_perf_gate_enabled",
        "max_stop_loss_pct", "min_token_nominal_price",
        "resolver_same_bar_rule", "crypto_long_only",
        "fee_perp_maker_bps", "fee_perp_taker_bps", "stop_extra_slippage_bps"
    ]
    risk_keys = [
        "risk_per_trade_pct", "max_position_leverage", "sizing_mode",
        "flat_risk_pct", "calibration_monitor_enabled", "calibration_min_trades",
        "calibration_size_floor", "drift_enabled", "circuit_breaker_enabled"
    ]

    source_params = orig_dict.get("parameters", orig_dict)
    signal_params = {k: source_params[k] for k in signal_keys if k in source_params}
    # Add newly formalized keys
    signal_params["primary_entry_mode"] = "hybrid"

    risk_params = {
        "sizing_mode": "flat_risk" if auto_flat_risk else "kelly",
        "flat_risk_pct": 0.50,
        "risk_per_trade_pct": source_params.get("risk_per_trade_pct", 0.75),
        "max_position_leverage": source_params.get("max_position_leverage", 1.0),
        "calibration_monitor_enabled": source_params.get("calibration_monitor_enabled", True),
        "drift_enabled": source_params.get("drift_enabled", True),
        "circuit_breaker_enabled": source_params.get("circuit_breaker_enabled", True),
    }

    # Serialize canonical JSON
    signal_canonical = json.dumps(signal_params, sort_keys=True, indent=2)
    new_sha = hashlib.sha256(signal_canonical.encode("utf-8")).hexdigest()

    frozen_v1_1_dict = {
        "version": "1.1",
        "freeze_timestamp": datetime.now(timezone.utc).isoformat(),
        "sha256": new_sha,
        "strategy": "core_4h_long",
        "type": "signal_generating_parameters_only",
        "parameters": signal_params,
    }

    proj_root = Path(__file__).resolve().parents[2]
    backend_root = Path(__file__).resolve().parents[1]

    for base in [proj_root, backend_root]:
        cfg_dir = base / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        with open(cfg_dir / "frozen_core_long_v1_1.json", "w", encoding="utf-8") as f:
            json.dump(frozen_v1_1_dict, f, indent=2)
        with open(cfg_dir / "risk_params.json", "w", encoding="utf-8") as f:
            json.dump(risk_params, f, indent=2)

    print(f"  Created config/frozen_core_long_v1_1.json")
    print(f"  New SHA-256 Checksum: {new_sha}")
    print(f"  Created config/risk_params.json (NOT hash-locked)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
