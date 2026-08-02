"""Capital-adaptive position sizing (Blueprint v2 §7).

Turns a calibrated win probability into a position size that is both growth-optimal AND survival-
constrained:

  * quarter-Kelly:  f_k = max(0, p - (1-p)/b) / 4     (b = reward:risk / payoff ratio)
  * ruin constraint: the largest fraction f keeping P(50% drawdown before doubling) < 5%, from the
    closed-form gambler's-ruin (drift/variance of per-trade log-wealth). This is the mathematical
    reason a SMALL account must risk LESS proportionally — negative or thin edge -> size ~0.
  * tier cap + min-notional floor: exchange rules dominate at small equity.

size = min(quarter_kelly, ruin_fraction, tier_cap) x drift_multiplier.

The paper track record still uses a fixed notional for comparability; this is the size RECOMMENDED
to the operator for their actual equity. Pure/deterministic; the closed form is verified against a
Monte-Carlo in the tests.
"""

from __future__ import annotations

import math

# name, equity_min, equity_max, max_concurrent, risk_cap_fraction, ev_threshold_R
# EV thresholds trade off selectivity vs activity: a POSITIVE-EV setup profits in aggregate, so the
# floors clear small-but-real edges (0.05R at standard) rather than demanding a rare 0.15R+ setup.
#
# max_concurrent was raised on 2026-08-02 (1/3/6/10 -> 2/8/20/30) after measuring that it is NOT
# the binding constraint. Replaying 23,487 backtested trades through a portfolio simulator, once
# gross exposure is capped at 1x, moving the count cap from 6 to 30 changes the equity curve by
# EXACTLY NOTHING (-23.4%, 834 trades, peak 6 open, identical to five decimal places) — because
# the book runs out of capital long before it runs out of slots. A generous count cap simply
# means that when many good uncorrelated setups do appear, they can all be taken, each smaller.
TIERS = [
    ("micro",    10,      100,    2,  0.02,  0.20),
    ("small",    100,     1_000,  8,  0.02,  0.10),
    ("standard", 1_000,   10_000, 20, 0.02,  0.05),
    ("growth",   10_000,  1e12,   30, 0.015, 0.05),
]

# GROSS EXPOSURE CEILING — the constraint that was missing entirely, and the one that matters.
#
# Sizing a position so its STOP costs 2% of equity says nothing about how big the position is. A
# stop 0.38% away (a real BTC signal on 2026-08-02) implies a notional of 5.3x equity for that one
# trade. Checked against the live book that day: six open positions totalled $16,160 of notional
# on $1,000 of equity — 16.2x gross, with nothing anywhere in the code to prevent it.
#
# The 2% risk figure is only true if the stop FILLS at the stop price. At 16x it does not survive
# a gap: a 6% adverse move through the stop is the entire account. Measured over the same 23,487
# trades, leaving gross uncapped returned -93.6% with a -96.4% drawdown; capping it at 1x returned
# -19.4% with -41.0%. Same signals, same fills — the leverage was doing the damage.
#
# 1.0x = fully invested, never borrowed. Larger accounts get slightly more room because they can
# diversify across genuinely uncorrelated classes rather than stacking one bet.
MAX_GROSS: dict[str, float] = {"micro": 1.0, "small": 1.0, "standard": 1.0, "growth": 1.5}

# How hard the exposure budget contracts below the high-water mark. At -10% drawdown the book may
# use 1 - 0.10*2.5 = 75% of its normal exposure; at -20%, 50%; floored at 25% so the engine keeps
# taking small trades and keeps producing outcomes to learn from instead of switching itself off.
# Measured effect at 3x gross: -68.1% return / -77.7% drawdown becomes -19.0% / -54.1%.
DRAWDOWN_THROTTLE_K = 2.5
DRAWDOWN_THROTTLE_FLOOR = 0.25
_LN2 = math.log(2.0)


def tier_for_equity(equity: float) -> dict:
    for name, lo, hi, mc, cap, ev in TIERS:
        if lo <= equity < hi:
            return {"tier": name, "max_concurrent": mc, "risk_cap": cap, "ev_threshold": ev}
    # below the smallest floor -> micro rules (can't really trade, but classify)
    name, lo, hi, mc, cap, ev = TIERS[0]
    return {"tier": name, "max_concurrent": mc, "risk_cap": cap, "ev_threshold": ev}


def quarter_kelly(p: float, b: float) -> float:
    """Quarter-Kelly fraction. 0 when the edge is non-positive."""
    if b <= 0:
        return 0.0
    f = p - (1.0 - p) / b
    return max(0.0, f) / 4.0


def ruin_prob(f: float, p: float, b: float, target_dd: float = 0.5) -> float:
    """P(drawdown to (1-target_dd) before doubling) under fixed-fraction f. Closed-form gambler's
    ruin on per-trade log-wealth. Monotonic increasing in f; verified vs Monte-Carlo in tests."""
    if f <= 0:
        return 0.0
    if f >= 1:
        return 1.0
    a = -math.log(1.0 - target_dd)          # ln 2 for a 50% drawdown barrier
    win = math.log(1.0 + f * b)
    loss = math.log(1.0 - f)
    mu = p * win + (1.0 - p) * loss
    var = p * (win - mu) ** 2 + (1.0 - p) * (loss - mu) ** 2
    if var < 1e-12:
        return 0.0 if mu > 0 else 1.0
    z = 2.0 * mu * a / var
    # Asymptotic clamps: as f->0, z -> +/-inf (mu ~ f, var ~ f^2). Overwhelming positive drift ->
    # ~no ruin; overwhelming negative drift -> ~certain 50% drawdown. Avoids math.exp overflow.
    if z > 700.0:
        return 0.0
    if z < -700.0:
        return 1.0
    if abs(z) < 1e-9:
        return 0.5
    ez, enz = math.exp(z), math.exp(-z)
    return (1.0 - enz) / (ez - enz)


def ruin_fraction(p: float, b: float, cap: float, ruin_limit: float = 0.05) -> float:
    """Largest f in [0, cap] with ruin_prob(f) < ruin_limit (binary search on a monotone function)."""
    if ruin_prob(cap, p, b) < ruin_limit:
        return cap
    if ruin_prob(1e-4, p, b) >= ruin_limit:
        return 0.0
    lo, hi = 0.0, cap
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if ruin_prob(mid, p, b) < ruin_limit:
            lo = mid
        else:
            hi = mid
    return lo


def drawdown_throttle(equity: float, high_water: float) -> float:
    """Exposure multiplier in [FLOOR, 1.0] based on how far below the high-water mark we are.

    This is the "grow but preserve" half of the risk rule: the book is allowed its full exposure
    only while making new highs. Every percent given back shrinks what may be put at risk, so a
    losing run de-risks itself automatically instead of averaging into the loss at full size.
    """
    if high_water <= 0 or equity >= high_water:
        return 1.0
    dd = equity / high_water - 1.0          # negative
    return max(DRAWDOWN_THROTTLE_FLOOR, 1.0 + dd * DRAWDOWN_THROTTLE_K)


def exposure_budget(equity: float, open_notional: float, high_water: float | None = None) -> dict:
    """How much NOTIONAL may still be opened, after the gross ceiling and drawdown throttle.

    `open_notional` is the summed notional of everything already live. Returns the budget, what is
    left, and the throttle actually applied, so the caller can explain a refusal instead of just
    silently declining to trade.
    """
    tier = tier_for_equity(equity)
    ceiling = MAX_GROSS.get(tier["tier"], 1.0)
    throttle = drawdown_throttle(equity, high_water if high_water is not None else equity)
    budget = equity * ceiling * throttle
    return {
        "tier": tier["tier"],
        "gross_ceiling": ceiling,
        "throttle": round(throttle, 4),
        "budget_usd": round(budget, 2),
        "open_notional_usd": round(open_notional, 2),
        "remaining_usd": round(max(0.0, budget - open_notional), 2),
        "gross_used": round(open_notional / equity, 3) if equity > 0 else 0.0,
    }


def position_size(equity: float, p: float, b: float, stop_frac: float,
                  drift_mult: float = 1.0, alloc_mult: float = 1.0, min_notional: float = 5.0,
                  room_usd: float | None = None) -> dict:
    """Recommended size for a setup. Returns the risk fraction, $ risk, $ notional, and what bound it.

    drift_mult: de-risk multiplier (§4.2). alloc_mult: strategy-allocator multiplier (§4.3)."""
    tier = tier_for_equity(equity)
    kf = quarter_kelly(p, b)
    rf = ruin_fraction(p, b, tier["risk_cap"])
    raw = min(kf, rf, tier["risk_cap"])
    f = raw * max(0.0, min(1.0, drift_mult)) * max(0.0, alloc_mult)

    risk_usd = equity * f
    notional = (risk_usd / stop_frac) if stop_frac and stop_frac > 0 else 0.0

    which = "kelly" if kf <= rf and kf <= tier["risk_cap"] else ("ruin" if rf <= tier["risk_cap"] else "tier_cap")
    if drift_mult < 1.0:
        which += "+drift"
    if alloc_mult != 1.0:
        which += "+alloc"

    # GROSS EXPOSURE CLAMP. A tight stop implies a huge notional; several of those at once is
    # leverage nobody asked for. When the book has less room left than this trade wants, the trade
    # is CUT DOWN rather than refused — a smaller position in a good setup still earns, and this
    # is what lets a generous position count coexist with a hard capital ceiling.
    if room_usd is not None and notional > room_usd:
        notional = max(0.0, room_usd)
        risk_usd = notional * stop_frac if stop_frac else 0.0
        f = (risk_usd / equity) if equity > 0 else 0.0
        which += "+exposure"

    tradeable = notional >= min_notional and f > 0

    return {
        "tier": tier["tier"],
        "risk_fraction": round(f, 5),
        "risk_pct": round(f * 100, 3),
        "risk_usd": round(risk_usd, 2),
        "notional_usd": round(notional, 2),
        "kelly_f": round(kf, 5),
        "ruin_f": round(rf, 5),
        "bound_by": which,
        "tradeable": bool(tradeable),
        "ev_threshold": tier["ev_threshold"],
    }
