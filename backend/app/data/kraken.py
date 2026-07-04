"""Kraken public OHLC — global, no API key, US-friendly (not geo-blocked from cloud IPs).

Fallback for when Binance returns 418/451 from datacenter IPs (Render). Supports the intervals the
app actually uses (15m, 1h, 4h, 1d, 1w). Returns the same OHLCV DataFrame shape as the Binance
fetcher. Note: Kraken uses XBT for BTC, XDG for DOGE, and USD (not USDT); a few Binance-only tokens
(e.g. BNB) aren't listed and will raise, which callers handle gracefully.
"""

from __future__ import annotations

import httpx
import pandas as pd

_URL = "https://api.kraken.com/0/public/OHLC"
_ASSET_MAP = {"BTC": "XBT", "DOGE": "XDG"}
_INTERVAL = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}


def _pair(symbol: str) -> str:
    s = symbol.upper()
    for quote in ("USDT", "USDC", "BUSD", "USD"):
        if s.endswith(quote):
            s = s[: -len(quote)]
            break
    return f"{_ASSET_MAP.get(s, s)}USD"


def fetch_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500) -> pd.DataFrame:
    """OHLCV DataFrame (open, high, low, close, volume) indexed by UTC time, oldest first."""
    if interval not in _INTERVAL:
        raise RuntimeError(f"Kraken: unsupported interval '{interval}'")
    pair = _pair(symbol)
    try:
        resp = httpx.get(_URL, params={"pair": pair, "interval": _INTERVAL[interval]}, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Kraken fetch failed for {symbol} ({pair}) {interval}: {exc}") from exc

    if data.get("error"):
        raise RuntimeError(f"Kraken error for {pair}: {data['error']}")
    result = data.get("result", {})
    key = next((k for k in result if k != "last"), None)
    if not key or not result.get(key):
        raise RuntimeError(f"Kraken returned no data for {pair} {interval}")

    cols = ["time", "open", "high", "low", "close", "vwap", "volume", "count"]
    df = pd.DataFrame(result[key], columns=cols)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    return df.tail(max(1, int(limit)))
