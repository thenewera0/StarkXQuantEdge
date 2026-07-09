"""Crypto Fear & Greed Index (alternative.me) — free, keyless. Feeds the sentiment family (F7).

Extremes mean-revert: Extreme Fear (<25) is contrarian-bullish, Extreme Greed (>75) bearish.
We also track the rate-of-change because a fast move toward an extreme often precedes the reversal.
"""

from __future__ import annotations

import time

import httpx

_URL = "https://api.alternative.me/fng/"
_TTL = 600
_cache: tuple[float, dict] | None = None


def fear_greed() -> dict:
    """Return {value, classification, delta} or {value: None}. Cached, never raises."""
    global _cache
    now = time.time()
    if _cache and now - _cache[0] < _TTL:
        return _cache[1]
    try:
        resp = httpx.get(_URL, params={"limit": 2}, timeout=12.0)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except (httpx.HTTPError, ValueError):
        return {"value": None, "classification": None, "delta": None}
    if not data:
        return {"value": None, "classification": None, "delta": None}
    value = int(data[0]["value"])
    prev = int(data[1]["value"]) if len(data) > 1 else value
    result = {"value": value, "classification": data[0].get("value_classification"), "delta": value - prev}
    _cache = (now, result)
    return result


def fng_score() -> float | None:
    """Contrarian sentiment score in [-100, 100]: extreme fear -> bullish (+), extreme greed -> bearish (-)."""
    fg = fear_greed()
    v = fg.get("value")
    if v is None:
        return None
    # 50 neutral; invert so fear is bullish. Scale so 0->+100, 100->-100.
    return round((50 - v) / 50 * 100, 1)


_hist_cache: tuple[float, list[float]] | None = None
_HIST_TTL = 3600


def fng_history(limit: int = 90) -> list[float]:
    """Recent Fear & Greed values (newest first) for z-scoring. Cached, best-effort ([] on failure)."""
    global _hist_cache
    now = time.time()
    if _hist_cache and now - _hist_cache[0] < _HIST_TTL:
        return _hist_cache[1]
    try:
        resp = httpx.get(_URL, params={"limit": limit}, timeout=12.0)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        vals = [float(d["value"]) for d in data]
    except (httpx.HTTPError, ValueError, KeyError):
        return []
    if vals:
        _hist_cache = (now, vals)
    return vals


def fng_zscore() -> float | None:
    """Z-score of the CURRENT F&G vs its ~90d distribution (§2.5). None if data is thin.

    Positive z = greedier than usual (contrarian bearish); negative = more fearful (bullish)."""
    hist = fng_history(90)
    if len(hist) < 20:
        return None
    cur = hist[0]
    mu = sum(hist) / len(hist)
    var = sum((x - mu) ** 2 for x in hist) / len(hist)
    sd = var ** 0.5
    if sd <= 1e-9:
        return 0.0
    return round((cur - mu) / sd, 4)
