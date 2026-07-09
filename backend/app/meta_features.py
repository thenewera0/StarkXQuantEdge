"""Meta-labeling feature vector (Blueprint v2 §5).

The confluence engine is the PRIMARY model (it decides direction). The meta-model is a SECONDARY
model that looks at a richer feature set and decides take/skip (and later, size). This module is the
single source of truth for that feature vector, used identically when training from history and when
scoring a live signal — so a stored `features` JSON replays through any future model version (§11).

Deliberately dependency-free and deterministic. Missing inputs map to 0.0 (the standardizer handles
scale), so forex rows without derivatives/on-chain still produce a valid vector.
"""

from __future__ import annotations

import math

FACTOR_KEYS = ("trend", "momentum", "volatility", "structure", "flow", "sentiment", "macro", "consensus")
REGIMES = ("strong_trend", "weak_trend", "range", "high_vol", "squeeze")

# Fixed, ordered feature layout. NEVER reorder — stored vectors index into this.
FEATURE_KEYS: list[str] = [
    "composite", "abs_composite", "agreement", "reward_risk", "atr_pct", "win_prob",
    "hour_sin", "hour_cos", "htf_trend", "is_long",
    *FACTOR_KEYS,
    *[f"regime_{r}" for r in REGIMES],
]


def _f(v) -> float:
    if v is None:
        return 0.0
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(x) else x


def build(raw: dict) -> list[float]:
    """Assemble the ordered feature vector from a raw dict of signal attributes.

    raw keys: composite, agreement, reward_risk, atr_pct, win_prob, hour_of_week (0..167),
              htf_trend (-1/0/1), is_long (bool), factors (dict of the 8), regime (str).
    """
    comp = _f(raw.get("composite"))
    how = raw.get("hour_of_week")
    hs = hc = 0.0
    if how is not None:
        ang = 2.0 * math.pi * (float(how) / 168.0)
        hs, hc = math.sin(ang), math.cos(ang)
    factors = raw.get("factors") or {}
    regime = raw.get("regime")

    vec = [
        comp, abs(comp), _f(raw.get("agreement")), _f(raw.get("reward_risk")),
        _f(raw.get("atr_pct")), _f(raw.get("win_prob")),
        hs, hc, _f(raw.get("htf_trend")), 1.0 if raw.get("is_long") else 0.0,
    ]
    vec += [_f(factors.get(k)) for k in FACTOR_KEYS]
    vec += [1.0 if regime == r else 0.0 for r in REGIMES]
    return vec
