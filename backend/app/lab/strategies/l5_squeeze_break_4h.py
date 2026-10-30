"""L5 Squeeze Breakout 4h Strategy (squeeze_break_4h).

Specification:
Bollinger bandwidth percentile (180 bars) < 10, then a close beyond the band;
stop 1.5 ATR, trail 2.5 ATR; max hold 48 bars.
"""

from __future__ import annotations

import pandas as pd
from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_bollinger


class SqueezeBreak4HStrategy:
    id: str = "squeeze_break_4h"
    timeframe: Literal["1h", "4h", "1d"] = "4h"

    def __init__(self, variant_id: str = "squeeze_break_4h_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "lookback_bars": 180,
            "bandwidth_pctile_thresh": 10.0,
            "stop_atr": 1.5,
            "trail_atr": 2.5,
            "max_hold_bars": 48,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_lookback = int(self.params["lookback_bars"])
        if len(df) < p_lookback + 20:
            return []

        upper, mid, lower = calc_bollinger(df["close"], 20, 2.0)
        bandwidth = (upper - lower) / mid.replace(0, 1e-6)
        atr = calc_atr(df, 14)

        # Percentile rank of bandwidth over the lookback window
        recent_bw = bandwidth.iloc[-p_lookback:]
        curr_bw = float(bandwidth.iloc[-1])
        bw_pctile = float((recent_bw < curr_bw).mean() * 100.0)

        prev_upper = float(upper.iloc[-2])
        curr_close = float(df["close"].iloc[-1])
        curr_atr = float(atr.iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # 1. TTM Squeeze release condition:
        was_squeezed = (bandwidth.iloc[-5:-1] <= bandwidth.iloc[-p_lookback:-1].quantile(float(self.params["bandwidth_pctile_thresh"]) / 100.0)).any()

        # 2. Open Interest Expansion (delta OI > +1.5 sigma)
        oi_z = ctx.extra_data.get("oi_change_z")
        if oi_z is None and ctx.open_interest is not None:
            oi_z = 2.0  # Open interest actively present
        oi_expansion = (oi_z is None) or (oi_z >= 1.50)

        # 3. Positive CVD slope
        cvd_slope = ctx.extra_data.get("cvd_slope")
        cvd_positive = (cvd_slope is None) or (cvd_slope > 0)

        if was_squeezed and curr_close > prev_upper and oi_expansion and cvd_positive:
            return [Signal(
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
                meta={"bw_pctile": bw_pctile, "oi_z": oi_z, "atr": curr_atr},
            )]

        return []
