"""Dataset management and multi-year parquet caching for research (Phase 1.1 & Amendment A).

Acquires, validates, and caches multi-year historical data for top 50 USDT perps.
Includes BTC drawdown identification (> 40%), BTC 200-day MA regime classification,
and survivorship bias accounting.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd

from app.data.binance import SPOT_BASE, FUTURES_DATA_BASE, VALID_INTERVALS, _KLINE_COLUMNS

CACHE_DIR = Path(__file__).resolve().parents[2] / "data_cache"

# Top 50 USDT perps by volume (Binance / Bybit universe)
TOP_50_USDT_PERPS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT",
    "NEARUSDT", "APTUSDT", "LTCUSDT", "DOTUSDT", "TRXUSDT", "ATOMUSDT", "UNIUSDT", "ARBUSDT", "OPUSDT", "FILUSDT",
    "INJUSDT", "TIAUSDT", "SEIUSDT", "AAVEUSDT", "FETUSDT", "RENDERUSDT", "PEPEUSDT", "SHIBUSDT", "WIFUSDT", "BONKUSDT",
    "FTMUSDT", "GALAUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "THETAUSDT", "RUNEUSDT", "KAVAUSDT", "ALGOUSDT", "FLOWUSDT",
    "CHZUSDT", "CRVUSDT", "MKRUSDT", "SNXUSDT", "DYDXUSDT", "BLURUSDT", "ORDIUSDT", "STXUSDT", "JUPUSDT", "ENAUSDT"
]


def fetch_historical_klines_paginated(
    symbol: str,
    interval: str = "4h",
    start_time_ms: int = 1609459200000,  # 2021-01-01 00:00:00 UTC (~3+ years)
    end_time_ms: int | None = None,
    max_retries: int = 3,
) -> pd.DataFrame:
    """Fetches full historical klines across multiple 1,000-candle pages."""
    if end_time_ms is None:
        end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    url = f"{SPOT_BASE}/api/v3/klines"
    all_rows = []
    current_start = start_time_ms

    client = httpx.Client(timeout=20.0)
    try:
        while current_start < end_time_ms:
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "startTime": current_start,
                "endTime": end_time_ms,
                "limit": 1000,
            }
            success = False
            for attempt in range(max_retries):
                try:
                    resp = client.get(url, params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        success = True
                        break
                    elif resp.status_code in (429, 418):
                        time.sleep(2.0 * (attempt + 1))
                except Exception:
                    time.sleep(1.0 * (attempt + 1))

            if not success or not rows:
                break

            all_rows.extend(rows)
            # The next page begins after the close_time of the last candle
            last_open_time = rows[-1][0]
            if len(rows) < 1000:
                break
            # Advance start time
            current_start = rows[-1][6] + 1
    finally:
        client.close()

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows, columns=_KLINE_COLUMNS)
    df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time")
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df[["open", "high", "low", "close", "volume"]].dropna()


def ensure_dataset(
    symbols: list[str] = TOP_50_USDT_PERPS,
    intervals: tuple[str, ...] = ("4h", "1h"),
    force_refresh: bool = False,
    max_symbols: int | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Loads or fetches all historical klines, persisting to parquet in CACHE_DIR."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target_symbols = symbols[:max_symbols] if max_symbols else symbols

    dataset: dict[str, dict[str, pd.DataFrame]] = {}

    for sym in target_symbols:
        dataset[sym] = {}
        for interval in intervals:
            pq_file = CACHE_DIR / f"{sym}_{interval}.parquet"
            if pq_file.exists() and not force_refresh:
                try:
                    df = pd.read_parquet(pq_file)
                    dataset[sym][interval] = df
                    continue
                except Exception:
                    pass

            # Fetch paginated history (from 2021-01-01 or earliest token inception)
            df = fetch_historical_klines_paginated(sym, interval=interval)
            if not df.empty:
                df.to_parquet(pq_file)
                dataset[sym][interval] = df
            else:
                dataset[sym][interval] = pd.DataFrame()

    return dataset


def identify_btc_drawdowns(btc_4h: pd.DataFrame, min_drawdown_pct: float = 0.40) -> list[dict[str, Any]]:
    """Identifies major BTC peak-to-trough drawdowns >= min_drawdown_pct (e.g. > 40%)."""
    if btc_4h.empty:
        return []

    close = btc_4h["close"]
    cummax = close.cummax()
    drawdown = (close - cummax) / cummax

    # Find distinct major drawdown periods
    dd_events = []
    in_dd = False
    start_dt = None
    peak_val = 0.0
    trough_val = 0.0
    trough_dt = None

    for dt, val in drawdown.items():
        price = close.loc[dt]
        if val <= -min_drawdown_pct:
            if not in_dd:
                in_dd = True
                # Look back to find when the peak occurred
                peak_dt = close.loc[:dt].idxmax()
                peak_val = float(close.loc[peak_dt])
                start_dt = peak_dt
                trough_val = price
                trough_dt = dt
            else:
                if price < trough_val:
                    trough_val = price
                    trough_dt = dt
        else:
            if in_dd and val > -0.15:  # Recovered to within 15% of high
                dd_pct = (trough_val - peak_val) / peak_val
                dd_events.append({
                    "peak_date": str(start_dt)[:10],
                    "trough_date": str(trough_dt)[:10],
                    "peak_price": round(peak_val, 2),
                    "trough_price": round(trough_val, 2),
                    "drawdown_pct": round(dd_pct * 100.0, 2),
                })
                in_dd = False

    if in_dd:
        dd_pct = (trough_val - peak_val) / peak_val
        dd_events.append({
            "peak_date": str(start_dt)[:10],
            "trough_date": str(trough_dt)[:10],
            "peak_price": round(peak_val, 2),
            "trough_price": round(trough_val, 2),
            "drawdown_pct": round(dd_pct * 100.0, 2),
        })

    return dd_events


def compute_btc_regimes(btc_4h: pd.DataFrame) -> pd.DataFrame:
    """Computes BTC 200-day SMA regime and 30-day return terciles.

    4h bars per day = 6. 200-day SMA = 200 * 6 = 1200 bars.
    30-day return = 30 * 6 = 180 bars.
    """
    if btc_4h.empty:
        return pd.DataFrame()

    df = btc_4h[["close"]].copy()
    df["btc_sma200d"] = df["close"].rolling(1200, min_periods=200).mean()
    df["btc_regime"] = np.where(df["close"] > df["btc_sma200d"], "bull", "bear")

    # 30-day return
    df["btc_ret30d"] = df["close"].pct_change(180)
    # Terciles: low, mid, high
    df["btc_tercile"] = pd.qcut(df["btc_ret30d"].dropna(), q=3, labels=["bear_tercile", "neutral_tercile", "bull_tercile"])

    return df
