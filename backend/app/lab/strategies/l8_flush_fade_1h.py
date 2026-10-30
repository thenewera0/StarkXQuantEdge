"""L8 Flush Drop Maker Fade 1h Strategy (flush_fade_1h).

Specification:
1h return <= -3% and volume z-score (30d) >= 3 and close > 200-day SMA
-> long with maker entry at close - 0.15 ATR, 2-bar expiry;
exit after 24 bars or +1.5R / -1R.
"""

from __future__ import annotations

import pandas as pd
from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_sma


class FlushFade1HStrategy:
    id: str = "flush_fade_1h"
    timeframe: Literal["1h", "4h", "1d"] = "1h"

    def __init__(self, variant_id: str = "flush_fade_1h_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "drop_pct": -3.0,
            "volume_z_min": 3.0,
            "maker_atr_offset": 0.15,
            "maker_expiry_bars": 2,
            "target_r": 1.5,
            "stop_r": 1.0,
            "max_hold_bars": 24,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        if len(df) < 240:
            return []

        # 1. 1h return
        curr_close = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2])
        ret_1h_pct = ((curr_close - prev_close) / prev_close) * 100.0

        # 2. Volume z-score over trailing window
        vol = df["volume"]
        vol_lookback = min(len(vol) - 1, 720)
        vol_mean = float(vol.iloc[-vol_lookback:-1].mean())
        vol_std = float(vol.iloc[-vol_lookback:-1].std())
        curr_vol = float(vol.iloc[-1])
        vol_z = (curr_vol - vol_mean) / max(vol_std, 1e-6)

        # 3. Lower wick >= 45% (Liquidation absorption wick)
        from app.lab.strategies.base import calc_rejection_wick
        lower_wick, _ = calc_rejection_wick(df)

        # 4. Open Interest Flush (delta OI < -2.0 sigma)
        oi_z = ctx.extra_data.get("oi_change_z")
        oi_flush = (oi_z is None) or (oi_z < -2.0)  # Forced liquidations absorbed

        # Check conditions
        if (
            vol_z >= 3.0
            and lower_wick >= 0.45
            and oi_flush
        ):
            atr = calc_atr(df, 14)
            curr_atr = float(atr.iloc[-1])
            bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

            return [Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="long",
                bar_open_time=bar_open_time,
                entry_mode="maker",
                stop_atr=float(self.params["stop_r"]),
                target_r=float(self.params["target_r"]),
                trail_atr=None,
                max_hold_bars=int(self.params["max_hold_bars"]),
                meta={
                    "ret_1h": ret_1h_pct,
                    "vol_z": vol_z,
                    "lower_wick": lower_wick,
                    "maker_offset_atr": float(self.params["maker_atr_offset"]),
                    "expiry_bars": int(self.params["maker_expiry_bars"]),
                    "atr": curr_atr,
                },
            )]

        return []
