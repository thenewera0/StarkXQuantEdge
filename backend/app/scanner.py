"""Autonomous signal scanner — the 'find signals & give signals' stage of the loop.

It sweeps a watchlist of popular crypto + forex pairs, computes the deterministic signal for each,
and LOGS the ones that are actionable (not Neutral, confidence >= threshold) with their entry/
stop/target. From there the existing pieces take over:

    scanner (find + give)  ->  persistence (log)  ->  resolver (verify)  ->  learning (self-improve)

Cost safety: scanning runs the DETERMINISTIC engine only (no LLM) and disables the per-symbol news
call (NewsAPI free tier is 100/day) — macro is cached, so a full sweep is a handful of cheap data
requests. The LLM debate stays on-demand in the UI. Duplicate bars are skipped so a 30-minute
cadence never re-logs the same 4h candle.
"""

from __future__ import annotations

from . import persistence
from .config import settings
from .signal_service import compute_signal

POPULAR: dict[str, list[str]] = {
    "crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"],
    "forex": ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"],
}
SCAN_INTERVALS: dict[str, list[str]] = {
    "crypto": ["4h"],
    "forex": ["1h"],
}

_ACTIONABLE = {"Buy", "Strong Buy", "Sell", "Strong Sell"}


def scan_once(min_confidence: float | None = None) -> dict:
    """Sweep popular pairs, log actionable signals, return a summary of what was emitted."""
    threshold = settings.scanner_min_confidence if min_confidence is None else min_confidence
    scanned = 0
    errors = 0
    emitted: list[dict] = []

    for market, symbols in POPULAR.items():
        for symbol in symbols:
            for interval in SCAN_INTERVALS[market]:
                scanned += 1
                try:
                    sig = compute_signal(symbol, interval, market=market, with_news=False)
                except Exception:
                    errors += 1
                    continue

                if sig["label"] not in _ACTIONABLE or sig["confidence"] < threshold:
                    continue
                if persistence.signal_exists(sig["symbol"], interval, sig["as_of"]):
                    continue  # already logged this bar

                sid = persistence.log_decision(sig)
                lv = sig["levels"]
                emitted.append({
                    "id": sid, "symbol": sig["symbol"], "market": market, "interval": interval,
                    "label": sig["label"], "confidence": sig["confidence"], "regime": sig.get("regime"),
                    "entry": lv["entry"], "stop": lv["stop"], "target": lv["target"],
                })

    return {
        "scanned": scanned, "errors": errors, "emitted": len(emitted),
        "min_confidence": threshold, "signals": emitted,
    }
