"""L2 Donchian Breakout 4h Strategy (donchian_4h).

Specification:
Long when close > highest high of 55 bars; exit when close < lowest low of 20 bars or stop 2.5 ATR.
Mirrored short variant: short when close < lowest low of 55 bars; exit when close > highest high of 20 bars or stop 2.5 ATR.
"""

from __future__ import annotations

from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr


class Donchian4HStrategy:
    id: str = "donchian_4h"
    timeframe: Literal["1h", "4h", "1d"] = "4h"

    def __init__(self, variant_id: str = "donchian_4h_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "entry_period": 55,
            "exit_period": 20,
            "stop_atr": 2.5,
            "trail_atr": 3.0,
            "max_hold_bars": 60,
        }
        self.params = {**defaults, **(params or {})}
        self.is_short_variant = "short" in variant_id.lower()

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_entry = int(self.params["entry_period"])
        p_exit = int(self.params["exit_period"])
        if len(df) < p_entry + 5:
            return []

        # Volatility Squeeze Pre-Condition (Phase 4): bbw_pct_rank < 0.25
        from app.lab.strategies.base import calc_bbw_pct_rank
        bbw_rank = calc_bbw_pct_rank(df["close"], window=20, lookback=100)
        if bbw_rank >= 0.25:
            return []  # Do not enter when volatility is already blown out / exhausted

        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # Breakout over previous p_entry bars (excluding current bar)
        highest_high = float(df["high"].iloc[-p_entry-1:-1].max())
        lowest_low = float(df["low"].iloc[-p_entry-1:-1].min())

        signals = []
        if not self.is_short_variant and curr_close > highest_high:
            signals.append(Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="long",
                bar_open_time=bar_open_time,
                entry_mode="maker",
                stop_atr=float(self.params["stop_atr"]),
                target_r=None,
                trail_atr=float(self.params["trail_atr"]),
                max_hold_bars=int(self.params["max_hold_bars"]),
                meta={
                    "highest_high": highest_high,
                    "atr": curr_atr,
                    "exit_period": p_exit,
                    "maker_offset_atr": 0.35,
                    "bbw_rank": bbw_rank,
                },
            ))
        elif self.is_short_variant and curr_close < lowest_low:
            signals.append(Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="short",
                bar_open_time=bar_open_time,
                entry_mode="maker",
                stop_atr=float(self.params["stop_atr"]),
                target_r=None,
                trail_atr=float(self.params["trail_atr"]),
                max_hold_bars=int(self.params["max_hold_bars"]),
                meta={
                    "lowest_low": lowest_low,
                    "atr": curr_atr,
                    "exit_period": p_exit,
                    "maker_offset_atr": 0.35,
                    "bbw_rank": bbw_rank,
                },
            ))

        return signals
