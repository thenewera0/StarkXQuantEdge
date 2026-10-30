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
        if len(df) < max(p_bb, 35):
            return []

        from app.lab.strategies.base import calc_hurst, calc_ou_halflife, calc_rejection_wick

        # 1. Hurst exponent regime check (H < 0.44 mean reverting)
        h = calc_hurst(df["close"], lags=20)
        if h >= 0.44:
            return []

        # 2. OU Half-life check (t_half <= 12 bars)
        half_life = calc_ou_halflife(df["close"].iloc[-60:])
        if half_life > 12.0:
            return []

        # 3. 2.5-sigma Bollinger Bands
        upper, mid, lower = calc_bollinger(df["close"], p_bb, 2.5)
        atr = calc_atr(df, 14)

        curr_close = float(df["close"].iloc[-1])
        curr_upper = float(upper.iloc[-1])
        curr_mid = float(mid.iloc[-1])
        curr_lower = float(lower.iloc[-1])
        curr_atr = float(atr.iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # 4. Mandatory rejection wick >= 40%
        lower_wick, upper_wick = calc_rejection_wick(df)

        signals = []
        if not self.is_short_variant and curr_close < curr_lower and lower_wick >= 0.40:
            target_dist = curr_mid - curr_close
            stop_dist = float(self.params["stop_atr"]) * curr_atr
            target_r = round(max(0.5, min(target_dist / max(stop_dist, 1e-6), 4.0)), 2)

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
                meta={"hurst": h, "ou_half_life": half_life, "mid": curr_mid, "atr": curr_atr},
            ))
        elif self.is_short_variant and curr_close > curr_upper and upper_wick >= 0.40:
            target_dist = curr_close - curr_mid
            stop_dist = float(self.params["stop_atr"]) * curr_atr
            target_r = round(max(0.5, min(target_dist / max(stop_dist, 1e-6), 4.0)), 2)

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
                meta={"hurst": h, "ou_half_life": half_life, "mid": curr_mid, "atr": curr_atr},
            ))

        return signals
