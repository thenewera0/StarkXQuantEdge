"""L9 ETH/BTC Log Ratio Spread 1d Strategy (pairs_btceth_1d).

Specification:
z-score of log(ETH/BTC) over 60 days;
|z| > 2 -> dollar-neutral spread;
exit |z| < 0.5; stop |z| > 4; max hold 30 days.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List, Literal
from app.lab.models import MarketContext, Signal
from app.lab.strategies.base import calc_atr


class PairsBTCETH1DStrategy:
    id: str = "pairs_btceth_1d"
    timeframe: Literal["1h", "4h", "1d"] = "1d"

    def __init__(self, variant_id: str = "pairs_btceth_1d_base", params: dict | None = None):
        self.variant_id = variant_id
        defaults = {
            "lookback_days": 60,
            "entry_z": 2.0,
            "exit_z": 0.5,
            "stop_z": 4.0,
            "max_hold_days": 30,
        }
        self.params = {**defaults, **(params or {})}

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        # Only evaluate on ETHUSDT to avoid duplicate pairs
        if ctx.symbol not in ("ETHUSDT", "ETH"):
            return []

        df_eth = ctx.bars
        p_lookback = int(self.params["lookback_days"])
        if len(df_eth) < p_lookback + 5:
            return []

        # Get BTC bars from extra_data
        df_btc = ctx.extra_data.get("btc_bars")
        if df_btc is None or len(df_btc) < p_lookback + 5:
            return []

        # Align closes
        aligned = pd.concat([df_eth["close"].rename("eth"), df_btc["close"].rename("btc")], axis=1).dropna()
        if len(aligned) < p_lookback + 5:
            return []

        log_ratio = np.log(aligned["eth"] / aligned["btc"])
        rolling_mean = log_ratio.rolling(window=p_lookback).mean()
        rolling_std = log_ratio.rolling(window=p_lookback).std()

        curr_log_ratio = float(log_ratio.iloc[-1])
        curr_mean = float(rolling_mean.iloc[-1])
        curr_std = float(rolling_std.iloc[-1])
        z = (curr_log_ratio - curr_mean) / max(curr_std, 1e-6)

        atr = calc_atr(df_eth, 14)
        curr_atr = float(atr.iloc[-1])
        bar_open_time = df_eth.index[-1].to_pydatetime() if hasattr(df_eth.index[-1], "to_pydatetime") else df_eth.index[-1]
        entry_z = float(self.params["entry_z"])

        signals = []
        if z < -entry_z:
            # ETH undervalued vs BTC -> Long ETH
            signals.append(Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="long",
                bar_open_time=bar_open_time,
                entry_mode="next_open",
                stop_atr=2.5,
                target_r=2.0,
                trail_atr=None,
                max_hold_bars=int(self.params["max_hold_days"]),
                meta={"z_score": z, "aligned_pair": "ETH/BTC", "atr": curr_atr},
            ))
        elif z > entry_z:
            # ETH overvalued vs BTC -> Short ETH
            signals.append(Signal(
                strategy_id=self.id,
                variant_id=self.variant_id,
                symbol=ctx.symbol,
                direction="short",
                bar_open_time=bar_open_time,
                entry_mode="next_open",
                stop_atr=2.5,
                target_r=2.0,
                trail_atr=None,
                max_hold_bars=int(self.params["max_hold_days"]),
                meta={"z_score": z, "aligned_pair": "ETH/BTC", "atr": curr_atr},
            ))

        return signals
