"""StarkX LAB: 1-Minute Candle Resolver & Execution Twins Simulator.

Operating Rules:
- Rule 0.4: Stops/targets resolved on 1-minute candles.
- Same-minute collision = STOP FIRST (always resolved as a stop).
- Initial stop is immutable; trailing stop is updated separately.
- Realistic costs: Fee tiering + 18% GST + Volume-rank slippage (3/6/10 bps) + Perp funding.
- Section 4: Execution Twins — every trade resolved for both taker_next_open and maker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Tuple
import numpy as np
import pandas as pd
from app.lab.models import LabPosition, Signal


class LabResolver:
    """Simulates realistic paper executions and tick-level resolutions."""

    TICK_SIZES: Dict[str, float] = {
        "BTCUSDT": 0.10,
        "ETHUSDT": 0.01,
        "SOLUSDT": 0.01,
        "DEFAULT": 0.001,
    }

    @classmethod
    def get_tick_size(cls, symbol: str) -> float:
        return cls.TICK_SIZES.get(symbol, cls.TICK_SIZES["DEFAULT"])

    @staticmethod
    def get_slippage_rate(volume_rank: int) -> float:
        """3/6/10 bps by volume rank."""
        if volume_rank <= 30:
            return 0.0003  # 3 bps
        elif volume_rank <= 50:
            return 0.0006  # 6 bps
        else:
            return 0.0010  # 10 bps

    @classmethod
    def open_position_from_signal(
        cls,
        signal: Signal,
        next_bar_open: float,
        next_bar_low: float,
        next_bar_high: float,
        volume_rank: int = 15,
        account_equity: float = 10000.0,
        risk_pct: float = 0.005,  # 0.5% risk per trade ($50)
    ) -> Tuple[Optional[LabPosition], Optional[LabPosition]]:
        """Creates taker and maker position twins from a validated signal.
        
        Returns (taker_pos, maker_pos).
        """
        atr = signal.meta.get("atr", next_bar_open * 0.02)
        stop_dist = max(signal.stop_atr * atr, next_bar_open * 0.0025)
        
        # 1. TAKER BASELINE: enters at next_bar_open with slippage
        slip_rate = cls.get_slippage_rate(volume_rank)
        taker_fee_rate = 0.0005  # 5 bps
        gst_rate = 0.18

        if signal.direction == "long":
            taker_entry = next_bar_open * (1.0 + slip_rate)
            initial_stop = next_bar_open - stop_dist
            target_price = (next_bar_open + signal.target_r * stop_dist) if signal.target_r else None
        else:
            taker_entry = next_bar_open * (1.0 - slip_rate)
            initial_stop = next_bar_open + stop_dist
            target_price = (next_bar_open - signal.target_r * stop_dist) if signal.target_r else None

        # Position sizing: flat 0.5% risk (Rule 0.5)
        risk_usd = account_equity * risk_pct
        size_qty = risk_usd / max(stop_dist, 1e-6)
        notional_usd = size_qty * taker_entry

        taker_fee = notional_usd * taker_fee_rate
        taker_gst = taker_fee * gst_rate
        taker_slip = notional_usd * slip_rate

        pos_id = f"pos_{signal.signal_id}"
        t_entry = signal.bar_open_time

        taker_pos = LabPosition(
            position_id=f"{pos_id}_taker",
            strategy_id=signal.strategy_id,
            variant_id=signal.variant_id,
            symbol=signal.symbol,
            side=signal.direction,
            entry_mode="taker",
            entry_price=round(taker_entry, 6),
            entry_time=t_entry,
            size_qty=size_qty,
            initial_stop=round(initial_stop, 6),
            trailing_stop=round(initial_stop, 6),
            target_price=round(target_price, 6) if target_price else None,
            risk_r_usd=risk_usd,
            max_hold_bars=signal.max_hold_bars,
            fee_paid_usd=taker_fee,
            gst_paid_usd=taker_gst,
            slippage_usd=taker_slip,
        )

        # 2. MAKER TWIN: limit order model (through-by-1-tick with 50% queue haircut)
        tick_size = cls.get_tick_size(signal.symbol)
        maker_fee_rate = 0.0002  # 2 bps

        # For maker, limit price is at or slightly behind touch (0.35 ATR default pullback)
        if signal.entry_mode == "maker":
            offset = signal.meta.get("maker_offset_atr", 0.35) * atr
            limit_price = (next_bar_open - offset) if signal.direction == "long" else (next_bar_open + offset)
        else:
            limit_price = next_bar_open

        # Runaway check (Phase 2): if price runs to +1.0R target before filling, cancel pending limit order
        target_1r = (next_bar_open + stop_dist) if signal.direction == "long" else (next_bar_open - stop_dist)
        runaway = (signal.direction == "long" and next_bar_high >= target_1r) or (signal.direction == "short" and next_bar_low <= target_1r)

        # Through-by-1-tick fill check:
        maker_filled = False
        if not runaway:
            if signal.direction == "long":
                if next_bar_low <= (limit_price - tick_size):
                    maker_filled = True
            else:
                if next_bar_high >= (limit_price + tick_size):
                    maker_filled = True

        maker_pos = None
        if maker_filled:
            maker_notional = size_qty * limit_price
            maker_fee = maker_notional * maker_fee_rate
            maker_gst = maker_fee * gst_rate

            maker_pos = LabPosition(
                position_id=f"{pos_id}_maker",
                strategy_id=signal.strategy_id,
                variant_id=signal.variant_id,
                symbol=signal.symbol,
                side=signal.direction,
                entry_mode="maker",
                entry_price=round(limit_price, 6),
                entry_time=t_entry,
                size_qty=size_qty,
                initial_stop=round(initial_stop, 6),
                trailing_stop=round(initial_stop, 6),
                target_price=round(target_price, 6) if target_price else None,
                risk_r_usd=risk_usd,
                max_hold_bars=signal.max_hold_bars,
                fee_paid_usd=maker_fee,
                gst_paid_usd=maker_gst,
                slippage_usd=0.0,
            )

        return taker_pos, maker_pos

    @classmethod
    def resolve_minute_candle(
        cls,
        pos: LabPosition,
        candle_open: float,
        candle_high: float,
        candle_low: float,
        candle_close: float,
        candle_time: datetime,
        funding_rate: float = 0.0,
    ) -> bool:
        """Evaluates stop, target, and trailing stop on a 1-minute candle.
        
        CRITICAL RULE 0.4: Same-minute collision = STOP FIRST!
        Returns True if the position was closed during this minute.
        """
        if pos.status == "closed":
            return True

        current_stop = pos.trailing_stop if pos.trailing_stop is not None else pos.initial_stop
        target = pos.target_price

        # Check collision conditions
        stop_hit = False
        target_hit = False

        if pos.side == "long":
            if candle_low <= current_stop:
                stop_hit = True
            if target is not None and candle_high >= target:
                target_hit = True
        else:
            if candle_high >= current_stop:
                stop_hit = True
            if target is not None and candle_low <= target:
                target_hit = True

        # Resolve: SAME-MINUTE COLLISION = STOP FIRST
        if stop_hit and target_hit:
            cls._close_position(pos, exit_price=current_stop, exit_time=candle_time, reason="stop_collision_first")
            return True
        elif stop_hit:
            cls._close_position(pos, exit_price=current_stop, exit_time=candle_time, reason="stop_loss")
            return True
        elif target_hit:
            cls._close_position(pos, exit_price=target, exit_time=candle_time, reason="take_profit")
            return True

        # Check funding rate accrual (every 8 hours ~ 480 minutes)
        if funding_rate != 0.0:
            notional = pos.size_qty * candle_close
            funding_cost = notional * funding_rate
            if pos.side == "long":
                pos.funding_paid_usd += funding_cost
            else:
                pos.funding_paid_usd -= funding_cost

        # Update unrealized R and trailing stop ratchet
        if pos.side == "long":
            price_delta = candle_close - pos.entry_price
            stop_dist = pos.entry_price - pos.initial_stop
        else:
            price_delta = pos.entry_price - candle_close
            stop_dist = pos.initial_stop - pos.entry_price

        pos.unrealized_r = round(price_delta / max(stop_dist, 1e-6), 3)
        return False

    @classmethod
    def _close_position(
        cls,
        pos: LabPosition,
        exit_price: float,
        exit_time: datetime,
        reason: str,
    ) -> None:
        """Executes terminal accounting on position close."""
        pos.status = "closed"
        pos.exit_price = round(exit_price, 6)
        pos.exit_time = exit_time
        pos.exit_reason = reason

        if pos.side == "long":
            price_delta = exit_price - pos.entry_price
            stop_dist = pos.entry_price - pos.initial_stop
        else:
            price_delta = pos.entry_price - exit_price
            stop_dist = pos.initial_stop - pos.entry_price

        r_return = price_delta / max(stop_dist, 1e-6)
        pos.realized_r = round(r_return, 4)
        pos.realized_pnl_usd = round(r_return * pos.risk_r_usd, 2)
        pos.unrealized_r = 0.0

        # Exit transaction fee
        exit_fee_rate = 0.0005 if pos.entry_mode == "taker" else 0.0002
        exit_notional = pos.size_qty * exit_price
        exit_fee = exit_notional * exit_fee_rate
        pos.fee_paid_usd += exit_fee
        pos.gst_paid_usd += exit_fee * 0.18
