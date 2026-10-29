"""L4 Bollinger Bands Mean Reversion 1h Strategy (bb_fade_1h).

Specification:
ADX(14) < 20 and close < lower Bollinger(20,2) -> long; target = middle band; stop 1.5 ATR; max hold 24 bars.
Mirrored short variant: ADX(14) < 20 and close > upper Bollinger(20,2) -> short; target = middle band; stop 1.5 ATR; max hold 24 bars.
"""

from __future__ import annotations

from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_adx, calc_atr, calc_bollinger


class BBFade1HStrategy:
    id: str = "bb_fade_1h"
    timeframe: Literal["1h", "4h", "1d"] = "1h"

    def __init__(self, variant_id: str = "bb_fade_1h_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "bb_period": 20,
            "bb_std": 2.0,
            "adx_period": 14,
            "adx_max": 20.0,
            "stop_atr": 1.5,
            "max_hold_bars": 24,
        }
        self.params = {**defaults, **(params or {})}
        self.is_short_variant = "short" in variant_id.lower()

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_bb = int(self.params["bb_period"])
        if len(df) < max(p_bb, 30):
            return []

        upper, mid, lower = calc_bollinger(df["close"], p_bb, float(self.params["bb_std"]))
        adx = calc_adx(df, int(self.params["adx_period"]))
        atr = calc_atr(df, 14)

        curr_adx = float(adx.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        curr_upper = float(upper.iloc[-1])
        curr_mid = float(mid.iloc[-1])
        curr_lower = float(lower.iloc[-1])
        curr_atr = float(atr.iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        signals = []
        # Non-trending environment check
        if curr_adx < float(self.params["adx_max"]):
            if not self.is_short_variant and curr_close < curr_lower:
                # Long: Target is the middle band
                target_dist = curr_mid - curr_close
                stop_dist = float(self.params["stop_atr"]) * curr_atr
                target_r = round(target_dist / max(stop_dist, 1e-6), 2)
                # Keep target_r within allowed geometry bounds [0.5, 5.0]
                target_r = max(0.5, min(target_r, 4.0))

                signals.append(Signal(
                    strategy_id=self.id,
                    variant_id=self.variant_id,
                    symbol=ctx.symbol,
                    direction="long",
                    bar_open_time=bar_open_time,
                    entry_mode="next_open",
                    stop_atr=float(self.params["stop_atr"]),
                    target_r=target_r,
                    trail_atr=None,
                    max_hold_bars=int(self.params["max_hold_bars"]),
                    meta={"adx": curr_adx, "mid": curr_mid, "atr": curr_atr},
                ))
            elif self.is_short_variant and curr_close > curr_upper:
                # Short: Target is the middle band
                target_dist = curr_close - curr_mid
                stop_dist = float(self.params["stop_atr"]) * curr_atr
                target_r = round(target_dist / max(stop_dist, 1e-6), 2)
                target_r = max(0.5, min(target_r, 4.0))

                signals.append(Signal(
                    strategy_id=self.id,
                    variant_id=self.variant_id,
                    symbol=ctx.symbol,
                    direction="short",
                    bar_open_time=bar_open_time,
                    entry_mode="next_open",
                    stop_atr=float(self.params["stop_atr"]),
                    target_r=target_r,
                    trail_atr=None,
                    max_hold_bars=int(self.params["max_hold_bars"]),
                    meta={"adx": curr_adx, "mid": curr_mid, "atr": curr_atr},
                ))

        return signals
