"""L10 Carry Sleeve Strategy (carry_v2).

Specification:
v2 Sleeve C paper with its economic hurdle gate unchanged (10.5% net APR hurdle, 3x ATR liquidation buffer).
"""

from __future__ import annotations

from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr


class CarryV2Strategy:
    id: str = "carry_v2"
    timeframe: Literal["1h", "4h", "1d"] = "1d"

    def __init__(self, variant_id: str = "carry_v2_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "hurdle_apr_pct": 10.5,
            "min_liq_buffer_atr": 3.0,
            "max_hold_days": 90,
            "stop_atr": 3.0,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        # Evaluated on BTC and ETH basis carry
        if ctx.symbol not in ("BTCUSDT", "BTC", "ETHUSDT", "ETH"):
            return []

        df = ctx.bars
        if len(df) < 30:
            return []

        # Annualized funding rate (3 x 365 = 1095 funding intervals/year)
        funding_rate = ctx.funding_rate if ctx.funding_rate is not None else 0.0001
        annualized_apr = funding_rate * 3 * 365 * 100.0  # in percent

        hurdle_apr = float(self.params["hurdle_apr_pct"])
        min_liq_buffer = float(self.params["min_liq_buffer_atr"])

        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # Liquidation buffer check
        liq_buffer_multiple = (curr_close * 0.30) / max(curr_atr, 1e-6)

        if annualized_apr >= hurdle_apr and liq_buffer_multiple >= min_liq_buffer:
            return [Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="long",
                bar_open_time=bar_open_time,
                entry_mode="next_open",
                stop_atr=float(self.params["stop_atr"]),
                target_r=None,
                trail_atr=4.0,
                max_hold_bars=int(self.params["max_hold_days"]),
                meta={
                    "annualized_apr": annualized_apr,
                    "hurdle_apr": hurdle_apr,
                    "liq_buffer": liq_buffer_multiple,
                    "atr": curr_atr,
                },
            )]

        return []
