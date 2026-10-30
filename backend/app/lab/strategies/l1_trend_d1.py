"""L1 Trend Daily Strategy (trend_d1).

Upgraded to Volatility-Targeted Donchian + Hurst Trend Filter (Phase 4):
- Only enter when 1d Hurst H > 0.55
- Price closes above 20-day high
- Residual RS vs BTC is positive
- Exit via 2.5 x ATR Chandelier stop
"""

from __future__ import annotations

from typing import List, Literal
import pandas as pd
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_ema, calc_hurst


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
            "hurst_thresh": 0.55,
            "donchian_period": 20,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_donchian = int(self.params["donchian_period"])
        if len(df) < max(self.params["slow_ema"], 60) + 5:
            return []

        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # 1. Hurst trend filter (H > 0.55 persistent trend regime)
        h = calc_hurst(df["close"], lags=20)
        if h <= float(self.params["hurst_thresh"]):
            return []

        # 2. Donchian 20-day breakout
        donchian_hi = float(df["high"].iloc[-p_donchian-1:-1].max())
        if curr_close <= donchian_hi:
            return []

        # 3. Residual RS vs BTC check
        btc_bars = ctx.extra_data.get("btc_bars")
        if btc_bars is not None and len(btc_bars) >= p_donchian:
            ret_asset = (curr_close - float(df["close"].iloc[-p_donchian])) / float(df["close"].iloc[-p_donchian])
            btc_curr = float(btc_bars["close"].iloc[-1])
            btc_prev = float(btc_bars["close"].iloc[-p_donchian])
            ret_btc = (btc_curr - btc_prev) / max(btc_prev, 1e-6)
            residual_rs = ret_asset - ret_btc
            if residual_rs <= 0.0 and ctx.symbol != "BTCUSDT":
                return []

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
            meta={"atr": curr_atr, "hurst": h, "donchian_hi": donchian_hi},
        )
        return [sig]
