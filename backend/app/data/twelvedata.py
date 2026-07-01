"""Twelve Data REST fetcher — forex, US equities, indices, commodities.

Free tier is rate-limited (8 requests/min, 800/day), so callers should cache. Returns the same
OHLCV DataFrame shape as the Binance fetcher so the rest of the engine is provider-agnostic.
"""

from __future__ import annotations

import httpx
import pandas as pd

from ..config import settings

_BASE = "https://api.twelvedata.com/time_series"

# Map our internal intervals to Twelve Data's interval strings.
_INTERVAL_MAP = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h",
    "1d": "1day", "1w": "1week",
}


def fetch_klines(symbol: str = "EUR/USD", interval: str = "1h", outputsize: int = 500) -> pd.DataFrame:
    """Return an OHLCV DataFrame indexed by datetime (UTC, oldest first).

    `symbol` uses Twelve Data notation: forex 'EUR/USD', equities 'AAPL', gold 'XAU/USD'.
    """
    if not settings.twelvedata_api_key:
        raise RuntimeError("TWELVEDATA_API_KEY is not set")
    td_interval = _INTERVAL_MAP.get(interval)
    if td_interval is None:
        raise ValueError(f"Unsupported interval '{interval}' for Twelve Data")

    params = {
        "symbol": symbol,
        "interval": td_interval,
        "outputsize": max(1, min(int(outputsize), 5000)),
        "order": "ASC",
        "timezone": "UTC",
        "format": "JSON",
        "apikey": settings.twelvedata_api_key,
    }
    try:
        resp = httpx.get(_BASE, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Twelve Data fetch failed for {symbol} {interval}: {exc}") from exc

    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Twelve Data error for {symbol}: {data.get('message')}")
    values = data.get("values") if isinstance(data, dict) else None
    if not values:
        raise RuntimeError(f"Twelve Data returned no values for {symbol} {interval}")

    df = pd.DataFrame(values)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.set_index("datetime").sort_index()
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Forex returns no volume column; default to 0 so volume-based factors stay neutral.
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
    else:
        df["volume"] = 0.0
    return df[["open", "high", "low", "close", "volume"]].dropna(subset=["open", "high", "low", "close"])
