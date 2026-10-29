"""StarkX LAB: Strategy Registry & Factory.

Instantiates and configures strategies L1 to L10 based on pre-registered lab_spec.json.
"""

from __future__ import annotations

from typing import Dict, List, Type
from app.lab.models import Strategy
from app.lab.strategies.l1_trend_d1 import TrendD1Strategy
from app.lab.strategies.l2_donchian_4h import Donchian4HStrategy
from app.lab.strategies.l3_rsi2_pullback_1h import RSI2Pullback1HStrategy
from app.lab.strategies.l4_bb_fade_1h import BBFade1HStrategy
from app.lab.strategies.l5_squeeze_break_4h import SqueezeBreak4HStrategy
from app.lab.strategies.l6_xs_momentum_1d import XSMomentum1DStrategy
from app.lab.strategies.l7_funding_skew_4h import FundingSkew4HStrategy
from app.lab.strategies.l8_flush_fade_1h import FlushFade1HStrategy
from app.lab.strategies.l9_pairs_btceth_1d import PairsBTCETH1DStrategy
from app.lab.strategies.l10_carry_v2 import CarryV2Strategy

STRATEGY_CLASSES: Dict[str, Type] = {
    "trend_d1": TrendD1Strategy,
    "donchian_4h": Donchian4HStrategy,
    "rsi2_pullback_1h": RSI2Pullback1HStrategy,
    "bb_fade_1h": BBFade1HStrategy,
    "squeeze_break_4h": SqueezeBreak4HStrategy,
    "xs_momentum_1d": XSMomentum1DStrategy,
    "funding_skew_4h": FundingSkew4HStrategy,
    "flush_fade_1h": FlushFade1HStrategy,
    "pairs_btceth_1d": PairsBTCETH1DStrategy,
    "carry_v2": CarryV2Strategy,
}


def build_strategy(strategy_id: str, variant_id: str, params: dict | None = None) -> Strategy:
    """Factory helper to build a Strategy instance."""
    cls = STRATEGY_CLASSES.get(strategy_id)
    if cls is None:
        raise ValueError(f"Unknown strategy_id: {strategy_id}")
    return cls(variant_id=variant_id, params=params)


def list_registered_strategies() -> List[str]:
    """Returns list of registered strategy IDs."""
    return list(STRATEGY_CLASSES.keys())
