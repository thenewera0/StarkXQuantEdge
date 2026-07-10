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

import math

from . import db
from .config import settings
from .data import fetch_book_tickers, fetch_funding_history

_PERIODS_PER_YEAR = 3 * 365  # 8h funding -> 3/day

# Curated currency set + the spot pairs among them (base, quote, binance_symbol) for the triangular
# cycle graph. A small hub-and-spoke graph keeps the Bellman-Ford cycles meaningful and fast.
_TRI_PAIRS = [
    ("BTC", "USDT", "BTCUSDT"), ("ETH", "USDT", "ETHUSDT"), ("BNB", "USDT", "BNBUSDT"),
    ("SOL", "USDT", "SOLUSDT"), ("XRP", "USDT", "XRPUSDT"), ("ADA", "USDT", "ADAUSDT"),
    ("ETH", "BTC", "ETHBTC"), ("BNB", "BTC", "BNBBTC"), ("SOL", "BTC", "SOLBTC"),
    ("XRP", "BTC", "XRPBTC"), ("ADA", "BTC", "ADABTC"),
    ("BNB", "ETH", "BNBETH"), ("SOL", "ETH", "SOLETH"), ("XRP", "ETH", "XRPETH"),
]


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
    _log_opportunities([o for o in opps if o["positive"]])
    return {
        "enabled": True,
        "scanned": len(syms),
        "positive": sum(1 for o in opps if o["positive"]),
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
    for base, quote, sym in _TRI_PAIRS:
        t = tickers.get(sym)
        if not t or t["bid"] <= 0 or t["ask"] <= 0:
            continue
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
    return {"enabled": True, "pairs": len(_TRI_PAIRS), "currencies": len(nodes), "opportunity": best}


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
