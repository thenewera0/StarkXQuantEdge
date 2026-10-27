"""Compute benchmarks with IDENTICAL exits (partial booking, stops, targets, timeout) matched on (symbol, entry_timestamp)."""

import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import load_dotenv

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app.indicators.engine import compute_indicators
from app.research.dataset import compute_btc_regimes
from app.research.labels import simulate_hybrid_entry_barrier
from app.signal_service import detect_regime, score_row


def load_all_cached_4h_data() -> dict[str, pd.DataFrame]:
    cache_dir = Path("backend/data_cache")
    if not cache_dir.exists():
        cache_dir = Path("data_cache")
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


def run_benchmark_audit():
    print("Loading 4h cached data...", flush=True)
    data_4h = load_all_cached_4h_data()
    btc_4h = data_4h["BTCUSDT"]
    btc_regimes = compute_btc_regimes(btc_4h)

    # Pre-compute indicators
    print("Pre-computing indicators...", flush=True)
    indicators_cache = {}
    for sym, df_raw in data_4h.items():
        indicators_cache[sym] = compute_indicators(df_raw)

    rule_trades = []
    rng = np.random.default_rng(42)
    allowed_regimes = {"strong_trend", "weak_trend", "range", "high_vol"}

    print("Simulating matching trades...", flush=True)
    for sym, df_raw in data_4h.items():
        ind_df = indicators_cache[sym]
        n_bars = len(ind_df)
        btc_sub = btc_regimes.reindex(ind_df.index, method="ffill")

        for i in range(50, n_bars - 48, 2):
            bar = ind_df.iloc[i]
            bar_dt = ind_df.index[i]
            px = float(bar["close"])
            if px < 0.01:
                continue
            reg = detect_regime(bar)
            if reg not in allowed_regimes:
                continue

            res = score_row(bar, interval="4h", regime=reg)
            is_rule_entry = (res.composite >= 0.50 and res.label in ("Buy", "Strong Buy"))

            if is_rule_entry:
                btc_reg = btc_sub.iloc[i].get("btc_regime", "bull")
                date_str = str(bar_dt)[:10]

                # 1. Rule trade: hybrid entry, partial booking at 0.20R taking 50%, target 2.0R, stop 1.25R, timeout 48
                r_trade = simulate_hybrid_entry_barrier(
                    df_raw, i, direction="long", k_up=2.0, k_dn=1.25, symbol=sym,
                    partial_book_r=0.20, partial_book_frac=0.50
                )

                # 2. Always-Long with IDENTICAL exits (partial booking 0.20R taking 50%, target 2.0R, stop 1.25R, timeout 48)
                al_m = simulate_hybrid_entry_barrier(
                    df_raw, i, direction="long", k_up=2.0, k_dn=1.25, symbol=sym,
                    partial_book_r=0.20, partial_book_frac=0.50
                )

                # 3. Always-Long UNMANAGED (partial_book_r=999, partial_book_frac=0.0)
                al_u = simulate_hybrid_entry_barrier(
                    df_raw, i, direction="long", k_up=2.0, k_dn=1.25, symbol=sym,
                    partial_book_r=999.0, partial_book_frac=0.0
                )

                # 4. Random-Entry with IDENTICAL exits (50% long, 50% short)
                rand_dir = "long" if rng.random() > 0.5 else "short"
                rand_trade = simulate_hybrid_entry_barrier(
                    df_raw, i, direction=rand_dir, k_up=2.0, k_dn=1.25, symbol=sym,
                    partial_book_r=0.20, partial_book_frac=0.50
                )

                if r_trade is not None and al_m is not None and al_u is not None and rand_trade is not None:
                    rule_trades.append({
                        "date": date_str,
                        "symbol": sym,
                        "idx": i,
                        "btc_regime": btc_reg,
                        "rule_r": r_trade["r_net"],
                        "al_managed_r": al_m["r_net"],
                        "al_unmanaged_r": al_u["r_net"],
                        "random_r": rand_trade["r_net"],
                    })

    df_active = pd.DataFrame(rule_trades)
    print(f"Total matched active trades: {len(df_active)}", flush=True)

    summary_records = []
    for label, subset in [
        ("Overall (All Markets)", df_active),
        ("BTC Bull (Price > 200d MA)", df_active[df_active["btc_regime"] == "bull"]),
        ("BTC Bear (Price <= 200d MA)", df_active[df_active["btc_regime"] == "bear"]),
    ]:
        print(f"\n==========================================", flush=True)
        print(f"{label} (n={len(subset)})", flush=True)
        print(f"==========================================", flush=True)

        dates = subset["date"].values
        unique_dates = np.unique(dates)
        date_map = {d: i for i, d in enumerate(unique_dates)}
        c_indices = np.array([date_map[d] for d in dates])

        def to_clusters(arr):
            cls = []
            for c_i in range(len(unique_dates)):
                vals = arr[c_indices == c_i]
                if len(vals) > 0:
                    cls.append(vals)
            return cls

        boot_rule = cluster_bootstrap_mean_unbiased(to_clusters(subset["rule_r"].values))
        boot_al_m = cluster_bootstrap_mean_unbiased(to_clusters(subset["al_managed_r"].values))
        boot_al_u = cluster_bootstrap_mean_unbiased(to_clusters(subset["al_unmanaged_r"].values))
        boot_rand = cluster_bootstrap_mean_unbiased(to_clusters(subset["random_r"].values))

        diff_m = subset["rule_r"].values - subset["al_managed_r"].values
        diff_u = subset["rule_r"].values - subset["al_unmanaged_r"].values
        diff_rand = subset["rule_r"].values - subset["random_r"].values

        boot_diff_m = cluster_bootstrap_mean_unbiased(to_clusters(diff_m))
        boot_diff_u = cluster_bootstrap_mean_unbiased(to_clusters(diff_u))
        boot_diff_rand = cluster_bootstrap_mean_unbiased(to_clusters(diff_rand))

        print(f"  Rule Mean R:                {boot_rule['sample_mean']:+.4f} R [{boot_rule['ci_low']:+.4f}, {boot_rule['ci_high']:+.4f}]")
        print(f"  Always-Long (Identical):    {boot_al_m['sample_mean']:+.4f} R [{boot_al_m['ci_low']:+.4f}, {boot_al_m['ci_high']:+.4f}]")
        print(f"  Always-Long (Unmanaged):    {boot_al_u['sample_mean']:+.4f} R [{boot_al_u['ci_low']:+.4f}, {boot_al_u['ci_high']:+.4f}]")
        print(f"  Random-Entry (Identical):   {boot_rand['sample_mean']:+.4f} R [{boot_rand['ci_low']:+.4f}, {boot_rand['ci_high']:+.4f}]")
        print(f"  Paired Excess vs AL (Ident):{boot_diff_m['sample_mean']:+.4f} R [{boot_diff_m['ci_low']:+.4f}, {boot_diff_m['ci_high']:+.4f}] (t={boot_diff_m['t_boot']:+.2f})")
        print(f"  Paired Excess vs AL (Unmgd):{boot_diff_u['sample_mean']:+.4f} R [{boot_diff_u['ci_low']:+.4f}, {boot_diff_u['ci_high']:+.4f}] (t={boot_diff_u['t_boot']:+.2f})")
        print(f"  Paired Excess vs Random:    {boot_diff_rand['sample_mean']:+.4f} R [{boot_diff_rand['ci_low']:+.4f}, {boot_diff_rand['ci_high']:+.4f}] (t={boot_diff_rand['t_boot']:+.2f})")

        summary_records.append({
            "regime": label,
            "n": len(subset),
            "rule_mean_r": boot_rule['sample_mean'],
            "excess_al_m": boot_diff_m['sample_mean'],
            "ci_al_m": [boot_diff_m['ci_low'], boot_diff_m['ci_high']],
            "excess_al_u": boot_diff_u['sample_mean'],
            "ci_al_u": [boot_diff_u['ci_low'], boot_diff_u['ci_high']],
            "excess_rand": boot_diff_rand['sample_mean'],
            "ci_rand": [boot_diff_rand['ci_low'], boot_diff_rand['ci_high']],
        })

    return summary_records


if __name__ == "__main__":
    run_benchmark_audit()
