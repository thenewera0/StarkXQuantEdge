"""Solana DEX <-> CEX arbitrage detector (Jupiter aggregator vs Binance).

Context, stated honestly: viral posts about turning $1 into six figures with Solana arb are not
credible — arbitrage profit is bounded by deployed capital, so a 400,000x return cannot come from
capturing small spreads (the screenshot behind that particular claim even says "SIMULATED").

What IS real: on-chain DEX prices genuinely drift from centralised order books, and Solana's fees
are low enough that the gap is sometimes worth taking. That is a legitimate strategy — it is simply
contested by professional MEV searchers with dedicated RPC nodes, Jito bundles and sub-100ms
latency. So we do what we do with every other arb type: DETECT it, cost it honestly, log how big
and how persistent the edge is, and let the evidence decide whether it is executable at our latency.

Cost model (why most "opportunities" are not opportunities):
    DEX side  : AMM pool fee (~0.25% typical) + price impact for the size + network/priority fee
    CEX side  : taker fee (~0.10%)
    -> round trip is roughly 0.35-0.5%, so a 0.1% quoted gap is a LOSS, not an edge.

Detection only — no wallet, no keys, no signing. Executing this would require a funded Solana
wallet and is a separate, deliberate decision.
"""

from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger("solana")

_JUP_PRICE = "https://lite-api.jup.ag/price/v3"
_BINANCE = "https://data-api.binance.vision/api/v3/ticker/bookTicker"

# Solana mints for liquid assets that also trade on Binance.
MINTS: dict[str, str] = {
    "SOL":  "So11111111111111111111111111111111111111112",
    "JUP":  "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JTO":  "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
    "WIF":  "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "RAY":  "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "W":    "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ",
}
# Binance symbol for each (USDT quoted).
CEX_SYMBOL = {k: f"{k}USDT" for k in MINTS}


def _jupiter_prices() -> dict[str, float]:
    """USD price per token from Jupiter's aggregated on-chain routing. {} on failure."""
    try:
        r = httpx.get(_JUP_PRICE, params={"ids": ",".join(MINTS.values())}, timeout=20.0)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}
    out: dict[str, float] = {}
    for name, mint in MINTS.items():
        node = data.get(mint) or {}
        px = node.get("usdPrice")
        if px:
            out[name] = float(px)
    return out


def _binance_books() -> dict[str, dict]:
    """Best bid/ask for the matching Binance spot pairs. {} on failure."""
    try:
        r = httpx.get(_BINANCE, timeout=20.0)
        r.raise_for_status()
        rows = r.json()
    except Exception:
        return {}
    want = set(CEX_SYMBOL.values())
    out: dict[str, dict] = {}
    for row in rows:
        if row.get("symbol") in want:
            try:
                bid, ask = float(row["bidPrice"]), float(row["askPrice"])
            except (KeyError, ValueError, TypeError):
                continue
            if bid > 0 and ask > 0:
                out[row["symbol"]] = {"bid": bid, "ask": ask}
    return out


_JUP_QUOTE = "https://lite-api.jup.ag/swap/v1/quote"


def verify_round_trip(mint_a: str, mint_b: str, amount: int,
                      dex_out: str | None = None, dex_back: str | None = None) -> dict | None:
    """EXECUTABLE test: swap A->B->A for a real size and report what actually comes back.

    THIS IS THE ONLY VALID PROOF OF AN ON-CHAIN ARB, and it exists because quoted price dispersion
    is NOT arbitrage. Measured live: individual Solana venues disagreed by 1.5% (SOL) and 15.8%
    (JUP), which looks like enormous free money. Round-tripping those exact venues returned
    -0.22%, -0.31%, -1.16% and -5.28%.

    The reason: a venue quotes 'cheap' precisely because it is thin for your size. The discount IS
    your price impact — you pay it the moment you trade there. Phoenix looked 1.5% cheap and cost
    5.28%. Any bot that treats a quoted spread as profit will lose money quickly, and a flash loan
    would simply lose it on borrowed principal.

    So: never act on a spread. Only ever act on a round trip that returns more than it consumed.
    """
    try:
        p1 = {"inputMint": mint_a, "outputMint": mint_b, "amount": int(amount), "slippageBps": 100}
        if dex_out:
            p1["dexes"] = dex_out
        r1 = httpx.get(_JUP_QUOTE, params=p1, timeout=20.0)
        r1.raise_for_status()
        mid = int(r1.json()["outAmount"])

        p2 = {"inputMint": mint_b, "outputMint": mint_a, "amount": mid, "slippageBps": 100}
        if dex_back:
            p2["dexes"] = dex_back
        r2 = httpx.get(_JUP_QUOTE, params=p2, timeout=20.0)
        r2.raise_for_status()
        back = int(r2.json()["outAmount"])
    except Exception:
        return None

    net = (back - amount) / amount
    # A flash loan must repay the FULL principal out of this number, plus its own fee and priority.
    total_cost = settings.solana_flash_fee + settings.solana_network_fee
    return {
        "size_in": amount, "size_out": back,
        "net_round_trip": round(net, 6),
        "flash_loan_cost": round(total_cost, 6),
        "net_after_flash_costs": round(net - total_cost, 6),
        "executable": bool(net - total_cost > settings.solana_buffer),
        "venues": {"out": dex_out or "aggregated", "back": dex_back or "aggregated"},
    }


def scan() -> dict:
    """Compare Solana DEX pricing against Binance and cost every gap honestly."""
    if not settings.solana_arb_enabled:
        return {"enabled": False, "opportunities": []}

    jup = _jupiter_prices()
    cex = _binance_books()
    if not jup or not cex:
        return {"enabled": True, "error": "price feed unavailable", "opportunities": []}

    dex_fee = settings.solana_dex_fee          # AMM pool fee
    cex_fee = settings.solana_cex_fee          # taker
    net_fee = settings.solana_network_fee      # gas/priority, as a fraction of a typical clip
    buffer = settings.solana_buffer

    opps: list[dict] = []
    for token, dex_px in jup.items():
        book = cex.get(CEX_SYMBOL[token])
        if not book:
            continue
        cex_bid, cex_ask = book["bid"], book["ask"]

        # Direction A: buy on DEX (pay dex_px), sell into the CEX bid.
        a = (cex_bid / dex_px) - 1.0
        # Direction B: buy on the CEX ask, sell on DEX.
        b = (dex_px / cex_ask) - 1.0
        gross, direction = (a, "buy DEX -> sell Binance") if a >= b else (b, "buy Binance -> sell DEX")

        cost = dex_fee + cex_fee + net_fee
        net = gross - cost
        opps.append({
            "token": token, "dex_price": round(dex_px, 6),
            "cex_bid": cex_bid, "cex_ask": cex_ask,
            "gross_spread": round(gross, 6), "cost": round(cost, 6),
            "net": round(net, 6), "direction": direction,
            "positive": bool(net > buffer),
        })

    opps.sort(key=lambda x: x["net"], reverse=True)
    positives = [o for o in opps if o["positive"]]
    for o in positives:
        logger.warning("SOLANA ARB %s net %+.3f%% (%s)", o["token"], o["net"] * 100, o["direction"])

    # --- dislocation view: the ONLY regime where flash-loan arb actually pays ---
    # In calm markets aggregators keep DEX pricing efficient (measured: best round trip +0.002%).
    # Spreads only blow out during stress — crashes, liquidation cascades, depegs. Flash loans
    # (Balancer/Morpho at 0% fee) make CAPITAL free, so during those windows the binding limit is
    # spread and priority fee, not how much money you have. This tracks how close we are.
    best = opps[0]["net"] if opps else None
    disloc = [o for o in opps if o["gross_spread"] >= settings.solana_dislocation_gross]
    state = ("DISLOCATED — spreads are wide enough to matter" if disloc
             else "efficient — aggregator pricing is tight, no flash-loan edge")
    if disloc:
        logger.warning("SOLANA DISLOCATION: %s", [(o["token"], round(o["gross_spread"] * 100, 3)) for o in disloc])

    return {
        "enabled": True, "scanned": len(opps), "positive": len(positives),
        "opportunities": opps,
        "cost_model": {"dex_fee": dex_fee, "cex_fee": cex_fee, "network": net_fee,
                       "round_trip": round(dex_fee + cex_fee + net_fee, 6)},
        "market_state": state,
        "dislocated": [o["token"] for o in disloc],
        "best_net": best,
        "flash_loan": {
            "capital_needed": "none — Balancer V2 and Morpho lend at 0% fee inside one transaction",
            "still_required": "a funded wallet for priority fees + a deployed contract; a flash "
                              "loan removes the capital constraint, never the cost or competition",
            "worth_attempting": bool(disloc and positives),
        },
        "note": ("detection only — execution needs a funded wallet and competes with MEV searchers "
                 "on dedicated RPC nodes"),
    }


def verify_round_trip_usd(token: str, usd: float = 1000.0) -> dict | None:
    """Convenience wrapper: round-trip USDC -> token -> USDC for a dollar clip."""
    mint = MINTS.get(token.upper())
    if not mint:
        return None
    usdc = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    out = verify_round_trip(usdc, mint, int(usd * 1_000_000))
    if out:
        out["token"] = token.upper()
        out["usd"] = usd
    return out
