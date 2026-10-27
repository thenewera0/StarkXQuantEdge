"""Triple-barrier labeling and vol-normalized forward returns in R (Phase 1.2 & Amendment E).

Zero lookahead: takes data[:t] only.
Simulates hybrid entry (limit at close - 0.15*ATR, cancel after 2 bars, then market),
same-bar dual touch = stop-first, and Phase 0.4 cost deductions.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings
from app.costs import trade_cost
from app.execution import tick_size

BARRIER_GRID = [
    (1.5, 1.0),   # K_up, K_dn
    (2.0, 1.25),
    (3.0, 1.5),
]

HORIZONS = [1, 4, 12, 24, 48]


def compute_vol_normalized_forward_returns(df: pd.DataFrame, horizons: list[int] = HORIZONS) -> pd.DataFrame:
    """Computes forward returns vol-normalized by (ATR14 / close).

    Return is: (close[t + h] - close[t]) / close[t] / (ATR14[t] / close[t])
    Zero lookahead: the denominator is ATR14[t] / close[t], known strictly at bar t close.
    """
    out = pd.DataFrame(index=df.index)
    close = df["close"]
    atr = df["atr"] if "atr" in df.columns else (df["high"] - df["low"]).rolling(14).mean()
    vol = (atr / close).replace(0, np.nan)

    for h in horizons:
        fwd_ret = (close.shift(-h) - close) / close
        out[f"fwd_ret_{h}b"] = fwd_ret
        out[f"fwd_vol_ret_{h}b"] = fwd_ret / vol

    return out


def simulate_hybrid_entry_barrier(
    df: pd.DataFrame,
    idx: int,
    direction: str = "long",
    k_up: float = 2.0,
    k_dn: float = 1.25,
    max_hold_bars: int = 48,
    symbol: str = "BTCUSDT",
    partial_book_r: float = 0.20,
    partial_book_frac: float = 0.50,
) -> dict[str, Any] | None:
    """Simulates a trade from bar idx under the hybrid entry rule and triple-barrier exit.

    Hybrid Entry Rule:
      - Place limit at close[t] - 0.15 * ATR14[t] (long) / + 0.15 * ATR14[t] (short).
      - Bar t+1 & t+2: if price trades THROUGH by >= 1 tick, filled as limit (maker).
      - If unfilled after 2 bars: market order fills at open[t+3] (taker).
    """
    n_bars = len(df)
    if idx + 3 >= n_bars:
        return None

    bar_t = df.iloc[idx]
    close_t = float(bar_t["close"])
    atr_t = float(bar_t.get("atr", (bar_t["high"] - bar_t["low"])))
    if close_t <= 0 or atr_t <= 0:
        return None

    t_size = tick_size(close_t)
    is_long = (direction.lower() == "long")

    # Limit order price
    if is_long:
        limit_px = close_t - 0.15 * atr_t
    else:
        limit_px = close_t + 0.15 * atr_t

    # 1. Simulate entry fill over bars idx+1, idx+2, idx+3
    entry_fill: float | None = None
    entry_execution = "maker"
    entry_bar_offset = 1

    for offset in (1, 2):
        if idx + offset >= n_bars:
            return None
        cand = df.iloc[idx + offset]
        high_c = float(cand["high"])
        low_c = float(cand["low"])

        if is_long:
            # Must trade THROUGH by >= 1 tick
            if low_c <= limit_px - t_size:
                entry_fill = limit_px
                entry_bar_offset = offset
                entry_execution = "maker"
                break
        else:
            if high_c >= limit_px + t_size:
                entry_fill = limit_px
                entry_bar_offset = offset
                entry_execution = "maker"
                break

    # If unfilled after 2 bars, sweep via market order at open of bar 3
    if entry_fill is None:
        cand3 = df.iloc[idx + 3]
        entry_fill = float(cand3["open"])
        entry_bar_offset = 3
        entry_execution = "taker"

    # Stop and target geometry based on ATR at fill
    risk_dist = k_dn * atr_t
    stop_dist_pct = risk_dist / entry_fill
    if risk_dist <= 0 or stop_dist_pct <= 0:
        return None

    if is_long:
        stop_px = entry_fill - risk_dist
        target_px = entry_fill + (k_up * atr_t)
    else:
        stop_px = entry_fill + risk_dist
        target_px = entry_fill - (k_up * atr_t)

    # 2. Simulate triple-barrier forward resolution
    start_sim = idx + entry_bar_offset
    end_sim = min(n_bars, start_sim + max_hold_bars)

    result = "timeout"
    exit_px = float(df.iloc[end_sim - 1]["close"])
    bars_held = end_sim - start_sim
    partial_booked = False

    for b in range(start_sim, end_sim):
        cand = df.iloc[b]
        high_b = float(cand["high"])
        low_b = float(cand["low"])
        close_b = float(cand["close"])

        # Check partial booking
        if not partial_booked:
            mfe_dist = (high_b - entry_fill) if is_long else (entry_fill - low_b)
            if (mfe_dist / risk_dist) >= partial_book_r:
                partial_booked = True

        # Check same-bar dual touch or barrier hits
        if is_long:
            hit_stop = (low_b <= stop_px)
            hit_target = (high_b >= target_px)

            if hit_stop and hit_target:
                # Same-bar dual touch = stop first (Rule 0.2 / R4)
                result = "stop"
                exit_px = stop_px
                bars_held = b - start_sim + 1
                break
            elif hit_stop:
                result = "stop"
                exit_px = stop_px
                bars_held = b - start_sim + 1
                break
            elif hit_target:
                result = "target"
                exit_px = target_px
                bars_held = b - start_sim + 1
                break
        else:
            hit_stop = (high_b >= stop_px)
            hit_target = (low_b <= target_px)

            if hit_stop and hit_target:
                result = "stop"
                exit_px = stop_px
                bars_held = b - start_sim + 1
                break
            elif hit_stop:
                result = "stop"
                exit_px = stop_px
                bars_held = b - start_sim + 1
                break
            elif hit_target:
                result = "target"
                exit_px = target_px
                bars_held = b - start_sim + 1
                break

    # Calculate Gross R
    r_exit = (exit_px - entry_fill) / risk_dist if is_long else (entry_fill - exit_px) / risk_dist
    if partial_booked:
        gross_r = partial_book_frac * partial_book_r + (1.0 - partial_book_frac) * r_exit
    else:
        gross_r = r_exit

    # Transaction costs from Phase 0.4 model
    holding_hours = bars_held * 4.0  # 4h bars
    cost_frac = trade_cost(
        market="crypto",
        symbol=symbol,
        atr_pct=atr_t / entry_fill,
        is_perp=True,
        entry_execution=entry_execution,
        exit_result=result,
        direction=direction,
        holding_hours=holding_hours,
    )
    cost_r = cost_frac / stop_dist_pct
    r_net = gross_r - cost_r

    return {
        "bar_idx": idx,
        "date": str(bar_t.name)[:10],
        "symbol": symbol,
        "direction": direction,
        "entry_px": entry_fill,
        "stop_px": stop_px,
        "target_px": target_px,
        "exit_px": exit_px,
        "entry_exec": entry_execution,
        "result": result,
        "bars_held": bars_held,
        "partial_booked": partial_booked,
        "gross_r": gross_r,
        "cost_r": cost_r,
        "r_net": r_net,
    }
