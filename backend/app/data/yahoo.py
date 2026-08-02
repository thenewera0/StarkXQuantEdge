"""Yahoo Finance chart fetcher — forex, commodity futures, indices, bonds, equities, ETFs.

This is the breadth provider. Twelve Data is capped at 800 requests/day on the free tier, which
cannot sustain a universe of hundreds of instruments; Yahoo's public chart endpoint needs no API
key, tolerates a scan-rate of requests, and serves ~5 years of daily bars and ~2 years of hourly
bars for essentially every liquid instrument on earth.

What it covers, in Yahoo's notation:
    forex        'EURUSD=X', 'USDJPY=X'   (no volume — FX is OTC, so volume factors go neutral)
    commodities  'GC=F' gold, 'CL=F' WTI, 'ZC=F' corn   (real exchange volume)
    indices      '^GSPC' S&P 500, '^N225' Nikkei
    bonds/rates  'TLT', 'ZN=F', '^TNX'
    equities     'AAPL'  /  ETFs 'SPY'

Returns the same OHLCV frame shape as the Binance fetcher (index = bar close time UTC; columns
open/high/low/close/volume as float), so every downstream indicator, backtest and sizing path is
provider-agnostic and needs no changes.

Two behaviours worth knowing:
  * Yahoo has no 4h/2h bar. Those are RESAMPLED from 1h, right-labelled and right-closed so the
    index still means "bar close time" exactly like Binance.
  * Non-24h markets (futures, equities) have session gaps and holidays. That is real, not bad data
    — the validator treats a gap as a gap, and indicators run on bar sequence, not wall-clock.
"""

from __future__ import annotations

import threading
import time

import httpx
import pandas as pd

_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
# Yahoo rejects the default httpx agent on some edges; a browser UA is the documented workaround.
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"}

# Yahoo's own interval strings. Anything not here is synthesised by resampling.
_NATIVE = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h",
           "1d": "1d", "1w": "1wk", "1M": "1mo"}
# Intervals we build by resampling a finer native bar: target -> (native, pandas rule)
_DERIVED = {"2h": ("1h", "2h"), "4h": ("1h", "4h"), "6h": ("1h", "6h"), "12h": ("1h", "12h")}

# Yahoo caps how far back each interval may be requested. Asking beyond the cap returns an error,
# so the range is always clamped to what the interval actually supports.
_MAX_RANGE_DAYS = {"1m": 7, "5m": 58, "15m": 58, "30m": 58, "1h": 726, "1d": 9000, "1wk": 9000, "1mo": 9000}
_BAR_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 1440, "1wk": 10080, "1mo": 43200}

# A scan sweeps the same instrument for several intervals and several consumers within a few
# minutes. Caching by (symbol, interval) collapses that to one network call per bar period.
_TTL = {"1m": 45, "5m": 120, "15m": 240, "30m": 420, "1h": 900, "1d": 3600, "1wk": 21600, "1mo": 43200}
_cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}
_lock = threading.Lock()


def _range_for(native: str, bars: int) -> str:
    """Smallest Yahoo `range` that can contain `bars` of `native` interval.

    Deliberately over-asks: sessions have gaps (weekends for FX, nights and holidays for futures),
    so calendar days per bar is always worse than the arithmetic suggests. Over-asking costs
    nothing — the response is trimmed to `bars` on the way out.
    """
    per_day = 1440 / _BAR_MINUTES[native]
    if native in ("1d", "1wk", "1mo"):
        days = bars * (1 if native == "1d" else 7 if native == "1wk" else 31) * 1.5
    else:
        days = (bars / per_day) * 2.6      # ~24/7 assumed off; futures trade ~23h, FX ~5 days/week
    days = int(min(max(days, 5), _MAX_RANGE_DAYS[native]))
    for label, d in (("1d", 1), ("5d", 5), ("1mo", 31), ("3mo", 92), ("6mo", 183),
                     ("1y", 366), ("2y", 731), ("5y", 1827), ("10y", 3653)):
        if days <= d:
            return label
    return "max"


def _get(symbol: str, native: str, bars: int) -> pd.DataFrame:
    """One raw Yahoo call -> OHLCV frame. No caching, no resampling."""
    url = f"{_BASE}/{symbol}"
    params = {"interval": native, "range": _range_for(native, bars),
              "includePrePost": "false", "events": "div,splits"}
    try:
        resp = httpx.get(url, params=params, headers=_HEADERS, timeout=25.0)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Yahoo fetch failed for {symbol} {native}: {exc}") from exc

    chart = (payload or {}).get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"Yahoo error for {symbol}: {chart['error'].get('description')}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo returned no result for {symbol} {native}")

    res = results[0]
    stamps = res.get("timestamp") or []
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    if not stamps or not quote.get("close"):
        raise RuntimeError(f"Yahoo returned no bars for {symbol} {native}")

    df = pd.DataFrame({
        "open": quote.get("open"), "high": quote.get("high"),
        "low": quote.get("low"), "close": quote.get("close"),
        "volume": quote.get("volume"),
    }, index=pd.to_datetime(stamps, unit="s", utc=True))

    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # FX and indices carry no volume. Zero (not NaN) keeps volume-based factors neutral rather
    # than poisoning every downstream mean with NaN.
    df["volume"] = df["volume"].fillna(0.0)
    df = df.dropna(subset=["open", "high", "low", "close"])
    if df.empty:
        raise RuntimeError(f"Yahoo bars for {symbol} {native} were all null")

    # Repair incoherent bars. Yahoo derives the FX high/low from one aggregation and the
    # open/close from a different tick stream, so a few bars per year have a close sitting a pip
    # or two OUTSIDE its own range (measured: 9 of 300 daily EUR/USD bars). The error is tiny in
    # price terms and fatal in logic terms — true range goes negative, and a backtest checking
    # "did the high reach my target" silently misses fills that really happened. Widening the
    # range to contain open and close is the conservative repair: it never moves the close (the
    # price every signal is computed from) and never invents a move that did not occur.
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)

    # Yahoo stamps a bar at its OPEN. Binance stamps at CLOSE, and the whole engine assumes close
    # stamping (a bar is only knowable once it has closed). Shift so the two agree — without this,
    # every backtest on a Yahoo instrument would read one bar into the future.
    if native in _BAR_MINUTES and native not in ("1wk", "1mo"):
        df.index = df.index + pd.Timedelta(minutes=_BAR_MINUTES[native])
    df.index.name = "close_time"
    return df[~df.index.duplicated(keep="last")].sort_index()


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregate finer bars into `rule`-sized ones, keeping close-time stamping."""
    out = df.resample(rule, label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return out.dropna(subset=["open", "high", "low", "close"])


def fetch_klines(symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
    """Return `limit` OHLCV bars for a Yahoo symbol, newest last. Cached per bar period."""
    if interval in _DERIVED:
        native, rule = _DERIVED[interval]
        factor = int(pd.Timedelta(rule) / pd.Timedelta(hours=1))
        raw = fetch_klines(symbol, native, limit * factor + factor)
        return _resample(raw, rule).tail(limit)

    native = _NATIVE.get(interval)
    if native is None:
        raise ValueError(f"Unsupported interval '{interval}' for Yahoo")

    key = (symbol, native)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _TTL.get(native, 900) and len(hit[1]) >= limit:
            return hit[1].tail(limit).copy()

    df = _get(symbol, native, max(limit, 400))
    with _lock:
        _cache[key] = (now, df)
    return df.tail(limit).copy()


def fetch_klines_history(symbol: str, interval: str = "1d", total: int = 1000) -> pd.DataFrame:
    """As much history as Yahoo will serve for this interval, capped at `total` bars.

    Same name and contract as the Binance history fetcher so callers can swap providers freely.
    Yahoo returns the whole window in one response, so unlike Binance there is nothing to page.
    """
    return fetch_klines(symbol, interval, total)


def quote(symbol: str) -> dict | None:
    """Latest price + session context, cheap. None when the symbol is unknown or delisted."""
    try:
        df = fetch_klines(symbol, "1d", 3)
    except (RuntimeError, ValueError):
        return None
    if df.empty:
        return None
    px = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2]) if len(df) > 1 else px
    return {"symbol": symbol, "price": px,
            "change_pct": round((px / prev - 1) * 100, 3) if prev else 0.0,
            "as_of": df.index[-1].isoformat()}
