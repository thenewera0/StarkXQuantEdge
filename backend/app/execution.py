"""Order execution model — how an entry actually reaches the market, and what it costs.

Measured 2026-08-07: on the core crypto long book, maker execution is worth +0.34 percentage
points per trade (+1.5135% -> +1.8535%) purely from not crossing the spread. Taker cost is
0.16-0.28% per round trip; a resting limit order pays ~0.04%.

That saving is NOT free, and this module exists to price the catch honestly.

    A limit order only fills if price comes to it.

Two consequences, both real money:

  MISSED TRADES     A buy limit resting below the close fills only when price dips. Setups that
                    run away immediately are never entered at all. Those are disproportionately
                    the winners, so the fills you DO get are adversely selected. Any model that
                    ignores this is fantasy.

  BETTER BASIS      When it does fill, it fills BELOW the close, which improves the entry by the
                    offset. This partly compensates for what was missed.

The right metric is therefore P&L PER SIGNAL, not per fill: an unfilled order contributes zero,
and the comparison against market execution has to carry that zero. `simulate_limit_entry` returns
exactly that so the trade-off can be measured instead of argued about.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import settings


@dataclass(frozen=True)
class LimitPlan:
    """Where the resting order sits, how long it waits, and what it costs if it fills."""
    limit_price: float
    offset_frac: float      # how far below (long) / above (short) the signal price, as a fraction
    expiry_bars: int        # cancel if unfilled after this many bars
    execution: str          # "maker" while resting; a cancelled order costs nothing


def limit_entry(price: float, atr: float, direction: str,
                offset_atr: float | None = None,
                expiry_bars: int | None = None) -> LimitPlan:
    """Where to rest a maker entry for a signal at `price`.

    The offset is measured in ATR so it scales with the instrument's own volatility: a fixed
    percentage would be trivially filled on a volatile alt and never filled on a quiet major.

    A LARGER offset means a better fill and a cheaper basis, but a lower fill rate — that is the
    whole trade-off, and `scripts.research_limit_orders` measures where it optimises rather than
    guessing. Do not tune this from intuition.
    """
    off = settings.limit_offset_atr if offset_atr is None else offset_atr
    exp = settings.limit_expiry_bars if expiry_bars is None else expiry_bars
    dist = max(0.0, off) * max(atr, 0.0)
    limit = price - dist if direction == "long" else price + dist
    return LimitPlan(
        limit_price=round(limit, 10),
        offset_frac=round(dist / price, 8) if price else 0.0,
        expiry_bars=int(exp),
        execution="maker",
    )


def tick_size(price: float) -> float:
    """Estimated minimum price variation (tick) for exchange matching engines."""
    p = abs(float(price or 1.0))
    if p >= 10000:
        return 0.1
    elif p >= 1000:
        return 0.01
    elif p >= 100:
        return 0.01
    elif p >= 10:
        return 0.001
    elif p >= 1:
        return 0.0001
    elif p >= 0.1:
        return 0.00001
    else:
        return 0.000001


def fill_bar(
    highs, lows, start: int, plan: LimitPlan, direction: str, n: int,
    tick: float | None = None,
) -> int | None:
    """Index of the bar where the resting order fills, or None if it expires unfilled.

    Institutional execution rule (Phase 0.3):
    A resting limit order fills ONLY if a later candle's low (long) / high (short)
    trades THROUGH the limit by >= 1 tick, and never on the signal candle (start).
    """
    t = tick if tick is not None else tick_size(plan.limit_price)
    last = min(start + 1 + plan.expiry_bars, n)
    for j in range(start + 1, last):
        if direction == "long":
            # Buy limit requires low to trade through by at least 1 tick
            if lows[j] <= (plan.limit_price - t):
                return j
        elif highs[j] >= (plan.limit_price + t):
            # Sell limit requires high to trade through by at least 1 tick
            return j
    return None

