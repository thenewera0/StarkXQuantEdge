"""L7 Funding Skew Sentiment 4h Strategy (funding_skew_4h).

Specification:
After each 8h funding settlement, funding z-score (30d) > +2 and close > SMA(50) -> short variant;
z < -2 -> long; stop 2 ATR; max hold 24 bars.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_sma


class FundingSkew4HStrategy:
    id: str = "funding_skew_4h"
    timeframe: Literal["1h", "4h", "1d"] = "4h"

    def __init__(self, variant_id: str = "funding_skew_4h_long", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "z_lookback_days": 30,
            "z_threshold": 2.0,
            "trend_sma": 50,
            "stop_atr": 2.0,
            "max_hold_bars": 24,
        }
        self.params = {**defaults, **(params or {})}
        self.is_short_variant = "short" in variant_id.lower()

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        p_sma = int(self.params["trend_sma"])
        if len(df) < p_sma + 10:
            return []

        # Funding z-score check
        funding_rate = ctx.funding_rate
        funding_series = ctx.extra_data.get("funding_history")
        
        if funding_series is not None and len(funding_series) >= 30:
            s = pd.Series(funding_series)
            mean_f = float(s.mean())
            std_f = float(s.std())
            curr_f = float(s.iloc[-1]) if funding_rate is None else funding_rate
            z_score = (curr_f - mean_f) / max(std_f, 1e-6)
        elif funding_rate is not None:
            # Estimate z-score from current funding rate assuming standard 0.01% baseline
            z_score = (funding_rate - 0.0001) / 0.0002
        else:
            # Proxy sentiment from premium/discount of high/low relative to close
            ret = df["close"].pct_change()
            z_score = float((ret.iloc[-1] - ret.rolling(180).mean().iloc[-1]) / max(ret.rolling(180).std().iloc[-1], 1e-6))

        sma = calc_sma(df["close"], p_sma)
        curr_sma = float(sma.iloc[-1])
        curr_close = float(df["close"].iloc[-1])
        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]
        z_thresh = float(self.params["z_threshold"])

        signals = []
        if not self.is_short_variant:
            # Long: z < -2 (extreme negative funding / oversold short squeeze setup)
            if z_score < -z_thresh:
                signals.append(Signal(
                    strategy_id=self.id,
                    variant_id=self.variant_id,
                    symbol=ctx.symbol,
                    direction="long",
                    bar_open_time=bar_open_time,
                    entry_mode="next_open",
                    stop_atr=float(self.params["stop_atr"]),
                    target_r=2.0,
                    trail_atr=None,
                    max_hold_bars=int(self.params["max_hold_bars"]),
                    meta={"z_score": z_score, "atr": curr_atr},
                ))
        else:
            # Short: z > +2 and close > SMA(50) (crowded long positioning fade)
            if z_score > z_thresh and curr_close > curr_sma:
                signals.append(Signal(
                    strategy_id=self.id,
                    variant_id=self.variant_id,
                    symbol=ctx.symbol,
                    direction="short",
                    bar_open_time=bar_open_time,
                    entry_mode="next_open",
                    stop_atr=float(self.params["stop_atr"]),
                    target_r=2.0,
                    trail_atr=None,
                    max_hold_bars=int(self.params["max_hold_bars"]),
                    meta={"z_score": z_score, "atr": curr_atr},
                ))

        return signals
