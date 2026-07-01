"""Fixed, hand-tuned category weights per timeframe bucket.

PLAN.md decision: NO adaptive/learned weights until an outcome table has real volume.
Intraday leans Trend/Momentum/Flow; long-term leans Macro/Structure. Each profile sums to 1.0.

Categories: trend, momentum, volatility, structure, flow, sentiment, macro, consensus.
"""

from __future__ import annotations

CATEGORIES = ("trend", "momentum", "volatility", "structure", "flow", "sentiment", "macro", "consensus")

_PROFILES: dict[str, dict[str, float]] = {
    "intraday": {
        "trend": 0.22, "momentum": 0.22, "volatility": 0.10, "structure": 0.12,
        "flow": 0.18, "sentiment": 0.04, "macro": 0.04, "consensus": 0.08,
    },
    "short": {
        "trend": 0.22, "momentum": 0.18, "volatility": 0.08, "structure": 0.14,
        "flow": 0.14, "sentiment": 0.06, "macro": 0.08, "consensus": 0.10,
    },
    "swing": {
        "trend": 0.18, "momentum": 0.14, "volatility": 0.08, "structure": 0.16,
        "flow": 0.10, "sentiment": 0.08, "macro": 0.16, "consensus": 0.10,
    },
    "long": {
        "trend": 0.14, "momentum": 0.10, "volatility": 0.06, "structure": 0.18,
        "flow": 0.06, "sentiment": 0.10, "macro": 0.26, "consensus": 0.10,
    },
}

# Map a Binance kline interval to a timeframe bucket.
_INTERVAL_BUCKET = {
    "1m": "intraday", "3m": "intraday", "5m": "intraday", "15m": "intraday", "30m": "intraday",
    "1h": "short", "2h": "short", "4h": "short",
    "6h": "swing", "8h": "swing", "12h": "swing", "1d": "swing",
    "3d": "long", "1w": "long",
}


def timeframe_bucket(interval: str) -> str:
    return _INTERVAL_BUCKET.get(interval, "short")


def weights_for_interval(interval: str) -> dict[str, float]:
    return dict(_PROFILES[timeframe_bucket(interval)])


# Regime-conditional weights (Confluence Engine L3). Category -> spec family mapping:
#   trend=F1, momentum=F2, volatility=F4 (vol/liq), structure=F3 (mean-rev/exhaustion),
#   flow=F5 (derivatives), sentiment=F7, macro=F8, consensus=F6 (on-chain). Each sums to 1.0.
_REGIME_PROFILES: dict[str, dict[str, float]] = {
    "strong_trend": {"trend": 0.22, "momentum": 0.18, "volatility": 0.10, "structure": 0.05,
                     "flow": 0.18, "sentiment": 0.07, "macro": 0.08, "consensus": 0.12},
    "weak_trend":   {"trend": 0.16, "momentum": 0.16, "volatility": 0.10, "structure": 0.12,
                     "flow": 0.16, "sentiment": 0.08, "macro": 0.10, "consensus": 0.12},
    "range":        {"trend": 0.05, "momentum": 0.08, "volatility": 0.12, "structure": 0.25,
                     "flow": 0.15, "sentiment": 0.12, "macro": 0.08, "consensus": 0.15},
    "high_vol":     {"trend": 0.10, "momentum": 0.10, "volatility": 0.20, "structure": 0.10,
                     "flow": 0.20, "sentiment": 0.10, "macro": 0.10, "consensus": 0.10},
    "squeeze":      {"trend": 0.10, "momentum": 0.12, "volatility": 0.22, "structure": 0.10,
                     "flow": 0.20, "sentiment": 0.08, "macro": 0.08, "consensus": 0.10},
}


def regime_base_weights(regime: str | None) -> dict[str, float] | None:
    """Base weight profile for a regime, or None if unknown (caller falls back to timeframe)."""
    if regime and regime in _REGIME_PROFILES:
        return dict(_REGIME_PROFILES[regime])
    return None
