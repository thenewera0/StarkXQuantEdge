"""CryptoCompare OHLCV — global, not geo-blocked, free (no key needed for basic use).

Used as an automatic fallback when Binance returns 418/451 from cloud IPs (e.g., Render US
datacenters). Returns the same OHLCV DataFrame shape as the Binance fetcher so callers don't care
which source served the data.
"""

from __future__ import annotations

import httpx
import pandas as pd

_BASE = "https://min-api.cryptocompare.com/data/v2"

# our interval -> (endpoint, aggregate)
_INTERVAL = {
    "1m": ("histominute", 1), "5m": ("histominute", 5), "15m": ("histominute", 15),
    "30m": ("histominute", 30), "1h": ("histohour", 1), "2h": ("histohour", 2),
    "4h": ("histohour", 4), "6h": ("histohour", 6), "12h": ("histohour", 12),
    "1d": ("histoday", 1), "3d": ("histoday", 3), "1w": ("histoday", 7),
}


def _base_asset(symbol: str) -> str:
    s = symbol.upper()
    for quote in ("USDT", "USDC", "BUSD", "USD"):
        if s.endswith(quote):
            return s[: -len(quote)]
    return s


def fetch_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500) -> pd.DataFrame:
    """OHLCV DataFrame (open, high, low, close, volume) indexed by UTC close time, oldest first."""
    if interval not in _INTERVAL:
        raise RuntimeError(f"CryptoCompare: unsupported interval '{interval}'")
    endpoint, aggregate = _INTERVAL[interval]
    fsym = _base_asset(symbol)
    limit = max(1, min(int(limit), 2000))

    params = {"fsym": fsym, "tsym": "USD", "limit": limit, "aggregate": aggregate}
    try:
        resp = httpx.get(f"{_BASE}/{endpoint}", params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"CryptoCompare fetch failed for {symbol} {interval}: {exc}") from exc

    if data.get("Response") != "Success":
        raise RuntimeError(f"CryptoCompare error for {symbol}: {data.get('Message')}")
    rows = (data.get("Data") or {}).get("Data") or []
    if not rows:
        raise RuntimeError(f"CryptoCompare returned no data for {symbol} {interval}")

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    df = df.rename(columns={"volumefrom": "volume"})
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    # CryptoCompare pads leading zero-price rows for illiquid history; drop them.
    return df[df["close"] > 0]
