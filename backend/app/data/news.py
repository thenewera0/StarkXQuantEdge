"""NewsAPI headlines -> a DETERMINISTIC lexical sentiment score for the sentiment factor.

Design choice (PLAN.md rule): the sentiment NUMBER is computed in code from a small finance
lexicon, not invented by an LLM. The LLM only narrates later. Crude but transparent and stable.
Results are cached in-process (TTL) so we don't hammer the free NewsAPI quota on every signal.
"""

from __future__ import annotations

import re
import time

import httpx

from ..config import settings

_URL = "https://newsapi.org/v2/everything"
_TTL = 600  # seconds
_cache: dict[str, tuple[float, dict]] = {}

# Map common tickers to a readable news query.
_QUERY = {
    "BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum", "SOLUSDT": "Solana", "BNBUSDT": "BNB",
    "EUR/USD": "euro dollar", "GBP/USD": "pound dollar", "USD/JPY": "yen dollar",
    "XAU/USD": "gold price",
}

_POS = {
    "surge", "surges", "rally", "rallies", "gain", "gains", "soar", "soars", "bull", "bullish",
    "jump", "jumps", "rise", "rises", "boost", "record", "high", "adoption", "approve", "approved",
    "upgrade", "support", "optimism", "strong", "growth", "breakout", "inflow", "inflows",
}
_NEG = {
    "plunge", "plunges", "crash", "crashes", "drop", "drops", "fall", "falls", "bear", "bearish",
    "slump", "selloff", "sell-off", "fear", "fears", "ban", "hack", "hacked", "lawsuit", "fraud",
    "weak", "decline", "declines", "dump", "liquidation", "outflow", "outflows", "warning", "risk",
}

_word_re = re.compile(r"[a-z][a-z\-]+")


def _query_for(symbol: str) -> str:
    return _QUERY.get(symbol.upper(), _QUERY.get(symbol, symbol.split("/")[0]))


def news_sentiment(symbol: str) -> dict:
    """Return {'score': -100..100 or None, 'headlines': int, 'query': str}. Never raises."""
    if not settings.newsapi_key:
        return {"score": None, "headlines": 0, "query": None}

    query = _query_for(symbol)
    now = time.time()
    cached = _cache.get(query)
    if cached and now - cached[0] < _TTL:
        return cached[1]

    params = {
        "q": query, "language": "en", "sortBy": "publishedAt",
        "pageSize": 30, "apiKey": settings.newsapi_key,
    }
    try:
        resp = httpx.get(_URL, params=params, timeout=15.0)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
    except (httpx.HTTPError, ValueError):
        return {"score": None, "headlines": 0, "query": query}

    pos = neg = 0
    for art in articles:
        text = f"{art.get('title') or ''} {art.get('description') or ''}".lower()
        for w in _word_re.findall(text):
            if w in _POS:
                pos += 1
            elif w in _NEG:
                neg += 1

    total = pos + neg
    score = round((pos - neg) / total * 100.0, 1) if total else 0.0
    result = {"score": score, "headlines": len(articles), "query": query}
    _cache[query] = (now, result)
    return result
