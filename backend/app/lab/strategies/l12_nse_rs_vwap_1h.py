"""L12 NSE Relative Strength Leaders vs Laggards L/S Strategy (nse_rs_vwap_1h).

Exploits institutional sector rotation across liquid Nifty 50 F&O stocks:
1. Hourly bar evaluation during IST market hours.
2. Calculates 30-bar (~5 trading days) beta-adjusted residual return vs benchmark (^NSEI).
3. Long: Top quartile RS (RS_Z > +1.2), Benchmark above 50-EMA, price touches rolling VWAP / 21-EMA with bullish rejection wick >= 35%, RSI > 45.
4. Short: Bottom quartile RS (RS_Z < -1.2), Benchmark below 50-EMA, price touches rolling VWAP / 21-EMA with bearish rejection wick >= 35%, RSI < 55.
5. Exit: Target +2.5R, stop at 1.8x ATR.
"""

from __future__ import annotations

from typing import List, Literal, Optional
import numpy as np
import pandas as pd

from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_ema, calc_rsi, calc_rejection_wick


class NSERSVwap1HStrategy:
    id: str = "nse_rs_vwap_1h"
    timeframe: Literal["15m", "1h", "4h", "1d"] = "1h"

    def __init__(self, variant_id: str = "nse_rs_vwap_1h_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "rs_lookback_bars": 30,
            "rs_z_thresh": 1.20,
            "rsi_period": 14,
            "ema_trend": 50,
            "ema_pullback": 21,
            "stop_atr": 1.8,
            "target_r": 2.5,
            "max_hold_bars": 36,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_rs = int(self.params["rs_lookback_bars"])
        if len(df) < p_rs + 15:
            return []

        curr_close = float(df["close"].iloc[-1])
        curr_open = float(df["open"].iloc[-1])
        curr_high = float(df["high"].iloc[-1])
        curr_low = float(df["low"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]

        # Benchmark context (Nifty 50)
        bench = ctx.extra_data.get("benchmark_bars")
        if bench is None or len(bench) < p_rs + 15:
            bench = df  # fallback if single-asset mode

        bench_close = bench["close"]
        bench_ema50 = calc_ema(bench_close, int(self.params["ema_trend"]))
        bench_bullish = float(bench_close.iloc[-1]) >= float(bench_ema50.iloc[-1])

        # Residual Return vs Benchmark over 30 bars
        ret_asset = (df["close"] / df["close"].shift(p_rs) - 1.0).dropna()
        ret_bench = (bench_close / bench_close.shift(p_rs) - 1.0).dropna()
        aligned_bench = ret_bench.reindex(ret_asset.index).bfill()

        # Simple beta estimation
        cov = np.cov(ret_asset.values[-30:], aligned_bench.values[-30:])
        beta = cov[0, 1] / max(cov[1, 1], 1e-6) if cov[1, 1] > 0 else 1.0
        residual_return = float(ret_asset.iloc[-1] - beta * aligned_bench.iloc[-1])

        # Rolling RS mean and std for Z-score
        res_series = ret_asset - beta * aligned_bench
        rs_mean = float(res_series.rolling(30, min_periods=10).mean().iloc[-1])
        rs_std = float(res_series.rolling(30, min_periods=10).std().iloc[-1])
        rs_z = (residual_return - rs_mean) / max(rs_std, 1e-4)

        # Pullback EMA21 & RSI(14)
        ema21 = calc_ema(df["close"], int(self.params["ema_pullback"]))
        curr_ema21 = float(ema21.iloc[-1])
        rsi = calc_rsi(df["close"], int(self.params["rsi_period"]))
        curr_rsi = float(rsi.iloc[-1])

        lower_wick, upper_wick = calc_rejection_wick(df)

        direction: Optional[Literal["long", "short"]] = None
        # Long: Strong RS, Bullish market, pullback to EMA21 with bullish rejection wick
        if (rs_z >= float(self.params["rs_z_thresh"]) and bench_bullish and
            curr_low <= curr_ema21 * 1.003 and curr_close >= curr_ema21 and
            lower_wick >= 0.35 and curr_rsi > 45.0):
            direction = "long"
        # Short: Weak RS, Bearish market, rally into EMA21 with bearish rejection wick
        elif (rs_z <= -float(self.params["rs_z_thresh"]) and not bench_bullish and
              curr_high >= curr_ema21 * 0.997 and curr_close <= curr_ema21 and
              upper_wick >= 0.35 and curr_rsi < 55.0):
            direction = "short"

        if not direction:
            return []

        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1]) if not atr.empty else curr_close * 0.01
        stop_dist = max(float(self.params["stop_atr"]) * curr_atr, curr_close * 0.006)

        if direction == "long":
            entry = curr_close
            stop = entry - stop_dist
            target = entry + float(self.params["target_r"]) * stop_dist
        else:
            entry = curr_close
            stop = entry + stop_dist
            target = entry - float(self.params["target_r"]) * stop_dist

        return [
            Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction=direction,
                bar_open_time=bar_open_time,
                entry_mode="maker",
                entry_price=round(entry, 2),
                initial_stop=round(stop, 2),
                target_price=round(target, 2),
                max_hold_bars=int(self.params["max_hold_bars"]),
                timeframe=self.timeframe,
            )
        ]
