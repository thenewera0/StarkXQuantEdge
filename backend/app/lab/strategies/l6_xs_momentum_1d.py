"""L6 Cross-Sectional Momentum 1d Strategy (xs_momentum_1d).

Specification:
Rank top 30 by 30-day return skipping the last day; hold the top 3 equal-risk; weekly rebalance; long only;
Reversal variant (xs_reversal_1d): bottom 3 by 3-day return.
"""

from __future__ import annotations

from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr


class XSMomentum1DStrategy:
    id: str = "xs_momentum_1d"
    timeframe: Literal["1h", "4h", "1d"] = "1d"

    def __init__(self, variant_id: str = "xs_momentum_1d_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "lookback_days": 30,
            "skip_days": 1,
            "top_n": 3,
            "rebalance_days": 7,
            "stop_atr": 3.0,
            "max_hold_bars": 14,
        }
        self.params = {**defaults, **(params or {})}
        self.is_reversal = "reversal" in variant_id.lower()

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_lookback = int(self.params["lookback_days"])
        if len(df) < p_lookback + 5:
            return []

        # Check if weekly rebalance trigger or daily check
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]
        
        # Check cross-sectional rank if available in extra_data
        rankings = ctx.extra_data.get("rankings", {})
        is_selected = False

        if rankings:
            if not self.is_reversal:
                # Top N by 30-day return (skip 1 day)
                top_symbols = rankings.get("top_momentum", [])[:int(self.params["top_n"])]
                is_selected = ctx.symbol in top_symbols
            else:
                # Bottom N by 3-day return (reversal)
                bot_symbols = rankings.get("bottom_reversal", [])[:int(self.params["top_n"])]
                is_selected = ctx.symbol in bot_symbols
        else:
            # Fallback to standalone relative return threshold if cross-sectional table not pre-computed
            if not self.is_reversal:
                ret_30d_skip1 = (df["close"].iloc[-2] - df["close"].iloc[-p_lookback]) / df["close"].iloc[-p_lookback]
                is_selected = ret_30d_skip1 > 0.15 and df["close"].iloc[-1] > df["close"].iloc[-20]
            else:
                ret_3d = (df["close"].iloc[-1] - df["close"].iloc[-4]) / df["close"].iloc[-4]
                is_selected = ret_3d < -0.08

        if is_selected:
            atr = calc_atr(df, 14)
            curr_atr = float(atr.iloc[-1])
            return [Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="long",
                bar_open_time=bar_open_time,
                entry_mode="next_open",
                stop_atr=float(self.params["stop_atr"]),
                target_r=None,
                trail_atr=3.5,
                max_hold_bars=int(self.params["max_hold_bars"]),
                meta={"is_reversal": self.is_reversal, "atr": curr_atr},
            )]

        return []
