"""L1 Trend Daily Strategy (trend_d1).

Replicates v2 Sleeve T Trend signal on 1-day closed bars.
"""

from __future__ import annotations

from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_ema, calc_sma


class TrendD1Strategy:
    id: str = "trend_d1"
    timeframe: Literal["1h", "4h", "1d"] = "1d"

    def __init__(self, variant_id: str = "trend_d1_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "fast_ema": 21,
            "slow_ema": 55,
            "stop_atr": 2.0,
            "trail_atr": 2.5,
            "max_hold_bars": 60,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        if len(df) < max(self.params["slow_ema"], 60) + 5:
            return []

        fast = calc_ema(df["close"], int(self.params["fast_ema"]))
        slow = calc_ema(df["close"], int(self.params["slow_ema"]))
        atr = calc_atr(df, 14)

        prev_fast = fast.iloc[-2]
        prev_slow = slow.iloc[-2]
        curr_fast = fast.iloc[-1]
        curr_slow = slow.iloc[-1]
        curr_atr = float(atr.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # Bullish trend alignment or crossover
        if (curr_fast > curr_slow and curr_close > curr_fast) and (prev_fast <= prev_slow or curr_close > df["high"].iloc[-20:-1].max()):
            sig = Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="long",
                bar_open_time=bar_open_time,
                entry_mode="next_open",
                stop_atr=float(self.params["stop_atr"]),
                target_r=None,
                trail_atr=float(self.params["trail_atr"]),
                max_hold_bars=int(self.params["max_hold_bars"]),
                meta={"atr": curr_atr, "fast_ema": curr_fast, "slow_ema": curr_slow},
            )
            return [sig]

        return []
