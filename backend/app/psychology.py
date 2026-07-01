"""Layer 4 — Positioning & Psychology engine (the differentiator).

Markets move by trapping the crowd. This BOOSTS conviction when the crowd is provably offside
(fade fuel) and VETOES the trade when you'd be joining a crowded, exhausted move (exit liquidity).

Output: a modifier in [-30, +30] (same scale as the -100..100 composite; + = more bullish) plus a
boolean crowd_veto and a human-readable note for the thesis.
"""

from __future__ import annotations

_FUNDING_HOT = 0.0002      # per-interval funding considered crowded
_FUNDING_EXTREME = 0.0004
_FEAR = 25
_GREED = 75
_VWAP_STRETCH = 0.03       # 3% from VWAP = extended


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def positioning_engine(
    direction: int, extras: dict | None, fng_value: int | None, vwap_dist: float | None
) -> tuple[float, bool, str]:
    """direction: +1 long candidate, -1 short candidate, 0 none."""
    extras = extras or {}
    funding = extras.get("funding_rate")
    modifier = 0.0
    veto = False
    notes: list[str] = []

    if direction > 0:  # long candidate
        if funding is not None and funding < -_FUNDING_HOT:
            modifier += 15
            notes.append(f"shorts trapped (funding {funding:+.3%})")
        if fng_value is not None and fng_value < _FEAR:
            modifier += 12
            notes.append(f"extreme fear (F&G {fng_value})")
        if (
            funding is not None and funding > _FUNDING_EXTREME
            and fng_value is not None and fng_value > _GREED
            and vwap_dist is not None and vwap_dist > _VWAP_STRETCH
        ):
            veto = True
            notes.append("crowded long, price extended above VWAP — would be exit liquidity")

    elif direction < 0:  # short candidate
        if funding is not None and funding > _FUNDING_HOT:
            modifier -= 15
            notes.append(f"longs trapped (funding {funding:+.3%})")
        if fng_value is not None and fng_value > _GREED:
            modifier -= 12
            notes.append(f"extreme greed (F&G {fng_value})")
        if (
            funding is not None and funding < -_FUNDING_EXTREME
            and fng_value is not None and fng_value < _FEAR
            and vwap_dist is not None and vwap_dist < -_VWAP_STRETCH
        ):
            veto = True
            notes.append("capitulation bottom, price extended below VWAP — fading risk")

    return _clamp(modifier, -30.0, 30.0), veto, "; ".join(notes) or "no crowd extreme"
