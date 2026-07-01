"""CryptoQuant on-chain data (F6) — best-effort.

CryptoQuant's API gates endpoints by plan. We try exchange NETFLOW (the highest-signal on-chain
metric): coins leaving exchanges = accumulation (bullish); flowing in = sell pressure (bearish).
If the key lacks access (401/403) or the endpoint shape differs, the on-chain family degrades to
NEUTRAL rather than guessing — no fake numbers. Cached to respect rate limits.
"""

from __future__ import annotations

import time

import httpx

from ..config import settings

_BASE = "https://api.cryptoquant.com/v1"
_TTL = 600
_cache: dict[str, tuple[float, dict]] = {}

# Map our symbols to CryptoQuant asset paths (only majors have rich on-chain data).
_ASSET = {"BTCUSDT": "btc", "ETHUSDT": "eth"}


def _base_asset(symbol: str) -> str | None:
    return _ASSET.get(symbol.upper())


def onchain_score(symbol: str) -> dict:
    """Return {'score': -100..100 or None, 'netflow': .., 'source': ..}. Never raises.

    Positive score = bullish (net outflows / accumulation).
    """
    if not settings.cryptoquant_api_key:
        return {"score": None, "available": False, "reason": "no key"}
    asset = _base_asset(symbol)
    if asset is None:
        return {"score": None, "available": False, "reason": "no on-chain for asset"}

    now = time.time()
    cached = _cache.get(asset)
    if cached and now - cached[0] < _TTL:
        return cached[1]

    url = f"{_BASE}/{asset}/exchange-flows/netflow"
    headers = {"Authorization": f"Bearer {settings.cryptoquant_api_key}"}
    params = {"exchange": "all_exchange", "window": "day", "limit": 7}
    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=15.0)
        if resp.status_code in (401, 403):
            result = {"score": None, "available": False, "reason": f"http {resp.status_code} (plan/endpoint)"}
            _cache[asset] = (now, result)
            return result
        resp.raise_for_status()
        rows = (resp.json().get("result") or {}).get("data") or []
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {"score": None, "available": False, "reason": str(exc)[:80]}

    if not rows:
        return {"score": None, "available": False, "reason": "no data"}

    # Netflow field name varies; pick the first numeric netflow-like value.
    def _netflow(r: dict) -> float | None:
        for k in ("netflow_total", "netflow", "exchange_netflow"):
            if k in r and r[k] is not None:
                return float(r[k])
        return None

    flows = [f for f in (_netflow(r) for r in rows) if f is not None]
    if not flows:
        return {"score": None, "available": False, "reason": "unrecognized shape"}

    latest = flows[-1]
    avg = sum(flows) / len(flows)
    std = (sum((f - avg) ** 2 for f in flows) / len(flows)) ** 0.5 or 1.0
    z = (latest - avg) / std
    # Net OUTFLOW (negative netflow) is bullish -> invert sign, squash.
    import math
    score = round(-100.0 * math.tanh(z / 2.0), 1)
    result = {"score": score, "available": True, "netflow": latest, "source": "cryptoquant"}
    _cache[asset] = (now, result)
    return result
