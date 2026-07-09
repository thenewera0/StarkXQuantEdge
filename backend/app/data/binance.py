"""Binance public REST fetchers (keyless).

- Spot klines (OHLCV) from api.binance.com
- Order-book depth from api.binance.com
- Global long/short account ratio from the USDT-M futures data API (fapi.binance.com)

Unofficial-source rule from PLAN.md: these wrap network calls so a failure degrades
gracefully (raises a clear error) rather than returning silently-wrong data.
"""

from __future__ import annotations

import httpx
import pandas as pd

# data-api.binance.vision is Binance's PUBLIC market-data mirror — it serves the same /api/v3/*
# spot endpoints (klines, depth) but is NOT geo-blocked, so it works from US cloud IPs (Render/
# Vercel) where api.binance.com returns 418/451. Futures data (fapi) has no such mirror, so
# funding/OI/long-short degrade to neutral when blocked (already handled best-effort).
SPOT_BASE = "https://data-api.binance.vision"
FUTURES_DATA_BASE = "https://fapi.binance.com"

# Valid kline intervals we expose to the app's timeframe switcher.
VALID_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w",
}

_KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_base", "taker_quote", "ignore",
]

# Seconds per kline interval — used to bound sub-bar (1m) fetches for fill resolution.
INTERVAL_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800, "12h": 43200,
    "1d": 86400, "3d": 259200, "1w": 604800,
}


def fetch_klines_range(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """OHLCV for a bounded [start_ms, end_ms] window (UTC ms). For sub-bar fill resolution.

    Uses the non-geo-blocked spot mirror. Raises on failure so callers can fall back safely.
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'")
    url = f"{SPOT_BASE}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval,
              "startTime": int(start_ms), "endTime": int(end_ms), "limit": 1000}
    resp = httpx.get(url, params=params, timeout=15.0)
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        raise RuntimeError(f"No {interval} klines for {symbol} in window")
    df = pd.DataFrame(rows, columns=_KLINE_COLUMNS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["open", "high", "low", "close", "volume"]].dropna()


def fetch_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Return an OHLCV DataFrame indexed by close time (UTC).

    Columns: open, high, low, close, volume (all float). limit max is 1000 per Binance.
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'. Valid: {sorted(VALID_INTERVALS)}")
    limit = max(1, min(int(limit), 1000))

    url = f"{SPOT_BASE}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    try:
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        rows = resp.json()
    except httpx.HTTPError as exc:
        # Binance geo-blocks cloud IPs (418/451). Fall back to a global source (CryptoCompare).
        from .kraken import fetch_klines as _cc_fetch_klines
        try:
            return _cc_fetch_klines(symbol, interval, limit)
        except RuntimeError:
            raise RuntimeError(f"Binance klines fetch failed for {symbol} {interval}: {exc}") from exc

    if not rows:
        raise RuntimeError(f"Binance returned no klines for {symbol} {interval}")

    df = pd.DataFrame(rows, columns=_KLINE_COLUMNS)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df = df.set_index("close_time")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["open", "high", "low", "close", "volume"]].dropna()


def fetch_klines_history(symbol: str = "BTCUSDT", interval: str = "1h", total: int = 3000) -> pd.DataFrame:
    """Page backwards through Binance klines to assemble up to `total` bars.

    Binance caps each request at 1000 klines, so we walk `endTime` backwards in chunks.
    Returns an OHLCV DataFrame indexed by close time (UTC), oldest first, de-duplicated.
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'. Valid: {sorted(VALID_INTERVALS)}")

    url = f"{SPOT_BASE}/api/v3/klines"
    end_time: int | None = None
    chunks: list[pd.DataFrame] = []
    fetched = 0

    while fetched < total:
        want = min(1000, total - fetched)
        params: dict = {"symbol": symbol.upper(), "interval": interval, "limit": want}
        if end_time is not None:
            params["endTime"] = end_time
        try:
            resp = httpx.get(url, params=params, timeout=20.0)
            resp.raise_for_status()
            rows = resp.json()
        except httpx.HTTPError as exc:
            # Geo-block fallback: return one CryptoCompare batch (up to 2000 bars) and stop paging.
            if not chunks:
                from .kraken import fetch_klines as _cc_fetch_klines
                try:
                    return _cc_fetch_klines(symbol, interval, min(total, 2000))
                except RuntimeError:
                    pass
            raise RuntimeError(f"Binance history fetch failed for {symbol} {interval}: {exc}") from exc
        if not rows:
            break

        df = pd.DataFrame(rows, columns=_KLINE_COLUMNS)
        chunks.append(df)
        fetched += len(rows)
        # Next page ends just before this chunk's first open.
        earliest_open = int(rows[0][0])
        end_time = earliest_open - 1
        if len(rows) < want:
            break  # no more history available

    if not chunks:
        raise RuntimeError(f"Binance returned no history for {symbol} {interval}")

    full = pd.concat(chunks, ignore_index=True)
    full["close_time"] = pd.to_datetime(full["close_time"], unit="ms", utc=True)
    full = full.drop_duplicates(subset="close_time").set_index("close_time").sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        full[col] = pd.to_numeric(full[col], errors="coerce")
    return full[["open", "high", "low", "close", "volume"]].dropna()


def fetch_depth(symbol: str = "BTCUSDT", limit: int = 100) -> dict:
    """Return order-book depth and a derived bid/ask imbalance in [-1, 1].

    imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol). Positive => buy-side pressure.
    """
    url = f"{SPOT_BASE}/api/v3/depth"
    params = {"symbol": symbol.upper(), "limit": max(5, min(int(limit), 5000))}
    try:
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        from .bybit import fetch_depth as _bb_depth
        try:
            return _bb_depth(symbol)
        except (httpx.HTTPError, RuntimeError):
            raise RuntimeError(f"Binance depth fetch failed for {symbol}: {exc}") from exc

    bid_vol = sum(float(q) for _, q in data.get("bids", []))
    ask_vol = sum(float(q) for _, q in data.get("asks", []))
    total = bid_vol + ask_vol
    imbalance = (bid_vol - ask_vol) / total if total > 0 else 0.0
    return {
        "symbol": symbol.upper(),
        "bid_volume": bid_vol,
        "ask_volume": ask_vol,
        "imbalance": imbalance,
    }


def fetch_funding_basis(symbol: str = "BTCUSDT") -> dict:
    """Funding rate + perp/spot basis from the futures premium index (keyless).

    funding_rate: last funding (>0 longs pay shorts -> longs crowded). basis: (mark-index)/index.
    """
    url = f"{FUTURES_DATA_BASE}/fapi/v1/premiumIndex"
    try:
        resp = httpx.get(url, params={"symbol": symbol.upper()}, timeout=15.0)
        resp.raise_for_status()
        d = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        from .bybit import fetch_funding_basis as _bb_funding
        try:
            return _bb_funding(symbol)
        except (httpx.HTTPError, RuntimeError):
            raise RuntimeError(f"Binance premiumIndex failed for {symbol}: {exc}") from exc
    mark = float(d.get("markPrice", 0) or 0)
    index = float(d.get("indexPrice", 0) or 0)
    basis = (mark - index) / index if index else 0.0
    return {
        "symbol": symbol.upper(),
        "funding_rate": float(d.get("lastFundingRate", 0) or 0),
        "basis": basis,
    }


def fetch_oi_trend(symbol: str = "BTCUSDT", period: str = "4h") -> dict:
    """Open-interest trend vs the prior reading (futures data API). Returns oi_change fraction."""
    url = f"{FUTURES_DATA_BASE}/futures/data/openInterestHist"
    try:
        resp = httpx.get(url, params={"symbol": symbol.upper(), "period": period, "limit": 2}, timeout=15.0)
        resp.raise_for_status()
        rows = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        from .bybit import fetch_oi_trend as _bb_oi
        try:
            return _bb_oi(symbol, period)
        except (httpx.HTTPError, RuntimeError):
            raise RuntimeError(f"Binance OI hist failed for {symbol}: {exc}") from exc
    if not rows or len(rows) < 2:
        return {"symbol": symbol.upper(), "oi_change": None}
    prev = float(rows[0]["sumOpenInterest"])
    now = float(rows[-1]["sumOpenInterest"])
    return {"symbol": symbol.upper(), "oi_change": (now - prev) / prev if prev else None}


def fetch_long_short_ratio(symbol: str = "BTCUSDT", period: str = "1h") -> dict:
    """Global long/short account ratio from the futures data API.

    Returns the most recent reading. ratio > 1 => more accounts net long.
    """
    url = f"{FUTURES_DATA_BASE}/futures/data/globalLongShortAccountRatio"
    params = {"symbol": symbol.upper(), "period": period, "limit": 1}
    try:
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        from .bybit import fetch_long_short_ratio as _bb_ls
        try:
            return _bb_ls(symbol, period)
        except (httpx.HTTPError, RuntimeError):
            raise RuntimeError(f"Binance long/short fetch failed for {symbol}: {exc}") from exc

    if not data:
        return {"symbol": symbol.upper(), "long_short_ratio": None}
    latest = data[-1]
    return {
        "symbol": symbol.upper(),
        "long_account": float(latest["longAccount"]),
        "short_account": float(latest["shortAccount"]),
        "long_short_ratio": float(latest["longShortRatio"]),
    }
