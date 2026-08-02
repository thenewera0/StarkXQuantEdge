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

# WHAT THE SCANNER SWEEPS, and why it is no longer crypto-only.
#
# The old comment here said "focus > breadth" and swept 28 crypto pairs. That reasoning was half
# right and half backwards. It was right that forex showed no edge across ~190 trades. It was
# backwards about concentration: on 2026-07-28 the engine opened 18 correlated crypto longs and a
# single ~1.6% BTC dip stopped out every one of them on a day the market closed UP. Sweeping only
# crypto means the concurrency cap can only ever be filled with the SAME BET repeated.
#
# Breadth across asset classes is the fix, because it is the only way the cap's slots get filled
# with genuinely independent risk. Gold, the Nikkei, wheat and the 30-year bond do not all gap
# down when Bitcoin does. Every existing gate still applies unchanged — regime, direction,
# segment-conditioned calibration, drift, and the concurrency cap — so a class that cannot earn
# its keep gets priced out by its own realised record rather than by a hand-written exclusion.
#
# Forex is back in on the G10 crosses ONLY, and deliberately on probation: its losing record was
# measured while calibration pooled every segment into one curve (the bug that priced 70%-win
# crypto longs at 7-20% and froze the engine for weeks). Calibration is now conditioned on
# (market, direction, regime), so forex is priced on forex's own history. If it is still bad, the
# segment curve will say so and size it to nothing — which is the system working.
_SCAN_CATEGORIES = ("commodities", "indices", "rates", "forex")


def scan_universe() -> dict[str, list[str]]:
    """market -> symbols, resolved live so new listings appear without a code change."""
    from . import universe
    out: dict[str, list[str]] = {}
    # Crypto: the deep end of the book only. A 15m-to-4h trade pays the spread against a small
    # move, so thin pairs are unwinnable regardless of signal quality.
    out["crypto"] = [c["symbol"] for c in universe.catalog(
        ["crypto"], crypto_limit=60, min_volume=universe.MIN_VOLUME_SCAN)]
    for cat in _SCAN_CATEGORIES:
        syms = [c["symbol"] for c in universe.catalog([cat], allocatable_only=True)]
        if cat == "forex":
            syms = [s for s in syms if s in _FX_PROBATION]
        if syms:
            out[cat] = syms
    return out


# G10 majors + the most liquid crosses. Outside these, FX spot momentum is a carry illusion
# (see universe._fx_allocatable) and the spread widens far past what a 4h move can pay for.
_FX_PROBATION = frozenset({
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD",
    "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY", "EUR/CHF", "EUR/AUD", "CAD/JPY", "CHF/JPY",
})

# Kept as the static fallback for tests and for when the venue/catalog is unreachable.
POPULAR: dict[str, list[str]] = {
    "crypto": [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
        "LINKUSDT", "LTCUSDT", "DOTUSDT", "TRXUSDT", "ATOMUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT",
        "ARBUSDT", "OPUSDT", "FILUSDT", "INJUSDT", "SUIUSDT", "SEIUSDT", "TIAUSDT", "AAVEUSDT",
        "ETCUSDT", "XLMUSDT", "RUNEUSDT", "GRTUSDT",
    ],
}
# Crypto runs 24/7 so 1h is tradable; the rest close overnight and at weekends, where an hourly
# bar spans a session gap and the "move" is just the reopen. Those trade on 4h and daily only.
SCAN_INTERVALS: dict[str, list[str]] = {
    "crypto": ["1h", "4h"],
    "commodities": ["4h", "1d"],
    "indices": ["4h", "1d"],
    "rates": ["4h", "1d"],
    "forex": ["4h", "1d"],
}

_ACTIONABLE = {"Buy", "Strong Buy", "Sell", "Strong Sell"}


def _open_slots() -> tuple[int, dict[str, int]]:
    """(total slots left, open count per market) under the tier's concurrency cap.

    Counts live (non-paper) positions that have not yet resolved. Returns a large number when
    persistence is off so local/backtest use is unaffected.
    """
    from . import db, sizing
    if not db.enabled():
        return 99, {}
    cap = sizing.tier_for_equity(settings.account_equity_usd)["max_concurrent"]
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """select coalesce(s.market, 'crypto'), count(*) from signals s
                   where not s.shadow and s.entry is not null and s.label <> 'Neutral'
                     and not exists (select 1 from outcomes o where o.signal_id = s.id)
                   group by 1"""
            )
            per_market = {str(m): int(n) for m, n in cur.fetchall()}
    except Exception:
        return 0, {}  # cannot verify exposure -> do not add risk
    return max(0, cap - sum(per_market.values())), per_market


def _class_cap() -> int:
    """Most positions any ONE asset class may hold at once.

    The global cap limits total risk. This limits CORRELATED risk, which is the thing that
    actually hurt: on 2026-07-28 eighteen crypto longs went on together and one ~1.6% BTC dip
    stopped out every one of them. Checked again on 2026-08-02, all six available slots had
    gone to crypto longs opened within the same two hours — the same shape, just capped smaller.
    Holding a class to half the book forces the rest of the slots onto instruments that do not
    share a driver. This REALLOCATES risk rather than adding any: the global cap is untouched.
    """
    from . import sizing
    cap = sizing.tier_for_equity(settings.account_equity_usd)["max_concurrent"]
    return max(1, (cap + 1) // 2)


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
    room, open_by_market = _open_slots()
    class_cap = _class_cap()
    if room <= 0:
        return {"scanned": 0, "errors": 0, "emitted": 0, "min_confidence": threshold,
                "signals": [], "open_by_market": open_by_market,
                "blocked": "position cap reached — already at max concurrent risk"}

    try:
        sweep = scan_universe()
    except Exception:
        sweep = POPULAR          # catalog unreachable — fall back to the proven core

    # ROUND-ROBIN the asset classes instead of finishing one before starting the next. The sweep
    # halts the moment the concurrency cap fills, so scanning class-by-class would hand every slot
    # to crypto again and rebuild the exact correlation risk that breadth is here to fix. Taking
    # one symbol from each class in turn means the cap gets spent on independent bets.
    queues = [list(syms) for syms in sweep.values() if syms]
    markets = [m for m, syms in sweep.items() if syms]
    ordered: list[tuple[str, str]] = []
    for depth in range(max((len(q) for q in queues), default=0)):
        for market, queue in zip(markets, queues):
            if depth < len(queue):
                ordered.append((market, queue[depth]))

    by_market: dict[str, int] = {}
    held: dict[str, int] = dict(open_by_market)   # already-open positions count against the class cap
    for market, symbol in ordered:
        if len(emitted) >= room:
            break             # cap reached — stop adding risk, whatever is left unscanned
        if held.get(market, 0) >= class_cap:
            continue          # this class is full; its remaining slots belong to other drivers
        for interval in SCAN_INTERVALS.get(market, ["4h"]):
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
            if held.get(market, 0) >= class_cap:
                break     # per-class cap — leave the rest of the book for uncorrelated drivers
            sid = persistence.log_decision(sig)
            lv = sig["levels"]
            by_market[market] = by_market.get(market, 0) + 1
            held[market] = held.get(market, 0) + 1
            emitted.append({
                "id": sid, "symbol": sig["symbol"], "market": market, "interval": interval,
                "label": sig["label"], "confidence": sig["confidence"], "regime": sig.get("regime"),
                "entry": lv["entry"], "stop": lv["stop"], "target": lv["target"],
            })

    return {
        "scanned": scanned, "errors": errors, "emitted": len(emitted),
        "min_confidence": threshold, "signals": emitted,
        "universe": {m: len(s) for m, s in sweep.items()},
        "emitted_by_market": by_market,
        "open_by_market": held,
        "class_cap": class_cap,
    }
