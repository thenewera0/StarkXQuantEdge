"""Item 4.1(e): Validate daily momentum with 7d, 14d, 30d, 60d lookbacks on point-in-time universe."""

import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import load_dotenv

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app.research.validation import deflated_sharpe_ratio


def day_block_bootstrap_sharpe(
    daily_returns: np.ndarray,
    n_boot: int = 10000,
    seed: int = 42,
    periods_per_year: float = 365.0,
) -> tuple[float, float, float, tuple[float, float]]:
    n = len(daily_returns)
    if n < 10:
        return 0.0, 0.0, 0.0, (0.0, 0.0)

    mean_r = float(np.mean(daily_returns))
    std_r = float(np.std(daily_returns, ddof=1)) if n > 1 else 1e-9
    sharpe_ann = (mean_r / std_r) * math.sqrt(periods_per_year) if std_r > 1e-9 else 0.0

    block_size = max(5, int(math.ceil(math.pow(n, 1.0 / 3.0))))
    n_blocks = int(math.ceil(n / block_size))

    rng = np.random.default_rng(seed)
    boot_sharpes = np.empty(n_boot)

    for b in range(n_boot):
        start_indices = rng.integers(0, max(1, n - block_size + 1), size=n_blocks)
        indices = np.concatenate([np.arange(idx, idx + block_size) for idx in start_indices])[:n]
        sample = daily_returns[indices]
        s_mean = np.mean(sample)
        s_std = np.std(sample, ddof=1)
        boot_sharpes[b] = (s_mean / s_std) * math.sqrt(periods_per_year) if s_std > 1e-9 else 0.0

    boot_mean_sr = float(np.mean(boot_sharpes))
    se_sr = float(np.std(boot_sharpes, ddof=1))
    ci_low = float(np.percentile(boot_sharpes, 2.5))
    ci_high = float(np.percentile(boot_sharpes, 97.5))

    return sharpe_ann, se_sr, boot_mean_sr, (ci_low, ci_high)


def run_2d_validation():
    # Load 4h parquets and aggregate to 1d bars
    cache_dir = Path("backend/data_cache")
    if not cache_dir.exists():
        cache_dir = Path("data_cache")

    daily_dict = {}
    vol_dict = {}

    for f in sorted(cache_dir.glob("*_4h.parquet")):
        sym = f.name.replace("_4h.parquet", "")
        df = pd.read_parquet(f)
        if len(df) < 100:
            continue
        # Resample to 1d
        df_1d = df.resample("1D").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()
        if len(df_1d) >= 180:
            daily_dict[sym] = df_1d["close"]
            vol_dict[sym] = df_1d["close"] * df_1d["volume"]

    px_df = pd.DataFrame(daily_dict).dropna(how="all")
    vol_df = pd.DataFrame(vol_dict).reindex(px_df.index)

    print(f"Total symbols resampled to daily: {len(px_df.columns)}")
    print(f"Date range: {px_df.index.min()} to {px_df.index.max()} ({len(px_df)} days)")

    # Trailing 30d USD volume point-in-time
    trailing_vol_30d = vol_df.rolling(30).mean()

    # Lookbacks: 7d, 14d, 30d, 60d momentum (skipping day t-1 to avoid microstructure bounce)
    lookbacks = [7, 14, 30, 60]
    mom_signals = {}
    for L in lookbacks:
        mom_signals[L] = px_df.shift(1) / px_df.shift(L + 1) - 1.0

    # Forward 1d return: strictly forward aligned t -> t+1
    fwd_1d_ret = px_df.pct_change(1).shift(-1)

    # Point-in-time universe ranking at each date:
    # Require >= 90 days of history at date t
    # Discovery = ranks 1-25 (out of our available symbols), Validation = ranks 26-50
    # Or top half vs bottom half
    results_2d = {}

    for L in lookbacks:
        sig = mom_signals[L]
        returns_disc = []
        returns_val = []
        dates_list = []

        for i in range(90, len(px_df) - 1):
            dt = px_df.index[i]
            # Point in time active symbols with >= 90 days of history
            v_row = trailing_vol_30d.iloc[i].dropna()
            # Rank symbols by trailing 30d volume
            v_ranked = v_row.sort_values(ascending=False)
            
            # Discovery: top 25; Validation: ranks 26-50
            disc_syms = v_ranked.index[:25]
            val_syms = v_ranked.index[25:]

            sig_row = sig.iloc[i]
            ret_fwd = fwd_1d_ret.iloc[i]

            # Discovery momentum (Long top quintile, short bottom quintile)
            s_disc = sig_row.reindex(disc_syms).dropna()
            if len(s_disc) >= 10:
                long_s = s_disc[s_disc >= s_disc.quantile(0.80)].index
                short_s = s_disc[s_disc <= s_disc.quantile(0.20)].index
                r_gross = float(ret_fwd[long_s].mean() - ret_fwd[short_s].mean())
                # Deduct 8 bps round trip turnover (4 bps taker/maker + slip)
                r_net = r_gross - 0.0008
                returns_disc.append(r_net)

            # Validation momentum
            s_val = sig_row.reindex(val_syms).dropna()
            if len(s_val) >= 10:
                long_s = s_val[s_val >= s_val.quantile(0.80)].index
                short_s = s_val[s_val <= s_val.quantile(0.20)].index
                r_gross = float(ret_fwd[long_s].mean() - ret_fwd[short_s].mean())
                r_net = r_gross - 0.0008
                returns_val.append(r_net)
                dates_list.append(dt)

        arr_val = np.array(returns_val)
        sr, se_sr, _, ci = day_block_bootstrap_sharpe(arr_val, n_boot=10000, seed=42)
        
        # Trial count: honest trial count = 502 + configs
        dsr = deflated_sharpe_ratio(
            sr_observed=sr,
            n_trials=510,
            t_bars=len(arr_val),
            skewness=float(pd.Series(arr_val).skew()),
            kurtosis=float(pd.Series(arr_val).kurtosis()),
        )

        df_p = pd.DataFrame({"dt": dates_list, "net": arr_val})
        df_p["year"] = pd.to_datetime(df_p["dt"]).dt.year
        yr_pos = sum(df_p.groupby("year")["net"].mean() > 0)
        tot_yr = df_p["year"].nunique()

        results_2d[L] = {
            "lookback": f"{L}d",
            "mean_bps": float(np.mean(arr_val) * 10000),
            "std_bps": float(np.std(arr_val, ddof=1) * 10000),
            "sharpe": sr,
            "ci_low": ci[0],
            "ci_high": ci[1],
            "dsr": dsr,
            "years_pos": f"{yr_pos}/{tot_yr}",
            "n_obs": len(arr_val),
        }

    print("\n" + "="*90)
    print("ITEM 4.1(e): DAILY MOMENTUM ON POINT-IN-TIME VALIDATION UNIVERSE")
    print("="*90)
    print(f"{'Lookback':<10} | {'Mean (bps/day)':>16} | {'Annualized Net Sharpe':>22} | {'95% Day-Block CI':>22} | {'DSR':>8} | {'Pos Years':>10}")
    print("-" * 95)
    for L, r in results_2d.items():
        print(f"{r['lookback']:<10} | {r['mean_bps']:>+15.2f}p | {r['sharpe']:>+21.2f} | [{r['ci_low']:>+8.2f}, {r['ci_high']:>+8.2f}] | {r['dsr']:>7.4f} | {r['years_pos']:>10}")

    best_L = max(results_2d.keys(), key=lambda k: results_2d[k]["sharpe"])
    print(f"\nBest-performing member: {best_L}d momentum with Net Sharpe {results_2d[best_L]['sharpe']:+.2f}")


if __name__ == "__main__":
    run_2d_validation()
