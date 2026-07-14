"""Funding-rate carry detector (Blueprint v2 §6.1) — the one arbitrage that works at retail.

Delta-neutral: long spot + short perpetual of the same asset in equal size. Price risk cancels; you
collect funding every 8h when funding is positive (shorts get paid). It is only worth doing when the
EXPECTED funding collected over the horizon exceeds the round-trip cost of both legs — so this is a
strict EV-after-cost gate, not a "funding is positive -> enter" rule.

Funding mean-reverts, so we forecast expected collection with an AR(1) model fit on the funding
history (same series the §2.5 z-score uses): E[f_{t+k}] = mu + phi^k (f_t - mu). Its half-life is
-ln2/ln(phi). Honest 2026 context: the cash-and-carry basis has compressed toward the risk-free
rate, so this is INTERMITTENT (shines during funding spikes in squeezes/panics), not a yield machine
— the detector will correctly report "no opportunity" most of the time.

Decision-support: this DETECTS and logs positive-EV carries; it does not place orders. Live position
tracking + allocator integration is a follow-up.
"""

from __future__ import annotations

import logging
import math

from . import db
from .config import settings
from .data import fetch_book_tickers, fetch_funding_history

logger = logging.getLogger("arb")
_PERIODS_PER_YEAR = 3 * 365  # 8h funding -> 3/day

# Currency universe for the triangular graph. The graph is built DYNAMICALLY from live book tickers
# by parsing every symbol into (base, quote) against this set — so it scans every cycle among these
# ~40 currencies, not a hand-picked pair list. Bases + quote/hub currencies together.
_ARB_QUOTES = ("FDUSD", "USDC", "USDT", "TUSD", "BTC", "ETH", "BNB")
_SORTED_QUOTES = tuple(sorted(_ARB_QUOTES, key=len, reverse=True))  # match longest suffix first
_ARB_UNIVERSE = frozenset({
    "USDT", "USDC", "FDUSD", "TUSD", "BTC", "ETH", "BNB",
    "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK", "LTC", "DOT", "TRX", "ATOM",
    "UNI", "NEAR", "APT", "ARB", "OP", "FIL", "INJ", "SUI", "SEI", "TIA", "ETC", "XLM",
    "ALGO", "VET", "ICP", "AAVE", "MKR", "RUNE", "GRT", "SAND", "FTM", "MATIC", "POL",
})


def _parse_pair(sym: str) -> tuple[str, str] | None:
    """Split a Binance symbol into (base, quote) against the universe. None if unrecognized."""
    for q in _SORTED_QUOTES:
        if sym.endswith(q) and len(sym) > len(q):
            base = sym[: -len(q)]
            if base in _ARB_UNIVERSE and q in _ARB_UNIVERSE:
                return base, q
    return None


def _ar1_params(hist: list[float]) -> tuple[float, float] | None:
    """(mu, phi) of an AR(1) fit on the funding series; None if too short/degenerate."""
    n = len(hist)
    if n < settings.arb_min_history:
        return None
    mu = sum(hist) / n
    x0 = [hist[i] - mu for i in range(n - 1)]
    x1 = [hist[i + 1] - mu for i in range(n - 1)]
    denom = sum(a * a for a in x0)
    if denom <= 1e-18:
        return mu, 0.0   # (near-)constant funding: no reversion info, forecast holds at the mean
    phi = sum(a * b for a, b in zip(x0, x1)) / denom
    return mu, max(-0.99, min(0.99, phi))


def _forecast_collection(current: float, mu: float, phi: float, horizon: int) -> float:
    """Expected total funding collected over the next `horizon` periods under the AR(1) forecast."""
    total, dev = 0.0, current - mu
    for k in range(1, horizon + 1):
        total += mu + (phi ** k) * dev
    return total


def funding_carry_opportunity(symbol: str) -> dict | None:
    """Evaluate the funding carry for one symbol. None if history is too thin to judge."""
    try:
        hist = fetch_funding_history(symbol, 200)
    except Exception:
        hist = []
    params = _ar1_params(hist)
    if params is None:
        return None
    mu, phi = params
    current = hist[-1]
    horizon = settings.arb_horizon_periods
    collection = _forecast_collection(current, mu, phi, horizon)

    cost = 2.0 * (settings.arb_spot_taker + settings.arb_perp_taker)  # entry + exit, both legs
    ev = collection - cost - settings.arb_buffer
    half_life = (-math.log(2.0) / math.log(phi)) if 0.0 < phi < 1.0 else None
    # Annualize from the mean forecast funding per period.
    annualized = (collection / horizon) * _PERIODS_PER_YEAR if horizon else 0.0

    return {
        "type": "funding_carry",
        "symbol": symbol.upper(),
        "current_funding": round(current, 8),
        "mean_funding": round(mu, 8),
        "phi": round(phi, 4),
        "half_life_periods": round(half_life, 2) if half_life else None,
        "horizon_periods": horizon,
        "expected_collection": round(collection, 6),
        "cost": round(cost, 6),
        "ev": round(ev, 6),
        "annualized_yield": round(annualized, 4),
        "positive": bool(ev > 0),
        "legs": f"long spot {symbol.upper()} + short perp {symbol.upper()} (delta-neutral)",
    }


def scan_funding_carry(symbols: list[str] | None = None) -> dict:
    """Evaluate every symbol; log the positive-EV opportunities. Never raises."""
    if not settings.arb_funding_enabled:
        return {"enabled": False, "opportunities": []}
    syms = symbols or list(settings.arb_symbols_list)
    opps = []
    for s in syms:
        try:
            o = funding_carry_opportunity(s)
        except Exception:
            o = None
        if o is not None:
            opps.append(o)
    opps.sort(key=lambda x: x["ev"], reverse=True)
    positives = [o for o in opps if o["positive"]]
    _log_opportunities(positives)
    for o in positives:
        logger.warning("ARB ALERT · funding carry %s EV %+.3f%% (annual %+.1f%%)",
                       o["symbol"], o["ev"] * 100, o["annualized_yield"] * 100)
    return {
        "enabled": True,
        "scanned": len(syms),
        "positive": len(positives),
        "opportunities": opps,
    }


def _log_opportunities(opps: list[dict]) -> None:
    if not opps or not db.enabled():
        return
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            for o in opps:
                cur.execute(
                    """insert into arb_opportunities
                       (type, symbol, expected_collection, cost, ev, annualized_yield,
                        half_life, horizon_periods, positive)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (o["type"], o["symbol"], o["expected_collection"], o["cost"], o["ev"],
                     o["annualized_yield"], o["half_life_periods"], o["horizon_periods"], o["positive"]),
                )
            conn.commit()
    except Exception:
        pass


# --- Triangular arbitrage (§6.2): Bellman-Ford negative-cycle detection ----

def _build_edges(tickers: dict[str, dict], fee: float):
    """Directed edges over currencies with weight = -log(rate * (1-fee)). A negative cycle == arb.

    For pair BASE/QUOTE: selling base gives `bid` quote (base->quote); buying base costs `ask`
    quote, i.e. 1 quote -> 1/ask base (quote->base). Fees apply on each conversion.
    """
    nodes: set[str] = set()
    edges: list[tuple[str, str, float]] = []
    rate: dict[tuple[str, str], float] = {}
    for sym, t in tickers.items():
        parsed = _parse_pair(sym)
        if parsed is None or t["bid"] <= 0 or t["ask"] <= 0:
            continue
        base, quote = parsed
        nodes.add(base); nodes.add(quote)
        r_bq = t["bid"] * (1 - fee)             # base -> quote
        r_qb = (1.0 / t["ask"]) * (1 - fee)     # quote -> base
        edges.append((base, quote, -math.log(r_bq))); rate[(base, quote)] = r_bq
        edges.append((quote, base, -math.log(r_qb))); rate[(quote, base)] = r_qb
    return list(nodes), edges, rate


def bellman_ford_neg_cycle(nodes: list[str], edges: list[tuple[str, str, float]]) -> list[str] | None:
    """Return one negative cycle (list of nodes, closed) or None. Classic Bellman-Ford."""
    if not nodes:
        return None
    dist = {n: 0.0 for n in nodes}      # 0-init detects any negative cycle in the graph
    pred: dict[str, str | None] = {n: None for n in nodes}
    x = None
    for _ in range(len(nodes)):
        x = None
        for u, v, w in edges:
            if dist[u] + w < dist[v] - 1e-12:
                dist[v] = dist[u] + w
                pred[v] = u
                x = v
    if x is None:
        return None
    for _ in range(len(nodes)):          # step into the cycle
        x = pred[x]
    cycle = [x]
    v = pred[x]
    while v != x and v is not None:
        cycle.append(v)
        v = pred[v]
    cycle.append(x)
    cycle.reverse()
    return cycle


def _cycle_net(cycle: list[str], rate: dict[tuple[str, str], float]) -> float | None:
    """Net profit fraction around a cycle (product of rates - 1), or None if an edge is missing."""
    prod = 1.0
    for a, b in zip(cycle, cycle[1:]):
        r = rate.get((a, b))
        if r is None:
            return None
        prod *= r
    return prod - 1.0


def triangular_scan() -> dict:
    """Scan for a profitable triangular cycle after fees (paper-mode detection, §6.2)."""
    if not settings.arb_triangular_enabled:
        return {"enabled": False, "opportunity": None}
    try:
        tickers = fetch_book_tickers()
    except Exception:
        return {"enabled": True, "error": "ticker fetch failed", "opportunity": None}

    fee = settings.arb_tri_fee
    nodes, edges, rate = _build_edges(tickers, fee)
    cycle = bellman_ford_neg_cycle(nodes, edges)
    best = None
    if cycle:
        net = _cycle_net(cycle, rate)
        if net is not None:
            best = {
                "type": "triangular", "cycle": cycle, "path": " -> ".join(cycle),
                "net": round(net, 6), "fee": fee, "buffer": settings.arb_tri_buffer,
                "positive": bool(net > settings.arb_tri_buffer),
                "legs": len(cycle) - 1,
            }
            if best["positive"]:
                _log_triangular(best)
                logger.warning("ARB ALERT · triangular %s net %+.3f%%", best["path"], best["net"] * 100)
    return {"enabled": True, "pairs": len(edges) // 2, "currencies": len(nodes), "opportunity": best}


def _log_triangular(o: dict) -> None:
    if not db.enabled():
        return
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """insert into arb_opportunities (type, symbol, ev, positive)
                   values (%s,%s,%s,%s)""",
                (o["type"], o["path"], o["net"], o["positive"]),
            )
            conn.commit()
    except Exception:
        pass


# --- Cross-exchange inventory arbitrage (§6.3) -----------------------------

def cross_exchange_opportunity(symbol: str, a: dict, b: dict, fee_a: float, fee_b: float) -> dict:
    """Best simultaneous cross-venue trade for a symbol held on both venues (no transfer).

    Direction 1: buy on B (ask_b), sell on A (bid_a) -> net = bid_a/ask_b*(1-fee_a)(1-fee_b) - 1.
    Direction 2: buy on A (ask_a), sell on B (bid_b). Report the better of the two."""
    d1 = (a["bid"] / b["ask"]) * (1 - fee_a) * (1 - fee_b) - 1.0   # buy Bybit, sell Binance
    d2 = (b["bid"] / a["ask"]) * (1 - fee_a) * (1 - fee_b) - 1.0   # buy Binance, sell Bybit
    if d1 >= d2:
        net, direction = d1, "buy Bybit -> sell Binance"
    else:
        net, direction = d2, "buy Binance -> sell Bybit"
    return {
        "type": "cross_exchange", "symbol": symbol.upper(), "direction": direction,
        "net": round(net, 6), "binance": {"bid": a["bid"], "ask": a["ask"]},
        "bybit": {"bid": b["bid"], "ask": b["ask"]},
    }


def cross_exchange_scan(symbols: list[str] | None = None) -> dict:
    """Scan symbols held on Binance + Bybit for a profitable simultaneous cross-venue trade (§6.3).

    Requires pre-positioned inventory on both venues -> unlocks at the Growth capital tier."""
    if not settings.arb_cross_enabled:
        return {"enabled": False, "opportunities": []}
    try:
        bin_t = fetch_book_tickers()
    except Exception:
        return {"enabled": True, "error": "binance tickers failed", "opportunities": []}
    try:
        from .data.bybit import fetch_book_tickers as _byb
        byb_t = _byb()
    except Exception:
        return {"enabled": True, "error": "bybit tickers failed", "opportunities": []}

    syms = symbols or list(settings.arb_symbols_list)
    buf = settings.arb_cross_buffer
    opps = []
    for s in syms:
        a, b = bin_t.get(s), byb_t.get(s)
        if not a or not b:
            continue
        o = cross_exchange_opportunity(s, a, b, settings.arb_cross_fee_binance, settings.arb_cross_fee_bybit)
        o["positive"] = bool(o["net"] > buf)
        opps.append(o)
    opps.sort(key=lambda x: x["net"], reverse=True)
    positives = [o for o in opps if o["positive"]]
    _log_cross(positives)
    for o in positives:
        logger.warning("ARB ALERT · cross-exchange %s net %+.3f%% (%s)", o["symbol"], o["net"] * 100, o["direction"])
    return {
        "enabled": True, "scanned": len(opps),
        "positive": len(positives),
        "opportunities": opps,
        "note": "requires pre-positioned inventory on both venues (Growth tier)",
    }


def _log_cross(opps: list[dict]) -> None:
    if not opps or not db.enabled():
        return
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            for o in opps:
                cur.execute(
                    "insert into arb_opportunities (type, symbol, ev, positive) values (%s,%s,%s,%s)",
                    (o["type"], f"{o['symbol']} ({o['direction']})", o["net"], o["positive"]),
                )
            conn.commit()
    except Exception:
        pass


def active_alerts(hours: int = 12) -> list[dict]:
    """Positive-EV arb opportunities caught in the last `hours` — the alert feed for the dashboard."""
    if not db.enabled():
        return []
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""select ts, type, symbol, ev, annualized_yield
                    from arb_opportunities
                    where positive = true and ts > now() - interval '{int(hours)} hours'
                    order by ts desc limit 20"""
            )
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return []


def recent_opportunities(limit: int = 20) -> list[dict]:
    if not db.enabled():
        return []
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """select ts, type, symbol, expected_collection, cost, ev, annualized_yield,
                          half_life, horizon_periods
                   from arb_opportunities order by ts desc limit %s""",
                (limit,),
            )
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return []
