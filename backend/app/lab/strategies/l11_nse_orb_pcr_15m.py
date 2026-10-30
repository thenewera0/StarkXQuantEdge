"""L11 NSE 15m Opening Range Breakout + Option Chain Flow Strategy (nse_orb_pcr_15m).

Captures institutional trend days on Nifty 50 (^NSEI) and BankNifty (^NSEBANK):
1. First 15m bar (09:15–09:30 IST) establishes Opening Range High (ORH) and Low (ORL).
2. Rejects opening range if wider than 0.85% of underlying price (exhaustion gap protection).
3. Long Signal: 15m close breaks above ORH before 11:30 IST, price above VWAP, Option Chain PCR_OI >= 1.10, vol > 1.4x SMA20.
4. Short Signal: 15m close breaks below ORL before 11:30 IST, price below VWAP, Option Chain PCR_OI <= 0.85, vol > 1.4x SMA20.
5. Exit & Execution: Stop at midpoint (ORH + ORL)/2, target +2.0R, MIS auto-square-off at 15:15 IST.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional
import numpy as np
import pandas as pd

from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr, calc_ema, calc_sma
from app.market_hours import to_ist, is_mis_squareoff_time


class NSEOrbPcr15MStrategy:
    id: str = "nse_orb_pcr_15m"
    timeframe: Literal["15m", "1h", "4h", "1d"] = "15m"

    def __init__(self, variant_id: str = "nse_orb_pcr_15m_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "max_range_pct": 0.85,
            "pcr_long_min": 1.10,
            "pcr_short_max": 0.85,
            "vol_mult": 1.40,
            "target_r": 2.0,
            "max_hold_bars": 24,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        df = ctx.bars
        if len(df) < 30:
            return []

        curr_close = float(df["close"].iloc[-1])
        curr_open = float(df["open"].iloc[-1])
        curr_high = float(df["high"].iloc[-1])
        curr_low = float(df["low"].iloc[-1])
        curr_vol = float(df["volume"].iloc[-1])
        bar_open_time = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else df.index[-1]
        ist_dt = to_ist(bar_open_time)

        # Skip if outside entry window (09:30 to 11:30 IST)
        t = ist_dt.time()
        if not (datetime.strptime("09:30:00", "%H:%M:%S").time() <= t <= datetime.strptime("11:30:00", "%H:%M:%S").time()):
            return []

        # Find 09:15-09:30 opening bar for the current day
        if hasattr(df.index, "date"):
            day_bars = df[df.index.date == df.index[-1].date()]
        else:
            day_bars = df.tail(16)
        if len(day_bars) < 2:
            return []

        opening_bar = day_bars.iloc[0]
        orh = float(opening_bar["high"])
        orl = float(opening_bar["low"])
        or_range = orh - orl

        # Reject if opening 15m range is abnormally wide (> 0.85% of price)
        if (or_range / max(curr_close, 1.0)) * 100.0 > float(self.params["max_range_pct"]):
            return []

        # Volume confirmation
        vol_sma = calc_sma(df["volume"], 20)
        curr_vol_sma = float(vol_sma.iloc[-1])
        if curr_vol <= float(self.params["vol_mult"]) * curr_vol_sma:
            return []

        # Cumulative Intraday VWAP
        day_cum_vol = day_bars["volume"].cumsum()
        day_cum_pv = (day_bars["close"] * day_bars["volume"]).cumsum()
        vwap = float(day_cum_pv.iloc[-1] / max(day_cum_vol.iloc[-1], 1e-4))

        # Option chain PCR (from extra_data if available, otherwise synthetic neutral)
        pcr_oi = float(ctx.extra_data.get("pcr_oi", 1.05))

        direction: Optional[Literal["long", "short"]] = None
        if curr_close > orh and curr_close > vwap and pcr_oi >= float(self.params["pcr_long_min"]):
            direction = "long"
        elif curr_close < orl and curr_close < vwap and pcr_oi <= float(self.params["pcr_short_max"]):
            direction = "short"

        if not direction:
            return []

        midpoint = (orh + orl) / 2.0
        atr = calc_atr(df, 14)
        curr_atr = float(atr.iloc[-1]) if not atr.empty else curr_close * 0.005

        if direction == "long":
            entry = curr_close
            stop = min(midpoint, entry - 0.5 * curr_atr)
            target = entry + float(self.params["target_r"]) * (entry - stop)
        else:
            entry = curr_close
            stop = max(midpoint, entry + 0.5 * curr_atr)
            target = entry - float(self.params["target_r"]) * (stop - entry)

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
