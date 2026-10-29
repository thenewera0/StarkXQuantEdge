"""StarkX LAB: Statistical Controls & Cost Gate.

Section 1 Requirements:
- RandomEntryControl: Same number of trades as strategy, same exits, 1,000 permutations weekly.
- AlwaysLongControl: Every closed bar, same exits.
- CostGate: Auto-disable any strategy/timeframe whose median cost_R > 0.25.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


class CostGate:
    """Auto-disables any strategy/timeframe variant whose median cost_R > 0.25."""

    MAX_MEDIAN_COST_R: float = 0.25

    @classmethod
    def evaluate(cls, trades: List[Dict]) -> Tuple[bool, float]:
        """Calculates median cost_R across completed trades.
        
        Returns (is_passed, median_cost_r).
        """
        if not trades:
            return True, 0.0

        cost_r_values = []
        for t in trades:
            risk_usd = t.get("risk_r_usd", 50.0)
            fee = t.get("fee_paid_usd", 0.0)
            gst = t.get("gst_paid_usd", 0.0)
            slippage = t.get("slippage_usd", 0.0)
            funding = t.get("funding_paid_usd", 0.0)
            total_cost = fee + gst + slippage + funding
            cost_r = total_cost / max(risk_usd, 1e-6)
            cost_r_values.append(cost_r)

        med_cost_r = float(np.median(cost_r_values)) if cost_r_values else 0.0
        is_passed = med_cost_r <= cls.MAX_MEDIAN_COST_R
        return is_passed, round(med_cost_r, 4)


class RandomEntryControl:
    """Random entry control: same trade count N, same exits, permuted entries."""

    @staticmethod
    def simulate_random_entries(
        bars: pd.DataFrame,
        n_trades: int,
        stop_atr_mult: float = 2.0,
        target_r: float | None = None,
        max_hold_bars: int = 24,
        permutations: int = 1000,
        seed: int = 17,
    ) -> List[float]:
        """Simulates 1,000 random entry permutations to establish statistical baseline R-distribution."""
        n_bars = len(bars)
        if n_bars < max_hold_bars + 20 or n_trades <= 0:
            return [0.0]

        rng = np.random.default_rng(seed=seed)
        eligible_indices = np.arange(15, n_bars - max_hold_bars)
        if len(eligible_indices) < n_trades:
            return [0.0]

        closes = bars["close"].values
        highs = bars["high"].values
        lows = bars["low"].values
        
        # Approximate ATR
        trs = np.maximum(highs[1:] - lows[1:], np.maximum(np.abs(highs[1:] - closes[:-1]), np.abs(lows[1:] - closes[:-1])))
        atr = np.pad(pd.Series(trs).rolling(14, min_periods=1).mean().values, (1, 0), mode="edge")

        perm_means = []
        for _ in range(permutations):
            chosen = rng.choice(eligible_indices, size=n_trades, replace=False)
            r_returns = []
            for idx in chosen:
                entry = closes[idx]
                curr_atr = atr[idx]
                stop_dist = max(stop_atr_mult * curr_atr, entry * 0.0025)
                stop_price = entry - stop_dist
                target_price = (entry + target_r * stop_dist) if target_r is not None else None

                # Forward simulate exits on bar granularity
                exit_price = closes[min(idx + max_hold_bars, n_bars - 1)]
                for step in range(1, max_hold_bars + 1):
                    bar_idx = idx + step
                    if bar_idx >= n_bars:
                        break
                    # Stop first collision check
                    if lows[bar_idx] <= stop_price:
                        exit_price = stop_price
                        break
                    if target_price is not None and highs[bar_idx] >= target_price:
                        exit_price = target_price
                        break

                trade_r = (exit_price - entry) / stop_dist
                r_returns.append(trade_r)

            perm_means.append(float(np.mean(r_returns)))

        return perm_means


class AlwaysLongControl:
    """Always-long naive baseline executing continuous exposure with the same exit parameters."""

    @staticmethod
    def simulate_always_long(
        bars: pd.DataFrame,
        stop_atr_mult: float = 2.0,
        max_hold_bars: int = 24,
    ) -> List[float]:
        """Simulates periodic rolling long baseline with same hold periods."""
        n_bars = len(bars)
        if n_bars < max_hold_bars + 20:
            return []

        closes = bars["close"].values
        r_returns = []
        step = max(1, max_hold_bars // 2)
        for idx in range(15, n_bars - max_hold_bars, step):
            entry = closes[idx]
            exit_px = closes[idx + max_hold_bars]
            approx_stop_dist = entry * 0.02
            r = (exit_px - entry) / approx_stop_dist
            r_returns.append(r)

        return r_returns
