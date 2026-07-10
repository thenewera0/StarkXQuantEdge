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
TIERS = [
    ("micro",    10,      100,    1,  0.02,  0.5),
    ("small",    100,     1_000,  3,  0.02,  0.3),
    ("standard", 1_000,   10_000, 6,  0.02,  0.15),
    ("growth",   10_000,  1e12,   10, 0.015, 0.15),
]
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


def position_size(equity: float, p: float, b: float, stop_frac: float,
                  drift_mult: float = 1.0, alloc_mult: float = 1.0, min_notional: float = 5.0) -> dict:
    """Recommended size for a setup. Returns the risk fraction, $ risk, $ notional, and what bound it.

    drift_mult: de-risk multiplier (§4.2). alloc_mult: strategy-allocator multiplier (§4.3)."""
    tier = tier_for_equity(equity)
    kf = quarter_kelly(p, b)
    rf = ruin_fraction(p, b, tier["risk_cap"])
    raw = min(kf, rf, tier["risk_cap"])
    f = raw * max(0.0, min(1.0, drift_mult)) * max(0.0, alloc_mult)

    risk_usd = equity * f
    notional = (risk_usd / stop_frac) if stop_frac and stop_frac > 0 else 0.0
    tradeable = notional >= min_notional and f > 0

    which = "kelly" if kf <= rf and kf <= tier["risk_cap"] else ("ruin" if rf <= tier["risk_cap"] else "tier_cap")
    if drift_mult < 1.0:
        which += "+drift"
    if alloc_mult != 1.0:
        which += "+alloc"

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
