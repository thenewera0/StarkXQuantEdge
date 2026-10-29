"""L3 RSI(2) Pullback 1h Strategy (rsi2_pullback_1h).

Specification:
Long when RSI(2) < 10 and close > SMA(200); exit RSI(2) > 70 or 12 bars; stop 2 ATR.
Mirrored short variant: short when RSI(2) > 90 below SMA(200); exit RSI(2) < 30 or 12 bars; stop 2 ATR.
"""

from __future__ import annotations

from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_rsi, calc_sma


class RSI2Pullback1HStrategy:
    id: str = "rsi2_pullback_1h"
    timeframe: Literal["1h", "4h", "1d"] = "1h"

    def __init__(self, variant_id: str = "rsi2_pullback_1h_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "rsi_period": 2,
            "trend_sma": 200,
            "oversold_thresh": 10,
            "overbought_thresh": 90,
            "exit_rsi_long": 70,
            "exit_rsi_short": 30,
            "stop_atr": 2.0,
            "max_hold_bars": 12,
        }
        self.params = {**defaults, **(params or {})}
        self.is_short_variant = "short" in variant_id.lower()

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_sma = int(self.params["trend_sma"])
        if len(df) < p_sma + 10:
            return []

        rsi = calc_rsi(df["close"], int(self.params["rsi_period"]))
        sma = calc_sma(df["close"], p_sma)
        atr = calc_atr(df, 14)

        curr_rsi = float(rsi.iloc[-1])
        curr_sma = float(sma.iloc[-1])
        curr_atr = float(atr.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        signals = []
        if not self.is_short_variant:
            # Long: RSI(2) < 10 and close > SMA(200)
            if curr_rsi < float(self.params["oversold_thresh"]) and curr_close > curr_sma:
                signals.append(Signal(
                    strategy_id=self.id,
                    variant_id=self.variant_id,
                    symbol=ctx.symbol,
                    direction="long",
                    bar_open_time=bar_open_time,
                    entry_mode="next_open",
                    stop_atr=float(self.params["stop_atr"]),
                    target_r=1.5,
                    trail_atr=None,
                    max_hold_bars=int(self.params["max_hold_bars"]),
                    meta={"rsi": curr_rsi, "sma200": curr_sma, "atr": curr_atr},
                ))
        else:
            # Short: RSI(2) > 90 and close < SMA(200)
            if curr_rsi > float(self.params["overbought_thresh"]) and curr_close < curr_sma:
                signals.append(Signal(
                    strategy_id=self.id,
                    variant_id=self.variant_id,
                    symbol=ctx.symbol,
                    direction="short",
                    bar_open_time=bar_open_time,
                    entry_mode="next_open",
                    stop_atr=float(self.params["stop_atr"]),
                    target_r=1.5,
                    trail_atr=None,
                    max_hold_bars=int(self.params["max_hold_bars"]),
                    meta={"rsi": curr_rsi, "sma200": curr_sma, "atr": curr_atr},
                ))

        return signals
