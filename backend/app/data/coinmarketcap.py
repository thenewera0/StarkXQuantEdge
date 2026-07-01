"""CoinMarketCap global metrics -> a DETERMINISTIC crypto macro/cross-asset score.

Why CMC here (and not as another price feed): Binance already gives us OHLCV. What CMC adds that
we don't otherwise have is MARKET-WIDE context — total-market-cap breadth and BTC dominance.
That is exactly the "macro / cross-asset" factor category, which was empty before.

The macro NUMBER is computed in code (PLAN.md rule); the LLM only narrates it. Cached to respect
the 20k/mo cap — global metrics move slowly, so a 5-minute TTL is plenty.
"""

from __future__ import annotations

import math
import time

import httpx

from ..config import settings

_GLOBAL_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
_TTL = 300  # seconds
_cache: dict[str, tuple[float, dict]] = {}


def _tanh100(x: float) -> float:
    return 100.0 * math.tanh(x)


def fetch_global_metrics() -> dict | None:
    """Return {btc_dominance, eth_dominance, market_cap_change_24h} or None. Never raises."""
    if not settings.coinmarketcap_api_key:
        return None

    now = time.time()
    cached = _cache.get("global")
    if cached and now - cached[0] < _TTL:
        return cached[1]

    headers = {"X-CMC_PRO_API_KEY": settings.coinmarketcap_api_key, "Accept": "application/json"}
    try:
        resp = httpx.get(_GLOBAL_URL, headers=headers, params={"convert": "USD"}, timeout=15.0)
        resp.raise_for_status()
        data = resp.json().get("data", {})
    except (httpx.HTTPError, ValueError):
        return None

    usd = (data.get("quote") or {}).get("USD") or {}
    metrics = {
        "btc_dominance": data.get("btc_dominance"),
        "eth_dominance": data.get("eth_dominance"),
        "market_cap_change_24h": usd.get("total_market_cap_yesterday_percentage_change"),
    }
    _cache["global"] = (now, metrics)
    return metrics


def _base_symbol(symbol: str) -> str:
    s = symbol.upper()
    for quote in ("USDT", "USDC", "USD", "BUSD"):
        if s.endswith(quote):
            return s[: -len(quote)]
    return s.split("/")[0]


def crypto_macro_score(symbol: str) -> dict:
    """Return {'score': -100..100 or None, 'btc_dominance': .., 'market_cap_change_24h': ..}.

    Breadth: total-market-cap 24h change = crypto-wide risk-on/off (directional for all coins).
    Dominance tilt: high BTC dominance favors BTC and pressures alts; low dominance, the reverse.
    """
    m = fetch_global_metrics()
    if not m:
        return {"score": None, "btc_dominance": None, "market_cap_change_24h": None}

    breadth = None
    change = m.get("market_cap_change_24h")
    if change is not None:
        breadth = _tanh100(float(change) / 3.0)  # ~3% market move -> strong read

    tilt = None
    dom = m.get("btc_dominance")
    if dom is not None:
        is_btc = _base_symbol(symbol) == "BTC"
        signed = (float(dom) - 50.0) / 50.0 * 100.0  # 50% dominance = neutral
        tilt = signed if is_btc else -signed

    if breadth is not None and tilt is not None:
        score = max(-100.0, min(100.0, 0.7 * breadth + 0.3 * tilt))
    elif breadth is not None:
        score = breadth
    elif tilt is not None:
        score = tilt
    else:
        score = None

    return {
        "score": round(score, 1) if score is not None else None,
        "btc_dominance": round(dom, 2) if dom is not None else None,
        "market_cap_change_24h": round(change, 2) if change is not None else None,
    }
