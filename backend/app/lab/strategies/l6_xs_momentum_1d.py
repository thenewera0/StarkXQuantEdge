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

        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]
        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1])
        
        # Cross-sectional relative strength rankings and beta calculations
        rankings = ctx.extra_data.get("rankings", {})
        top_2_symbols = rankings.get("top_momentum", [])[:2]
        bot_2_symbols = rankings.get("bottom_weakest", rankings.get("bottom_reversal", []))[:2]
        beta_map = ctx.extra_data.get("beta_btc", {})

        signals = []
        is_top = ctx.symbol in top_2_symbols
        is_bot = ctx.symbol in bot_2_symbols

        if not rankings:
            # Fallback based on 30-day return skipping day 1
            ret_30d = (df["close"].iloc[-2] - df["close"].iloc[-p_lookback]) / df["close"].iloc[-p_lookback]
            if not self.is_reversal and ret_30d > 0.15:
                is_top = True
            elif self.is_reversal and ret_30d < -0.15:
                is_bot = True

        beta = float(beta_map.get(ctx.symbol, 1.0))

        if is_top:
            signals.append(Signal(
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
                meta={"beta_weight": beta, "factor_leg": "long_top", "net_btc_beta": 0.0, "atr": curr_atr},
            ))
        elif is_bot:
            signals.append(Signal(
                strategy_id=self.id,
                variant_id=f"{self.variant_id}_short" if "short" not in self.variant_id else self.variant_id,
                symbol=ctx.symbol,
                direction="short",
                bar_open_time=bar_open_time,
                entry_mode="next_open",
                stop_atr=float(self.params["stop_atr"]),
                target_r=None,
                trail_atr=3.5,
                max_hold_bars=int(self.params["max_hold_bars"]),
                meta={"beta_weight": beta, "factor_leg": "short_bottom", "net_btc_beta": 0.0, "atr": curr_atr},
            ))

        return signals
