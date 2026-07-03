"""Turn a deterministic signal dict into a written rationale.

If OPENROUTER_API_KEY is set, we ask an OpenRouter model to narrate. The system prompt forbids
inventing or altering numbers — the model may only reference the values we pass. If no key is
configured (local dev default), we fall back to a deterministic template so the UI still works.
"""

from __future__ import annotations

import json
import time

import httpx

from ..config import settings
from ..factors.weights import weights_for_interval

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Cache the LLM rationale per (symbol, interval, bar, label) so repeated /explain calls for the
# SAME bar don't re-hit the LLM. A rationale is stable within a bar; regenerating it every poll
# was the source of runaway OpenRouter cost.
_rationale_cache: dict[tuple, tuple[float, dict]] = {}
_RATIONALE_TTL = 3600

_SYSTEM = (
    "You are a trading decision-support analyst. You are given structured, pre-computed numbers "
    "(category scores in [-100,100], a composite, a confidence, and trade levels). "
    "RULES: Never invent, change, or compute any number. Only reference the numbers provided. "
    "Write 2-4 plain sentences explaining which categories drove the signal and the main risk. "
    "Be sober and non-promotional. This is decision-support, not financial advice."
)


def _top_drivers(signal: dict, k: int = 3) -> list[tuple[str, float]]:
    """Categories with the largest weighted contribution to the composite."""
    weights = weights_for_interval(signal["interval"])
    contrib = []
    for cat, score in signal["categories"].items():
        if score is None:
            continue
        contrib.append((cat, weights.get(cat, 0.0) * score))
    contrib.sort(key=lambda x: abs(x[1]), reverse=True)
    return contrib[:k]


def _fallback(signal: dict) -> str:
    drivers = _top_drivers(signal)
    driver_txt = ", ".join(f"{c} ({signal['categories'][c]:+.0f})" for c, _ in drivers) or "no strong category"
    lv = signal["levels"]
    bias = signal["label"]
    line = (
        f"{bias} bias on {signal['symbol']} {signal['interval']} with composite "
        f"{signal['composite']:+.0f} and {signal['confidence']:.0f}% confidence. "
        f"Main drivers: {driver_txt}."
    )
    if lv["direction"] != "flat":
        line += (
            f" Plan: {lv['direction']} near {lv['entry']}, stop {lv['stop']}, target {lv['target']} "
            f"({lv['reward_risk']:.1f}R). "
        )
    line += "Confidence is modest and backtested edge is weak — size small and honor the stop."
    return line


def build_rationale(signal: dict) -> dict:
    """Return {'rationale': str, 'source': 'openrouter'|'fallback', 'model': str|None}. Cached per bar."""
    if not settings.openrouter_api_key:
        return {"rationale": _fallback(signal), "source": "fallback", "model": None}

    key = (signal.get("symbol"), signal.get("interval"), signal.get("as_of"), signal.get("label"))
    now = time.time()
    cached = _rationale_cache.get(key)
    if cached and now - cached[0] < _RATIONALE_TTL:
        return cached[1]

    payload = {
        "model": settings.openrouter_model_strong,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(signal, default=str)},
        ],
        "temperature": 0.3,
        "max_tokens": 220,
    }
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "Content-Type": "application/json"}
    try:
        resp = httpx.post(_OPENROUTER_URL, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        result = {"rationale": text, "source": "openrouter", "model": settings.openrouter_model_strong}
        _rationale_cache[key] = (now, result)
        return result
    except (httpx.HTTPError, KeyError, IndexError):
        # Degrade gracefully — never let an LLM outage break the signal.
        return {"rationale": _fallback(signal), "source": "fallback", "model": None}
