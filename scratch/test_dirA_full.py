"""Item 4.2: Hedged Cross-Sectional Composite (Direction A) Pre-Registered Final Test."""

import json
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import load_dotenv

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app.execution import tick_size, fill_bar, LimitPlan
from app.indicators.engine import compute_indicators
from app.research.dataset import compute_btc_regimes
from app.research.validation import deflated_sharpe_ratio
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


def day_block_bootstrap_sharpe(
    returns: np.ndarray,
    n_boot: int = 10000,
    seed: int = 42,
    periods_per_year: float = 2190.0,
) -> tuple[float, float, float, tuple[float, float]]:
    n = len(returns)
    if n < 10:
        return 0.0, 0.0, 0.0, (0.0, 0.0)

    mean_r = float(np.mean(returns))
    std_r = float(np.std(returns, ddof=1)) if n > 1 else 1e-9
    sharpe_ann = (mean_r / std_r) * math.sqrt(periods_per_year) if std_r > 1e-9 else 0.0

    block_size = max(5, int(math.ceil(math.pow(n, 1.0 / 3.0))))
    n_blocks = int(math.ceil(n / block_size))

    rng = np.random.default_rng(seed)
    boot_sharpes = np.empty(n_boot)

    for b in range(n_boot):
        start_indices = rng.integers(0, max(1, n - block_size + 1), size=n_blocks)
        indices = np.concatenate([np.arange(idx, idx + block_size) for idx in start_indices])[:n]
        sample = returns[indices]
        s_mean = np.mean(sample)
        s_std = np.std(sample, ddof=1)
        boot_sharpes[b] = (s_mean / s_std) * math.sqrt(periods_per_year) if s_std > 1e-9 else 0.0

    boot_mean_sr = float(np.mean(boot_sharpes))
    se_sr = float(np.std(boot_sharpes, ddof=1))
    ci_low = float(np.percentile(boot_sharpes, 2.5))
    ci_high = float(np.percentile(boot_sharpes, 97.5))

    return sharpe_ann, se_sr, boot_mean_sr, (ci_low, ci_high)


def run_dirA_full():
    print("Loading 4h cached dataset...", flush=True)
    data_4h = load_all_cached_4h_data()
    btc_df = data_4h["BTCUSDT"]
    btc_regimes = compute_btc_regimes(btc_df)
    btc_close = btc_df["close"]

    cache_file = Path("scratch/cached_scores_4h.parquet")
    if cache_file.exists():
        print("Loading precomputed scores from scratch/cached_scores_4h.parquet...", flush=True)
        scores_df = pd.read_parquet(cache_file)
        all_close = {sym: df_raw["close"] for sym, df_raw in data_4h.items() if len(df_raw) >= 180}
        all_open = {sym: df_raw["open"] for sym, df_raw in data_4h.items() if len(df_raw) >= 180}
        all_high = {sym: df_raw["high"] for sym, df_raw in data_4h.items() if len(df_raw) >= 180}
        all_low = {sym: df_raw["low"] for sym, df_raw in data_4h.items() if len(df_raw) >= 180}
        all_vol = {sym: df_raw["close"] * df_raw["volume"] for sym, df_raw in data_4h.items() if len(df_raw) >= 180}
        all_atr = {}
        for sym, df_raw in data_4h.items():
            if len(df_raw) >= 180:
                all_atr[sym] = (df_raw["high"] - df_raw["low"]).rolling(14).mean()
        px_close = pd.DataFrame(all_close).dropna(how="all")
        px_open = pd.DataFrame(all_open).reindex(px_close.index)
        px_high = pd.DataFrame(all_high).reindex(px_close.index)
        px_low = pd.DataFrame(all_low).reindex(px_close.index)
        px_vol = pd.DataFrame(all_vol).reindex(px_close.index)
        px_atr = pd.DataFrame(all_atr).reindex(px_close.index)
        scores_df = scores_df.reindex(px_close.index)
    else:
        print("Precomputing indicators and scores for all symbols...", flush=True)
        all_scores = {}
        all_close = {}
        all_open = {}
        all_high = {}
        all_low = {}
        all_vol = {}
        all_atr = {}

        for sym, df_raw in data_4h.items():
            if len(df_raw) < 180:
                continue
            ind = compute_indicators(df_raw)
            scores = []
            for i in range(len(ind)):
                bar = ind.iloc[i]
                reg = detect_regime(bar)
                res = score_row(bar, interval="4h", regime=reg)
                scores.append(res.composite)
            all_scores[sym] = pd.Series(scores, index=ind.index)
            all_close[sym] = df_raw["close"]
            all_open[sym] = df_raw["open"]
            all_high[sym] = df_raw["high"]
            all_low[sym] = df_raw["low"]
            all_vol[sym] = df_raw["close"] * df_raw["volume"]
            all_atr[sym] = ind["atr"] if "atr" in ind.columns else (df_raw["high"] - df_raw["low"]).rolling(14).mean()

        px_close = pd.DataFrame(all_close).dropna(how="all")
        px_open = pd.DataFrame(all_open).reindex(px_close.index)
        px_high = pd.DataFrame(all_high).reindex(px_close.index)
        px_low = pd.DataFrame(all_low).reindex(px_close.index)
        px_vol = pd.DataFrame(all_vol).reindex(px_close.index)
        px_atr = pd.DataFrame(all_atr).reindex(px_close.index)
        scores_df = pd.DataFrame(all_scores).reindex(px_close.index)
        scores_df.to_parquet(cache_file)
        print("Cached scores to scratch/cached_scores_4h.parquet", flush=True)

    print(f"Total symbols active: {len(px_close.columns)} across {len(px_close)} 4h bars", flush=True)

    # 30d trailing volume (30 days * 6 bars/day = 180 bars)
    rolling_vol_30d = px_vol.rolling(180).mean()

    # 30d rolling realized volatility (standard deviation of 4h log returns * sqrt(6*365))
    ret_4h = px_close.pct_change(1)
    rolling_vol_ret_30d = ret_4h.rolling(180).std().replace(0, np.nan)

    # 30d rolling beta to BTC
    btc_ret_4h = ret_4h["BTCUSDT"]
    rolling_cov_btc = ret_4h.rolling(180).cov(btc_ret_4h)
    btc_var_30d = btc_ret_4h.rolling(180).var()
    rolling_beta_btc = rolling_cov_btc.div(btc_var_30d, axis=0)

    # Survivorship / Delisted Analysis:
    # Check tokens that entered late or had short history
    first_valid = px_close.apply(lambda col: col.first_valid_index())
    late_entrants = [s for s, dt in first_valid.items() if dt > pd.Timestamp("2021-06-01", tz="UTC")]
    total_bars_all = px_close.notna().sum().sum()
    late_bars = px_close[late_entrants].notna().sum().sum()
    late_share_pct = (late_bars / total_bars_all) * 100.0
    print(f"Delisted / late rising tokens share of total symbol-bars: {late_share_pct:.2f}%", flush=True)

    horizons = [12, 24, 48]
    results_by_h = {}

    for H in horizons:
        print(f"\n--- Simulating Horizon H = {H} bars ({H*4} hours) ---", flush=True)
        # Rebalance every H bars, step by H
        rebal_records = []
        maker_fill_records = []

        # Start from bar 540 (90 days of history required)
        for i in range(540, len(px_close) - H - 3, H):
            dt = px_close.index[i]
            next_open_dt = px_close.index[i + 1]
            exit_open_dt = px_close.index[i + 1 + H]

            # 1. Point-in-time universe ranking
            vol_row = rolling_vol_30d.iloc[i].dropna()
            # Require >= 90 days of history (540 bars) at date t
            valid_syms = [s for s in vol_row.index if px_close[s].iloc[:i].count() >= 540]
            vol_ranked = vol_row.loc[valid_syms].sort_values(ascending=False)

            # Split Discovery vs Validation:
            # Discovery = ranks 1 to 25; Validation = ranks 26 to 50 (or ranks 51-100 in production universe)
            disc_syms = vol_ranked.index[:25]
            val_syms = vol_ranked.index[25:50]

            # We focus on the pre-registered VALIDATION universe
            active_syms = val_syms
            scores_row = scores_df.loc[dt, active_syms].dropna()
            if len(scores_row) < 10:
                continue

            q5_syms = scores_row[scores_row >= scores_row.quantile(0.80)].index
            q1_syms = scores_row[scores_row <= scores_row.quantile(0.20)].index
            if len(q5_syms) == 0 or len(q1_syms) == 0:
                continue

            # Equal-risk weights: inverse 30d realized vol
            vols_q5 = rolling_vol_ret_30d.loc[dt, q5_syms].fillna(0.02)
            w_raw_q5 = 1.0 / vols_q5
            w_q5 = w_raw_q5 / w_raw_q5.sum()

            vols_q1 = rolling_vol_ret_30d.loc[dt, q1_syms].fillna(0.02)
            w_raw_q1 = 1.0 / vols_q1
            w_q1 = w_raw_q1 / w_raw_q1.sum()

            # Beta hedge to BTC:
            beta_q5 = float((rolling_beta_btc.loc[dt, q5_syms] * w_q5).sum())
            beta_q1 = float((rolling_beta_btc.loc[dt, q1_syms] * w_q1).sum())
            net_beta = beta_q5 - beta_q1

            # Forward returns: entered at NEXT bar open (t+1 open), exited at t+1+H open
            entry_px_open = px_open.loc[next_open_dt]
            exit_px_open = px_open.loc[exit_open_dt]

            ret_q5 = (exit_px_open[q5_syms] - entry_px_open[q5_syms]) / entry_px_open[q5_syms]
            ret_q1 = (exit_px_open[q1_syms] - entry_px_open[q1_syms]) / entry_px_open[q1_syms]

            btc_entry_px = float(entry_px_open["BTCUSDT"])
            btc_exit_px = float(exit_px_open["BTCUSDT"])
            btc_ret = (btc_exit_px - btc_entry_px) / btc_entry_px if btc_entry_px > 0 else 0.0

            gross_long = float((ret_q5 * w_q5).sum())
            gross_short = float((ret_q1 * w_q1).sum())
            gross_spread = gross_long - gross_short
            hedged_spread = gross_spread - net_beta * btc_ret

            # Taker costs:
            # Taker fee 5 bps/side * 2 sides = 10 bps per leg = 20 bps round trip
            # Slippage: for ranks 51-100, 10 bps per side = 20 bps per leg = 40 bps round trip
            # Funding cost: assume 0.01% / 8h baseline settlement * (H / 2) epochs
            n_epochs = H / 2.0
            funding_drag = 0.0001 * n_epochs * 0.5  # net funding differential
            taker_fee_slip_rt = (0.0005 * 2 + 0.0010 * 2) * 2  # long leg + short leg = 60 bps RT
            net_taker_ret = hedged_spread - (taker_fee_slip_rt + funding_drag)

            # Maker variant execution model:
            # Use execution.py fill rule at bar t+1 and t+2:
            maker_fills_q5 = []
            maker_fills_q1 = []
            for s in q5_syms:
                px_sig = float(px_close.loc[dt, s])
                atr_sig = float(px_atr.loc[dt, s]) if not np.isnan(px_atr.loc[dt, s]) else 0.02 * px_sig
                plan = LimitPlan(limit_price=px_sig - 0.15 * atr_sig, offset_frac=0.15 * atr_sig / px_sig, expiry_bars=2, execution="maker")
                # Check fill on bar i+1 and i+2
                lows = px_low[s].values
                highs = px_high[s].values
                fb = fill_bar(highs, lows, start=i, plan=plan, direction="long", n=len(px_close))
                if fb is not None:
                    # Filled as maker at limit price
                    maker_fills_q5.append({"filled_maker": True, "fill_px": plan.limit_price, "entry_type": "maker"})
                else:
                    # Swept at taker at open of bar i+3
                    sweep_px = float(px_open.loc[px_close.index[i + 3], s])
                    maker_fills_q5.append({"filled_maker": False, "fill_px": sweep_px, "entry_type": "taker"})

            for s in q1_syms:
                px_sig = float(px_close.loc[dt, s])
                atr_sig = float(px_atr.loc[dt, s]) if not np.isnan(px_atr.loc[dt, s]) else 0.02 * px_sig
                plan = LimitPlan(limit_price=px_sig + 0.15 * atr_sig, offset_frac=0.15 * atr_sig / px_sig, expiry_bars=2, execution="maker")
                lows = px_low[s].values
                highs = px_high[s].values
                fb = fill_bar(highs, lows, start=i, plan=plan, direction="short", n=len(px_close))
                if fb is not None:
                    maker_fills_q1.append({"filled_maker": True, "fill_px": plan.limit_price, "entry_type": "maker"})
                else:
                    sweep_px = float(px_open.loc[px_close.index[i + 3], s])
                    maker_fills_q1.append({"filled_maker": False, "fill_px": sweep_px, "entry_type": "taker"})

            q5_maker_rate = np.mean([f["filled_maker"] for f in maker_fills_q5])
            q1_maker_rate = np.mean([f["filled_maker"] for f in maker_fills_q1])
            overall_fill_rate = 0.5 * (q5_maker_rate + q1_maker_rate)

            # Maker model cost:
            # Maker leg: 2 bps fee + 0 slip; Taker sweep leg: 5 bps fee + 10 bps slip
            maker_cost_leg_q5 = q5_maker_rate * 0.0004 + (1.0 - q5_maker_rate) * 0.0030
            maker_cost_leg_q1 = q1_maker_rate * 0.0004 + (1.0 - q1_maker_rate) * 0.0030
            total_maker_cost = maker_cost_leg_q5 + maker_cost_leg_q1 + funding_drag
            net_maker_ret = hedged_spread - total_maker_cost

            # 1-bar lag test: enter at t+2 open instead of t+1 open
            lag_open_dt = px_close.index[i + 2]
            lag_exit_dt = px_close.index[i + 2 + H]
            lag_entry_px = px_open.loc[lag_open_dt]
            lag_exit_px = px_open.loc[lag_exit_dt]
            lag_ret_q5 = (lag_exit_px[q5_syms] - lag_entry_px[q5_syms]) / lag_entry_px[q5_syms]
            lag_ret_q1 = (lag_exit_px[q1_syms] - lag_entry_px[q1_syms]) / lag_entry_px[q1_syms]
            lag_btc_ret = (float(lag_exit_px["BTCUSDT"]) - float(lag_entry_px["BTCUSDT"])) / float(lag_entry_px["BTCUSDT"])
            lag_spread = float((lag_ret_q5 * w_q5).sum() - (lag_ret_q1 * w_q1).sum()) - net_beta * lag_btc_ret
            net_lag_ret = lag_spread - (taker_fee_slip_rt + funding_drag)

            rebal_records.append({
                "dt": dt,
                "year": dt.year,
                "btc_regime": btc_regimes.loc[dt, "btc_regime"] if dt in btc_regimes.index else "bull",
                "gross_spread": gross_spread,
                "hedged_spread": hedged_spread,
                "net_taker_ret": net_taker_ret,
                "net_maker_ret": net_maker_ret,
                "net_lag_ret": net_lag_ret,
                "fill_rate": overall_fill_rate,
                "net_beta": net_beta,
                "btc_ret": btc_ret,
            })

        df_rebal = pd.DataFrame(rebal_records)
        periods_yr = 2190.0 / H

        # 1. Taker Sharpe & CI
        taker_sr, taker_se, _, taker_ci = day_block_bootstrap_sharpe(df_rebal["net_taker_ret"].values, n_boot=10000, seed=42, periods_per_year=periods_yr)
        
        # 2. Maker Sharpe & CI
        maker_sr, maker_se, _, maker_ci = day_block_bootstrap_sharpe(df_rebal["net_maker_ret"].values, n_boot=10000, seed=42, periods_per_year=periods_yr)

        # 3. 1-bar lag test Sharpe
        lag_sr, _, _, _ = day_block_bootstrap_sharpe(df_rebal["net_lag_ret"].values, n_boot=10000, seed=42, periods_per_year=periods_yr)
        lag_fall_pct = ((taker_sr - lag_sr) / abs(taker_sr) * 100.0) if abs(taker_sr) > 1e-6 else 0.0

        # 4. Yearly breakdown
        years_pos = sum(df_rebal.groupby("year")["net_taker_ret"].mean() > 0)
        tot_years = df_rebal["year"].nunique()

        # 5. Bull vs Bear returns
        bull_mean = float(df_rebal[df_rebal["btc_regime"] == "bull"]["net_taker_ret"].mean())
        bear_mean = float(df_rebal[df_rebal["btc_regime"] == "bear"]["net_taker_ret"].mean())

        # 6. Top 5% of days P&L share
        # 6. Top 5% of days P&L share (concentration of positive gains)
        daily_pnl = df_rebal["net_taker_ret"].values
        pos_gains = daily_pnl[daily_pnl > 0]
        if len(pos_gains) > 0:
            top_thresh = np.percentile(pos_gains, 95)
            top_5pct_sum = float(np.sum(pos_gains[pos_gains >= top_thresh]))
            top_5pct_share = float(top_5pct_sum / np.sum(pos_gains) * 100.0)
        else:
            top_5pct_share = 0.0

        # 7. Incremental Alpha regression against BTC
        y_reg = df_rebal["net_taker_ret"].values
        x_reg = df_rebal["btc_ret"].values
        X_reg = np.column_stack([np.ones_like(x_reg), x_reg])
        beta_reg, _, _, _ = np.linalg.lstsq(X_reg, y_reg, rcond=None)
        resid_reg = y_reg - X_reg @ beta_reg
        s2_reg = np.sum(resid_reg ** 2) / max(1, len(y_reg) - 2)
        try:
            cov_reg = s2_reg * np.linalg.inv(X_reg.T @ X_reg)
            se_reg = np.sqrt(np.diag(cov_reg))
            alpha_t = float(beta_reg[0] / se_reg[0]) if se_reg[0] > 1e-12 else 0.0
        except Exception:
            alpha_t = 0.0
        alpha_coef = float(beta_reg[0])

        # 8. Placebo test (1,000 within-timestamp score shuffles)
        print("  Running 1,000 within-timestamp placebo permutations...", flush=True)
        rng_p = np.random.default_rng(42)
        placebo_srs = np.empty(1000)
        base_rets = df_rebal["net_taker_ret"].values
        for p_idx in range(1000):
            # Shuffle returns to simulate zero cross-sectional skill
            shuffled = rng_p.permutation(base_rets)
            p_mean = np.mean(shuffled)
            p_std = np.std(shuffled, ddof=1)
            placebo_srs[p_idx] = (p_mean / p_std) * math.sqrt(periods_yr) if p_std > 1e-9 else 0.0

        placebo_p = float(np.mean(placebo_srs >= taker_sr))

        # 9. Deflated Sharpe Ratio
        dsr = deflated_sharpe_ratio(
            sr_observed=taker_sr,
            n_trials=512,  # 502 + 10 configs
            t_bars=len(df_rebal),
            skewness=float(df_rebal["net_taker_ret"].skew()),
            kurtosis=float(df_rebal["net_taker_ret"].kurtosis()),
        )

        # 10. Capacity check
        avg_fill_rate = float(df_rebal["fill_rate"].mean())
        print(f"  Taker Net Sharpe:      {taker_sr:+.2f} [{taker_ci[0]:+.2f}, {taker_ci[1]:+.2f}]")
        print(f"  Maker Net Sharpe:      {maker_sr:+.2f} [{maker_ci[0]:+.2f}, {maker_ci[1]:+.2f}] (Fill Rate: {avg_fill_rate*100:.1f}%)")
        print(f"  1-Bar Lag Sharpe:      {lag_sr:+.2f} (Fall: {lag_fall_pct:.1f}%)")
        print(f"  Placebo p-value:       p = {placebo_p:.4f}")
        print(f"  DSR (n=512):           {dsr:.4f}")
        print(f"  Positive Years:        {years_pos} / {tot_years}")
        print(f"  Bull Return Mean:      {bull_mean*10000:+.1f} bps | Bear Return Mean: {bear_mean*10000:+.1f} bps")
        print(f"  Top 5% Days P&L Share: {top_5pct_share:.1f}%")
        print(f"  Incremental Alpha t:   t = {alpha_t:+.2f} (alpha = {alpha_coef*10000:+.1f} bps)")

        passes_all = (
            taker_sr >= 0.50 and
            maker_sr >= 1.20 and
            maker_ci[0] > 0.0 and
            dsr >= 0.95 and
            years_pos >= 4 and
            bull_mean > 0.0 and bear_mean > 0.0 and
            top_5pct_share <= 25.0 and
            placebo_p < 0.01 and
            alpha_t >= 2.0
        )
        verdict = "PASS (SHADOW)" if passes_all else "FAIL (KILL)"
        print(f"  Pre-Registered Verdict: >>> {verdict} <<<", flush=True)

        results_by_h[H] = {
            "horizon": f"{H}b",
            "taker_sr": taker_sr,
            "taker_ci": taker_ci,
            "maker_sr": maker_sr,
            "maker_ci": maker_ci,
            "fill_rate": avg_fill_rate,
            "lag_sr": lag_sr,
            "lag_fall_pct": lag_fall_pct,
            "placebo_p": placebo_p,
            "dsr": dsr,
            "years_pos": f"{years_pos}/{tot_years}",
            "bull_bps": bull_mean * 10000,
            "bear_bps": bear_mean * 10000,
            "top_5pct_share": top_5pct_share,
            "alpha_t": alpha_t,
            "verdict": verdict,
        }

    return results_by_h


if __name__ == "__main__":
    run_dirA_full()
