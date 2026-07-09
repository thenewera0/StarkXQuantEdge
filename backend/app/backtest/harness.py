"""Bar-by-bar backtest. The single most important file for trusting this system.

Integrity rules (see PLAN.md §4):
  * The decision for bar t is computed from the indicator row at bar t-1 (last CLOSED bar).
  * Entry fills at bar t's OPEN, never its close. No same-bar lookahead.
  * Stop and target are ATR-based, sized at entry. Intrabar, if BOTH could fill in one bar,
    we assume the STOP filled first (conservative — never flatter the result).
  * Every fill pays slippage; every round-trip pays 2x the fee rate.
  * No survivorship: we test exactly the series handed in, start to finish.

This is intentionally a simple long/short stop-target strategy driver. Its job is to measure
whether the factor scorer has any edge net of costs, not to be a production execution engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..costs import round_trip_cost
from ..factors import score_row

_LONG_LABELS = {"Buy", "Strong Buy"}
_SHORT_LABELS = {"Sell", "Strong Sell"}


def _market_of(symbol: str) -> str:
    s = (symbol or "").upper()
    return "crypto" if (s.endswith("USDT") or s.endswith("USDC") or s.endswith("BUSD")) else "forex"


@dataclass
class Trade:
    direction: str          # "long" | "short"
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    net_return: float       # fraction, net of fees + slippage
    exit_reason: str        # "target" | "stop" | "flip" | "max_hold" | "end"
    bars_held: int
    mfe: float              # max favorable excursion, fraction of entry
    mae: float              # max adverse excursion, fraction of entry
    confidence: float


@dataclass
class BacktestResult:
    symbol: str
    interval: str
    trades: list[Trade] = field(default_factory=list)
    n_bars: int = 0

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.net_return > 0)

    @property
    def hit_rate(self) -> float:
        return self.wins / self.n_trades if self.n_trades else 0.0

    @property
    def total_return(self) -> float:
        """Sum of per-trade net returns (1 unit risked per trade; not compounded)."""
        return sum(t.net_return for t in self.trades)

    @property
    def avg_return(self) -> float:
        return self.total_return / self.n_trades if self.n_trades else 0.0

    @property
    def avg_win(self) -> float:
        w = [t.net_return for t in self.trades if t.net_return > 0]
        return sum(w) / len(w) if w else 0.0

    @property
    def avg_loss(self) -> float:
        l = [t.net_return for t in self.trades if t.net_return <= 0]
        return sum(l) / len(l) if l else 0.0

    @property
    def profit_factor(self) -> float:
        gains = sum(t.net_return for t in self.trades if t.net_return > 0)
        losses = -sum(t.net_return for t in self.trades if t.net_return < 0)
        return gains / losses if losses > 0 else float("inf")

    def summary(self) -> dict:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "bars": self.n_bars,
            "trades": self.n_trades,
            "hit_rate": round(self.hit_rate, 4),
            "total_return": round(self.total_return, 4),
            "avg_return": round(self.avg_return, 5),
            "avg_win": round(self.avg_win, 5),
            "avg_loss": round(self.avg_loss, 5),
            "profit_factor": round(self.profit_factor, 3) if self.profit_factor != float("inf") else None,
        }


def backtest(
    df_ind: pd.DataFrame,
    symbol: str,
    interval: str,
    *,
    fee_rate: float = 0.0004,      # DEPRECATED: superseded by costs.round_trip_cost (kept for API compat)
    slippage: float = 0.0002,      # DEPRECATED: superseded by costs.round_trip_cost (kept for API compat)
    atr_mult: float = 1.5,         # stop distance = atr_mult * ATR
    reward_risk: float = 2.0,      # target distance = reward_risk * stop distance
    max_hold_bars: int = 48,       # force exit after this many bars
    warmup: int = 200,             # skip until EMA200 etc. are valid
    flip_on_opposite: bool = True, # exit if an opposing signal forms
    start_idx: int | None = None,  # first bar index allowed to OPEN a trade
    end_idx: int | None = None,    # entries only while index < end_idx (exits may run past)
    weights_override: dict | None = None,  # adaptive/challenger weights for the scorer
) -> BacktestResult:
    """Replay a fully-indicator'd OHLCV frame through the factor scorer.

    `df_ind` must already contain indicator columns (run compute_indicators first).
    `start_idx`/`end_idx` bound where NEW trades may open — used for walk-forward folds so
    out-of-sample windows are evaluated in isolation while indicators keep their real history.
    """
    result = BacktestResult(symbol=symbol, interval=interval, n_bars=len(df_ind))
    rows = df_ind
    n = len(rows)
    opens = rows["open"].to_numpy()
    highs = rows["high"].to_numpy()
    lows = rows["low"].to_numpy()
    times = rows.index
    market = _market_of(symbol)

    entry_limit = n if end_idx is None else min(end_idx, n)
    i = max(warmup, 1, start_idx or 0)
    while i < entry_limit:
        prev = rows.iloc[i - 1]
        sig = score_row(prev, interval, weights=weights_override)

        direction = None
        if sig.label in _LONG_LABELS:
            direction = "long"
        elif sig.label in _SHORT_LABELS:
            direction = "short"

        if direction is None or np.isnan(sig.atr) or sig.atr <= 0:
            i += 1
            continue

        # Enter at this bar's open. Slippage is charged once as part of round_trip_cost below,
        # not baked into the fill price, so live (resolver) and backtest costing stay identical.
        entry = opens[i]
        atr_pct = sig.atr / entry if entry else 0.0
        cost = round_trip_cost(market, symbol, atr_pct)
        if direction == "long":
            stop = entry - atr_mult * sig.atr
            target = entry + reward_risk * atr_mult * sig.atr
        else:
            stop = entry + atr_mult * sig.atr
            target = entry - reward_risk * atr_mult * sig.atr

        exit_price = None
        exit_reason = "end"
        exit_idx = n - 1
        mfe = mae = 0.0

        j = i
        while j < n:
            hi, lo = highs[j], lows[j]
            # Track excursions (fraction of entry).
            if direction == "long":
                mfe = max(mfe, (hi - entry) / entry)
                mae = min(mae, (lo - entry) / entry)
                hit_stop = lo <= stop
                hit_target = hi >= target
            else:
                mfe = max(mfe, (entry - lo) / entry)
                mae = min(mae, (entry - hi) / entry)
                hit_stop = hi >= stop
                hit_target = lo <= target

            if hit_stop:  # conservative: stop wins ties (sub-bar precision handled live by resolver)
                exit_price = stop
                exit_reason, exit_idx = "stop", j
                break
            if hit_target:
                exit_price = target
                exit_reason, exit_idx = "target", j
                break

            # Opposite-signal flip, evaluated on the bar we just closed (j), acted next bar's open.
            if flip_on_opposite and j > i and j + 1 < n:
                jsig = score_row(rows.iloc[j], interval, weights=weights_override)
                opp = (direction == "long" and jsig.label in _SHORT_LABELS) or (
                    direction == "short" and jsig.label in _LONG_LABELS
                )
                if opp:
                    exit_price = opens[j + 1]
                    exit_reason, exit_idx = "flip", j + 1
                    break

            if j - i >= max_hold_bars:
                exit_price = opens[min(j + 1, n - 1)]
                exit_reason, exit_idx = "max_hold", min(j + 1, n - 1)
                break
            j += 1

        if exit_price is None:  # ran off the end while in position
            exit_price = opens[n - 1]
            exit_idx = n - 1

        if direction == "long":
            gross = (exit_price - entry) / entry
        else:
            gross = (entry - exit_price) / entry
        net = gross - cost  # per-market round-trip cost (fees + ATR/liquidity-scaled slippage)

        result.trades.append(
            Trade(
                direction=direction,
                entry_time=times[i],
                exit_time=times[exit_idx],
                entry_price=round(entry, 6),
                exit_price=round(exit_price, 6),
                net_return=round(net, 6),
                exit_reason=exit_reason,
                bars_held=exit_idx - i,
                mfe=round(mfe, 6),
                mae=round(mae, 6),
                confidence=sig.confidence,
            )
        )

        i = exit_idx + 1  # re-enter only after the position closes

    return result
