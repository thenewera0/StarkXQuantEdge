"""Bybit public v5 market data — derivatives (funding, OI, long/short, order book).

Geo-independent replacement for Binance futures data when Binance geo-blocks cloud IPs (Render).
Bybit uses the same BTCUSDT symbol format, so no mapping is needed. All functions mirror the return
shape of the Binance equivalents in binance.py so they can be used as drop-in fallbacks.
"""

from __future__ import annotations

import httpx

_BASE = "https://api.bybit.com"

# our interval/period -> Bybit intervalTime
_INTERVAL = {"5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1d"}


def _iv(period: str) -> str:
    return _INTERVAL.get(period, "1h")


def _get(path: str, params: dict) -> dict:
    resp = httpx.get(f"{_BASE}{path}", params=params, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    return data.get("result") or {}


def fetch_funding_basis(symbol: str = "BTCUSDT") -> dict:
    """Funding rate + perp/spot basis from the linear-perp ticker."""
    res = _get("/v5/market/tickers", {"category": "linear", "symbol": symbol.upper()})
    rows = res.get("list") or []
    if not rows:
        raise RuntimeError(f"Bybit tickers: no data for {symbol}")
    t = rows[0]
    mark = float(t.get("markPrice") or 0)
    index = float(t.get("indexPrice") or 0)
    basis = (mark - index) / index if index else 0.0
    return {"symbol": symbol.upper(), "funding_rate": float(t.get("fundingRate") or 0), "basis": basis}


def fetch_book_tickers() -> dict[str, dict]:
    """Best bid/ask for every SPOT symbol on Bybit in one call — for cross-exchange arb (§6.3).

    Returns {symbol: {"bid": float, "ask": float}}. Raises on failure (caller degrades gracefully)."""
    res = _get("/v5/market/tickers", {"category": "spot"})
    out: dict[str, dict] = {}
    for r in res.get("list") or []:
        try:
            bid, ask = float(r.get("bid1Price") or 0), float(r.get("ask1Price") or 0)
        except (ValueError, TypeError):
            continue
        if bid > 0 and ask > 0:
            out[r["symbol"]] = {"bid": bid, "ask": ask}
    return out


def fetch_funding_history(symbol: str = "BTCUSDT", limit: int = 120) -> list[float]:
    """Recent funding rates (oldest->newest) from Bybit — fallback for §2.5 z-scoring."""
    res = _get("/v5/market/funding/history",
               {"category": "linear", "symbol": symbol.upper(), "limit": min(int(limit), 200)})
    rows = res.get("list") or []
    rows = sorted(rows, key=lambda r: int(r["fundingRateTimestamp"]))
    return [float(r["fundingRate"]) for r in rows]


def fetch_oi_trend(symbol: str = "BTCUSDT", period: str = "4h") -> dict:
    """Open-interest change vs the prior reading."""
    res = _get("/v5/market/open-interest",
               {"category": "linear", "symbol": symbol.upper(), "intervalTime": _iv(period), "limit": 2})
    rows = res.get("list") or []
    if len(rows) < 2:
        return {"symbol": symbol.upper(), "oi_change": None}
    rows = sorted(rows, key=lambda r: int(r["timestamp"]))
    prev, now = float(rows[0]["openInterest"]), float(rows[-1]["openInterest"])
    return {"symbol": symbol.upper(), "oi_change": (now - prev) / prev if prev else None}


def fetch_long_short_ratio(symbol: str = "BTCUSDT", period: str = "1h") -> dict:
    """Top-trader long/short account ratio (>1 = net long)."""
    res = _get("/v5/market/account-ratio",
               {"category": "linear", "symbol": symbol.upper(), "period": _iv(period), "limit": 1})
    rows = res.get("list") or []
    if not rows:
        return {"symbol": symbol.upper(), "long_short_ratio": None}
    r = rows[0]
    buy, sell = float(r.get("buyRatio") or 0), float(r.get("sellRatio") or 0)
    return {
        "symbol": symbol.upper(), "long_account": buy, "short_account": sell,
        "long_short_ratio": (buy / sell) if sell else None,
    }


def fetch_depth(symbol: str = "BTCUSDT", limit: int = 50) -> dict:
    """Spot order-book imbalance in [-1, 1] (positive = buy-side pressure)."""
    res = _get("/v5/market/orderbook", {"category": "spot", "symbol": symbol.upper(), "limit": min(limit, 200)})
    bid_vol = sum(float(q) for _, q in res.get("b", []))
    ask_vol = sum(float(q) for _, q in res.get("a", []))
    total = bid_vol + ask_vol
    return {
        "symbol": symbol.upper(), "bid_volume": bid_vol, "ask_volume": ask_vol,
        "imbalance": (bid_vol - ask_vol) / total if total > 0 else 0.0,
    }
