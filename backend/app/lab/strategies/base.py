"""StarkX LAB: Strategy Base Utilities & Technical Indicators.

Pure functions operating strictly on closed historical bars to guarantee lookahead invariance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """True Range & Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def calc_rsi(series: pd.Series, period: int = 2) -> pd.Series:
    """Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # If loss was 0, RSI is 100; if gain was 0, RSI is 0
    fill_vals = pd.Series(np.where(avg_gain > 0, 100.0, 50.0), index=rsi.index)
    rsi = rsi.fillna(fill_vals)
    return rsi


def calc_bollinger(series: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands: (upper, middle, lower)."""
    mid = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std()
    upper = mid + (num_std * std)
    lower = mid - (num_std * std)
    return upper, mid, lower


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (ADX)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    tr_smooth = pd.Series(tr).rolling(window=period, min_periods=period).sum()
    pos_dm_smooth = pd.Series(pos_dm, index=df.index).rolling(window=period, min_periods=period).sum()
    neg_dm_smooth = pd.Series(neg_dm, index=df.index).rolling(window=period, min_periods=period).sum()
    
    plus_di = 100 * (pos_dm_smooth / tr_smooth.replace(0, np.nan))
    minus_di = 100 * (neg_dm_smooth / tr_smooth.replace(0, np.nan))
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.rolling(window=period, min_periods=period).mean()
    return adx.fillna(0.0)
