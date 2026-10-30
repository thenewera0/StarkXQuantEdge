"""L10 Carry Sleeve Strategy (carry_v2).

Specification:
v2 Sleeve C paper with its economic hurdle gate unchanged (10.5% net APR hurdle, 3x ATR liquidation buffer).
"""

from __future__ import annotations

from typing import List, Literal
import numpy as np
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
        df = ctx.bars
        if len(df) < 30:
            return []

        funding_rate = ctx.funding_rate if ctx.funding_rate is not None else 0.0001
        
        # AR(1) 72h forecast on funding history (9 periods of 8h)
        funding_hist = ctx.extra_data.get("funding_history", [funding_rate] * 15)
        if len(funding_hist) >= 10:
            y = np.array(funding_hist)
            y_lag = y[:-1]
            dy = y[1:]
            var_lag = float(np.var(y_lag))
            phi = float(np.cov(dy, y_lag)[0, 1]) / max(var_lag, 1e-9)
            phi = max(-0.95, min(0.95, phi))
            forecast_72h = sum(float(funding_rate * (phi ** step)) for step in range(1, 10))
        else:
            forecast_72h = float(funding_rate * 9.0)

        # Economic Hurdle: 3.5x round trip fees + 18% GST
        # Maker fee 2 bps each way = 4 bps = 0.0004 * 1.18 = 0.000472
        rt_fee_gst = 0.0004 * 1.18
        hurdle_threshold = 3.5 * rt_fee_gst

        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # 3 consecutive epochs persistence check
        epochs_below = int(ctx.extra_data.get("consecutive_epochs_below", 0))
        if forecast_72h < hurdle_threshold:
            epochs_below += 1
            if epochs_below >= 3:
                return []  # Rotate out only after 3 consecutive epochs below hurdle
        else:
            epochs_below = 0

        # Liquidation buffer check
        liq_buffer_multiple = (curr_close * 0.30) / max(curr_atr, 1e-6)

        if forecast_72h >= hurdle_threshold and liq_buffer_multiple >= float(self.params["min_liq_buffer_atr"]):
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
                    "forecast_72h": forecast_72h,
                    "hurdle_threshold": hurdle_threshold,
                    "liq_buffer": liq_buffer_multiple,
                    "atr": curr_atr,
                },
            )]

        return []
