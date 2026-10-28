"""StarkX QuantEdge v2: Point-in-Time Data Infrastructure & Historical Cache.

Features:
1. Daily OHLCV with cache: BTC and ETH from earliest history (Aug 2017 to Oct 2026).
2. Point-in-Time Basket: Top 15 USDT perps by trailing 90-day USD volume with >= 365 days history at monthly rebalance dates.
3. Funding rate series for carry analysis.
4. Truncation invariance: Verifies that features at t computed on data[:t] equal features on data[:t+k].
"""

from __future__ import annotations

import functools
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


_DATA_CACHE_DIR = Path(__file__).resolve().parents[2] / "data_cache"


def get_daily_asset(symbol: str, include_pre_2017: bool = False) -> pd.DataFrame:
    """Loads and resamples historical data to clean daily OHLCV bars.
    
    For BTC and ETH, merges 2017-2020 daily data with 2021-2026 4h data.
    If include_pre_2017 is True and pre-2017 daily parquet exists (e.g. BTC 2014-2016),
    prepends historical bars.
    For all other coins, resamples 4h parquet cache to daily.
    """
    sym = symbol.upper()
    pre_2017_path = _DATA_CACHE_DIR / f"{sym}_daily_2014_2016.parquet"
    pre_2021_path = _DATA_CACHE_DIR / f"{sym}_daily_2017_2020.parquet"
    cur_4h_path = _DATA_CACHE_DIR / f"{sym}_4h.parquet"

    df_pre_2017 = None
    if include_pre_2017 and pre_2017_path.exists():
        df_pre_2017 = pd.read_parquet(pre_2017_path)
        if not isinstance(df_pre_2017.index, pd.DatetimeIndex) and "open_time" in df_pre_2017.columns:
            df_pre_2017 = df_pre_2017.set_index("open_time")
        df_pre_2017.index = pd.to_datetime(df_pre_2017.index, utc=True)

    df_pre = None
    if pre_2021_path.exists():
        df_pre = pd.read_parquet(pre_2021_path)
        if not isinstance(df_pre.index, pd.DatetimeIndex) and "open_time" in df_pre.columns:
            df_pre = df_pre.set_index("open_time")
        df_pre.index = pd.to_datetime(df_pre.index, utc=True)

    df_post = None
    if cur_4h_path.exists():
        df_raw = pd.read_parquet(cur_4h_path)
        if not isinstance(df_raw.index, pd.DatetimeIndex) and "open_time" in df_raw.columns:
            df_raw = df_raw.set_index("open_time")
        df_raw.index = pd.to_datetime(df_raw.index, utc=True)
        # Resample to daily (1D)
        df_post = df_raw.resample("1D").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()
        if "quote_volume" in df_raw.columns:
            df_post["quote_volume"] = df_raw["quote_volume"].resample("1D").sum()
        else:
            df_post["quote_volume"] = df_post["volume"] * df_post["close"]

    dfs_to_concat = []
    if df_pre_2017 is not None:
        if df_pre is not None:
            pre_2017_cut = df_pre_2017.loc[df_pre_2017.index < df_pre.index[0]]
            dfs_to_concat.append(pre_2017_cut[["open", "high", "low", "close", "volume", "quote_volume"]])
        elif df_post is not None:
            pre_2017_cut = df_pre_2017.loc[df_pre_2017.index < df_post.index[0]]
            dfs_to_concat.append(pre_2017_cut[["open", "high", "low", "close", "volume", "quote_volume"]])
        else:
            dfs_to_concat.append(df_pre_2017[["open", "high", "low", "close", "volume", "quote_volume"]])

    if df_pre is not None and df_post is not None:
        pre_cut = df_pre.loc[df_pre.index < df_post.index[0]]
        dfs_to_concat.append(pre_cut[["open", "high", "low", "close", "volume", "quote_volume"]])
        dfs_to_concat.append(df_post[["open", "high", "low", "close", "volume", "quote_volume"]])
    elif df_pre is not None:
        dfs_to_concat.append(df_pre[["open", "high", "low", "close", "volume", "quote_volume"]])
    elif df_post is not None:
        dfs_to_concat.append(df_post[["open", "high", "low", "close", "volume", "quote_volume"]])

    if dfs_to_concat:
        combined = pd.concat(dfs_to_concat)
        combined = combined[~combined.index.duplicated(keep="first")].sort_index()
        return combined
    else:
        raise FileNotFoundError(f"No parquet data found for symbol {symbol} in {_DATA_CACHE_DIR}")


@functools.lru_cache(maxsize=64)
def get_available_universe_symbols() -> List[str]:
    """Returns sorted list of symbols available in 4h parquet cache."""
    files = list(_DATA_CACHE_DIR.glob("*_4h.parquet"))
    symbols = sorted(set(f.name.replace("_4h.parquet", "") for f in files))
    return symbols


def build_point_in_time_basket(
    rebalance_date: datetime | str,
    top_n: int = 15,
    min_history_days: int = 365,
    trailing_vol_days: int = 90
) -> List[str]:
    """Selects top N coins by trailing USD volume at rebalance date using ONLY past data.
    
    Zero lookahead: Every coin must have at least `min_history_days` before `rebalance_date`.
    Volume is computed strictly on [rebalance_date - trailing_vol_days, rebalance_date].
    """
    reb_dt = pd.to_datetime(rebalance_date, utc=True)
    all_syms = get_available_universe_symbols()
    
    candidates = []
    for sym in all_syms:
        try:
            df = get_daily_asset(sym)
        except Exception:
            continue
            
        # Filter data strictly up to rebalance_date
        past_df = df.loc[df.index <= reb_dt]
        if len(past_df) < min_history_days:
            continue
            
        # Check if latest available bar is reasonably recent (within 5 days of rebalance date)
        if (reb_dt - past_df.index[-1]).total_seconds() > 5 * 86400:
            continue
            
        # Trailing 90-day USD volume
        window_start = reb_dt - pd.Timedelta(days=trailing_vol_days)
        window_df = past_df.loc[past_df.index >= window_start]
        if len(window_df) < trailing_vol_days * 0.7:  # At least 70% of days present
            continue
            
        usd_vol = (window_df["volume"] * window_df["close"]).sum()
        candidates.append((sym, usd_vol))
        
    candidates.sort(key=lambda x: x[1], reverse=True)
    selected = [sym for sym, _ in candidates[:top_n]]
    return selected


def verify_truncation_invariance(
    feature_func,
    df: pd.DataFrame,
    t_idx: int,
    k_steps: int = 30
) -> bool:
    """Asserts that features computed at time t on data[:t] are identical to data[:t+k].
    
    Ensures that no forward-looking bias, leak, or centering occurs in indicator computation.
    """
    assert t_idx < len(df) - k_steps, "Insufficient future data for truncation invariance check"
    
    df_truncated = df.iloc[:t_idx + 1].copy()
    df_extended = df.iloc[:t_idx + 1 + k_steps].copy()
    
    feats_t = feature_func(df_truncated)
    feats_tk = feature_func(df_extended)
    
    # Compare the features at position t_idx
    # Last row of feats_t vs row t_idx of feats_tk
    val_t = feats_t.iloc[-1]
    val_tk = feats_tk.iloc[t_idx]
    
    if isinstance(val_t, pd.Series):
        diff = (val_t - val_tk).abs().max()
        return bool(diff < 1e-9)
    else:
        return bool(abs(val_t - val_tk) < 1e-9)
