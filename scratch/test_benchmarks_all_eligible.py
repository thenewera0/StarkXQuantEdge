"""5.2 Benchmark Design: Always-Long and Random-Entry built from ALL eligible bars."""

import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[1]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app.indicators.engine import compute_indicators
from app.research.dataset import compute_btc_regimes
from app.research.labels import simulate_hybrid_entry_barrier
from app.signal_service import detect_regime, score_row


def load_all_cached_4h_data() -> dict[str, pd.DataFrame]:
    cache_dir = backend_dir / "data_cache"
    if not cache_dir.exists():
        cache_dir = root_dir / "data_cache"
    data = {}
    for f in sorted(cache_dir.glob("*_4h.parquet")):
        sym = f.name.replace("_4h.parquet", "")
        try:
            df = pd.read_parquet(f)
            if len(df) >= 100:
                data[sym] = df
        except Exception:
            pass
    return data


def cluster_bootstrap_mean_unbiased(
    clusters: list[np.ndarray],
    n_boot: int = 10000,
    seed: int = 42,
) -> dict:
    k = len(clusters)
    if k == 0:
        return {"n": 0, "sample_mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "se_boot": 0.0, "t_boot": 0.0}
    cluster_sums = np.array([float(np.sum(c)) for c in clusters])
    cluster_sizes = np.array([len(c) for c in clusters])
    n_total = float(np.sum(cluster_sizes))
    sample_mean = float(np.sum(cluster_sums)) / n_total if n_total > 0 else 0.0

    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(k, size=k, replace=True)
        boot_means[b] = np.sum(cluster_sums[idx]) / n_total

    se_boot = float(np.std(boot_means, ddof=1))
    return {
        "n": int(n_total),
        "k_clusters": k,
        "sample_mean": sample_mean,
        "ci_low": float(np.percentile(boot_means, 2.5)),
        "ci_high": float(np.percentile(boot_means, 97.5)),
        "se_boot": se_boot,
        "t_boot": sample_mean / se_boot if se_boot > 1e-9 else 0.0,
    }


def run_benchmarks_all_eligible():
    print("Loading 4h cached data...", flush=True)
    data_4h = load_all_cached_4h_data()
    btc_4h = data_4h["BTCUSDT"]
    btc_regimes = compute_btc_regimes(btc_4h)

    print("Pre-computing indicators...", flush=True)
    indicators_cache = {}
    for sym, df_raw in data_4h.items():
        indicators_cache[sym] = compute_indicators(df_raw)

    rule_trades = []
    baseline_al_trades = []
    baseline_rand_trades = []
    rng = np.random.default_rng(42)
    allowed_regimes = {"strong_trend", "weak_trend", "range", "high_vol"}

    print("Simulating trades across universe...", flush=True)
    step = 2  # Evaluate every 2 bars (8 hours) for independent trade sampling

    for sym, df_raw in data_4h.items():
        ind_df = indicators_cache[sym]
        n_bars = len(ind_df)
        btc_sub = btc_regimes.reindex(ind_df.index, method="ffill")

        for i in range(50, n_bars - 48, step):
            bar = ind_df.iloc[i]
            bar_dt = ind_df.index[i]
            px = float(bar["close"])
            if px < 0.01:
                continue
            reg = detect_regime(bar)
            if reg not in allowed_regimes:
                continue

            btc_reg = btc_sub.iloc[i].get("btc_regime", "bull")
            date_str = str(bar_dt)[:10]

            # 1. Check if Rule fires
            res = score_row(bar, interval="4h", regime=reg)
            is_rule_entry = (res.composite >= 0.50 and res.label in ("Buy", "Strong Buy"))

            # 2. Always-Long on this eligible bar (Identical exits)
            al_trade = simulate_hybrid_entry_barrier(
                df_raw, i, direction="long", k_up=2.0, k_dn=1.25, symbol=sym,
                partial_book_r=0.20, partial_book_frac=0.50
            )

            # 3. Random-Entry on this eligible bar (Identical exits)
            rand_dir = "long" if rng.random() > 0.5 else "short"
            rand_trade = simulate_hybrid_entry_barrier(
                df_raw, i, direction=rand_dir, k_up=2.0, k_dn=1.25, symbol=sym,
                partial_book_r=0.20, partial_book_frac=0.50
            )

            if al_trade is not None:
                baseline_al_trades.append({
                    "date": date_str, "symbol": sym, "idx": i,
                    "btc_regime": btc_reg, "al_r": al_trade["r_net"]
                })

            if rand_trade is not None:
                baseline_rand_trades.append({
                    "date": date_str, "symbol": sym, "idx": i,
                    "btc_regime": btc_reg, "rand_r": rand_trade["r_net"]
                })

            if is_rule_entry and al_trade is not None:
                rule_trades.append({
                    "date": date_str, "symbol": sym, "idx": i,
                    "btc_regime": btc_reg, "rule_r": al_trade["r_net"]
                })

    df_rule = pd.DataFrame(rule_trades)
    df_al = pd.DataFrame(baseline_al_trades)
    df_rand = pd.DataFrame(baseline_rand_trades)

    n_rule = len(df_rule)
    n_al = len(df_al)
    n_rand = len(df_rand)

    print(f"\nRule Trades Count (n_rule):          {n_rule}")
    print(f"Always-Long Baseline Count (n_al):     {n_al}")
    print(f"Random Baseline Count (n_rand):        {n_rand}")

    # Section 5.2 Mandatory Invariant Assertions
    assert n_al > n_rule, f"Assertion failed: n_baseline ({n_al}) must be strictly > n_rule ({n_rule})"
    assert n_rand > n_rule, f"Assertion failed: n_rand ({n_rand}) must be strictly > n_rule ({n_rule})"
    assert df_al["al_r"].values.shape != df_rule["rule_r"].values.shape, "Assertion failed: Baseline series equals rule series!"

    # Aggregate by day for daily paired excess calculation
    # For each day: Rule daily mean vs Baseline daily mean
    days = sorted(list(set(df_rule["date"]).union(set(df_al["date"]))))
    
    rule_by_day = df_rule.groupby("date")["rule_r"].mean().to_dict()
    al_by_day = df_al.groupby("date")["al_r"].mean().to_dict()
    rand_by_day = df_rand.groupby("date")["rand_r"].mean().to_dict()

    # Get daily BTC regime
    day_regime = df_al.groupby("date")["btc_regime"].first().to_dict()

    paired_records = []
    for d in days:
        if d in rule_by_day and d in al_by_day:
            r_val = rule_by_day[d]
            al_val = al_by_day[d]
            rand_val = rand_by_day.get(d, 0.0)
            paired_records.append({
                "date": d,
                "regime": day_regime.get(d, "bull"),
                "rule_r": r_val,
                "al_r": al_val,
                "rand_r": rand_val,
                "excess_al": r_val - al_val,
                "excess_rand": r_val - rand_val
            })

    df_paired = pd.DataFrame(paired_records)
    print(f"Total Paired Calendar Days: {len(df_paired)}")

    # Evaluate Overall, Bull, Bear
    regimes = [
        ("Overall (All Markets)", df_paired),
        ("BTC Bull (Price > 200d MA)", df_paired[df_paired["regime"] == "bull"]),
        ("BTC Bear (Price <= 200d MA)", df_paired[df_paired["regime"] == "bear"]),
    ]

    results = []
    for r_name, sub in regimes:
        # Group into 7-day clusters for cluster bootstrap
        sub = sub.copy().sort_values("date")
        sub["cluster"] = (pd.to_datetime(sub["date"]) - pd.to_datetime(sub["date"].iloc[0])).dt.days // 7
        
        clusters_excess_al = [c["excess_al"].values for _, c in sub.groupby("cluster")]
        clusters_excess_rand = [c["excess_rand"].values for _, c in sub.groupby("cluster")]
        clusters_rule = [c["rule_r"].values for _, c in sub.groupby("cluster")]
        clusters_al = [c["al_r"].values for _, c in sub.groupby("cluster")]

        boot_excess_al = cluster_bootstrap_mean_unbiased(clusters_excess_al, n_boot=10000, seed=42)
        boot_excess_rand = cluster_bootstrap_mean_unbiased(clusters_excess_rand, n_boot=10000, seed=42)
        boot_rule = cluster_bootstrap_mean_unbiased(clusters_rule, n_boot=10000, seed=42)
        boot_al = cluster_bootstrap_mean_unbiased(clusters_al, n_boot=10000, seed=42)

        print(f"\n==========================================")
        print(f"{r_name} (Days = {len(sub)})")
        print(f"==========================================")
        print(f"  Rule Daily Mean R:         {boot_rule['sample_mean']:+.4f} R [{boot_rule['ci_low']:+.4f}, {boot_rule['ci_high']:+.4f}]")
        print(f"  Always-Long Universe Mean: {boot_al['sample_mean']:+.4f} R [{boot_al['ci_low']:+.4f}, {boot_al['ci_high']:+.4f}]")
        print(f"  Paired Excess vs AL:       {boot_excess_al['sample_mean']:+.4f} R [{boot_excess_al['ci_low']:+.4f}, {boot_excess_al['ci_high']:+.4f}] (t={boot_excess_al['t_boot']:+.2f})")
        print(f"  Paired Excess vs Random:   {boot_excess_rand['sample_mean']:+.4f} R [{boot_excess_rand['ci_low']:+.4f}, {boot_excess_rand['ci_high']:+.4f}] (t={boot_excess_rand['t_boot']:+.2f})")

        verdict = "RULE ADDS INFORMATION" if (boot_excess_al["ci_low"] > 0 and boot_excess_rand["ci_low"] > 0) else (
            "REGIME-DEPENDENT" if (boot_excess_al["ci_low"] > 0 or boot_excess_rand["ci_low"] > 0) else "BETA ONLY"
        )
        print(f"  Pre-Registered Verdict:    {verdict}")

        results.append({
            "regime": r_name,
            "days": len(sub),
            "rule_mean": boot_rule["sample_mean"],
            "al_mean": boot_al["sample_mean"],
            "excess_al": boot_excess_al["sample_mean"],
            "ci_low_al": boot_excess_al["ci_low"],
            "ci_high_al": boot_excess_al["ci_high"],
            "excess_rand": boot_excess_rand["sample_mean"],
            "ci_low_rand": boot_excess_rand["ci_low"],
            "ci_high_rand": boot_excess_rand["ci_high"],
            "verdict": verdict
        })

    return results


if __name__ == "__main__":
    run_benchmarks_all_eligible()
