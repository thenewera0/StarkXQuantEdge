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

# The engine autonomously trades ONLY where it has a demonstrated edge. Per the P&L record, the
# edge is entirely in CRYPTO (crypto/long ~70% hit, +$2.2k; crypto/short is gated by the direction
# gate when it bleeds). FOREX showed no edge across ~190 trades (long 30%/-$46, short 22%/-$123),
# so it's dropped from the scanner (still viewable on-demand in the UI). Focus > breadth.
POPULAR: dict[str, list[str]] = {
    "crypto": [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
        "LINKUSDT", "LTCUSDT", "DOTUSDT", "TRXUSDT", "ATOMUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT",
        "ARBUSDT", "OPUSDT", "FILUSDT", "INJUSDT", "SUIUSDT", "SEIUSDT", "TIAUSDT", "AAVEUSDT",
        "ETCUSDT", "XLMUSDT", "RUNEUSDT", "GRTUSDT",
    ],
}
SCAN_INTERVALS: dict[str, list[str]] = {
    "crypto": ["1h", "4h"],
}

_ACTIONABLE = {"Buy", "Strong Buy", "Sell", "Strong Sell"}


def _open_slots() -> int:
    """How many NEW positions may still be opened under the tier's concurrency cap.

    Counts live (non-paper) positions that have not yet resolved. Returns a large number when
    persistence is off so local/backtest use is unaffected.
    """
    from . import db, sizing
    if not db.enabled():
        return 99
    cap = sizing.tier_for_equity(settings.account_equity_usd)["max_concurrent"]
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """select count(*) from signals s
                   where not s.shadow and s.entry is not null and s.label <> 'Neutral'
                     and not exists (select 1 from outcomes o where o.signal_id = s.id)"""
            )
            open_now = int(cur.fetchone()[0])
    except Exception:
        return 0  # cannot verify exposure -> do not add risk
    return max(0, cap - open_now)


def scan_once(min_confidence: float | None = None) -> dict:
    """Sweep popular pairs, log actionable signals, return a summary of what was emitted."""
    threshold = settings.scanner_min_confidence if min_confidence is None else min_confidence
    scanned = 0
    errors = 0
    emitted: list[dict] = []

    # CONCENTRATION CAP — the lesson from 2026-07-28. The engine opened 14 correlated crypto longs
    # inside two hours; a single ~1.6% BTC dip stopped out ALL of them, even though the market
    # closed UP that day. The direction was right; the position count was the failure. Crypto pairs
    # are ~0.8+ correlated, so N simultaneous longs is not N bets — it is one bet sized N times.
    # sizing.TIERS already declared max_concurrent and nothing ever enforced it. It does now.
    room = _open_slots()
    if room <= 0:
        return {"scanned": 0, "errors": 0, "emitted": 0, "min_confidence": threshold,
                "signals": [], "blocked": "position cap reached — already at max concurrent risk"}

    for market, symbols in POPULAR.items():
        for symbol in symbols:
            for interval in SCAN_INTERVALS[market]:
                scanned += 1
                try:
                    sig = compute_signal(symbol, interval, market=market, with_news=False)
                except Exception:
                    errors += 1
                    continue
                if persistence.signal_exists(sig["symbol"], interval, sig["as_of"]):
                    continue  # already logged this bar (live or shadow)

                if sig["label"] not in _ACTIONABLE or sig["confidence"] < threshold:
                    continue  # silenced — the engine only logs setups it would actually trade
                if len(emitted) >= room:
                    break     # concurrency cap reached mid-sweep — stop adding correlated risk
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
