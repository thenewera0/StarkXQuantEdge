"""StarkX QuantEdge v2: Execution Engine, Paper Broker & Live Adapter Stub.

Operating Rules:
- Rule 0.2: LIVE_TRADING_ENABLED stays False. Add V2_LIVE_ENABLED=false.
  The v2 live adapter is an interface plus a stub that raises NotImplementedError.
  The agent must never set, document how to bypass, or auto-enable any live flag.
- Rule 0.3: All decisions run on CLOSED daily bars (00:05 UTC after the 00:00 close).
  Order ids are idempotent: id = sha256(sleeve, asset, bar_open_time, side), UNIQUE-constrained.
- Section 5: State machine NEW -> SUBMITTED -> PARTIAL -> FILLED | CANCELLED | EXPIRED.
  Maker-first: post-only limit at the touch, reprice every 5 minutes up to 6 times,
  cross as taker only if the target delta is still open and fewer than 30 minutes
  remain in the 4-hour execution window.
  Paper fills use the through-by-1-tick rule with a 50% queue haircut.
  Costs: fee tier from config (FEE_*_BPS) with a 30-day-volume tier tracker,
  18% GST on fees, slippage 3/6/10 bps by volume rank (<=30, 31-50, 51-100),
  funding for perps.
  Weekly tracking-error report: paper fills versus ideal daily-close fills.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.v2.config import settings_v2
from app.v2.models import compute_order_id


class OrderState(str, Enum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT_POST_ONLY = "LIMIT_POST_ONLY"
    MARKET_TAKER = "MARKET_TAKER"


@dataclass
class Order:
    order_id: str
    sleeve: str
    asset: str
    bar_open_time: str
    side: OrderSide
    order_type: OrderType
    target_qty: float
    limit_price: float
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    state: OrderState = OrderState.NEW
    reprice_count: int = 0  # Reprice every 5 mins up to 6 times
    elapsed_minutes: float = 0.0  # Out of 240 mins (4-hour window)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fee_paid_usd: float = 0.0
    gst_paid_usd: float = 0.0
    slippage_usd: float = 0.0
    asset_volume_rank: int = 15

    @property
    def remaining_qty(self) -> float:
        return max(0.0, self.target_qty - self.filled_qty)


class LiveExecutionAdapter(ABC):
    """Abstract interface for live order execution (Strictly unimplemented in paper engine)."""

    @abstractmethod
    def place_order(self, order: Order) -> dict:
        """Place live order on venue."""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict:
        """Cancel live order on venue."""
        raise NotImplementedError

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict:
        """Query live order status."""
        raise NotImplementedError


class V2LiveStubAdapter(LiveExecutionAdapter):
    """Rule 0.2: Non-operational live adapter stub.
    
    Strictly raises NotImplementedError on all invocations.
    Guarantees no live trade execution can be reached under any circumstances.
    """

    def place_order(self, order: Order) -> dict:
        if not settings_v2.v2_live_enabled:
            raise NotImplementedError(
                "Rule 0.2 Violation Attempt: V2_LIVE_ENABLED is False. "
                "Live trading adapter is a stub and cannot place orders."
            )
        raise NotImplementedError("Live execution adapter is not implemented.")

    def cancel_order(self, order_id: str) -> dict:
        raise NotImplementedError("Live execution adapter is not implemented.")

    def get_order_status(self, order_id: str) -> dict:
        raise NotImplementedError("Live execution adapter is not implemented.")


class VolumeTierTracker:
    """Tracks 30-day trailing traded volume to determine maker/taker fee tiers."""

    def __init__(self):
        self.trade_records: List[Tuple[datetime, float]] = []

    def record_trade(self, dt: datetime, notional_usd: float) -> None:
        self.trade_records.append((dt, abs(notional_usd)))

    def get_30d_volume(self, current_dt: datetime) -> float:
        cutoff = current_dt - pd.Timedelta(days=30)
        recent = [notional for (t, notional) in self.trade_records if t >= cutoff]
        return sum(recent)

    def get_fee_bps(self, current_dt: datetime) -> Tuple[float, float]:
        """Returns (maker_fee_bps, taker_fee_bps) based on 30-day volume."""
        vol_30d = self.get_30d_volume(current_dt)
        if vol_30d >= 1_000_000.0:
            return 1.0, 3.0  # Tier 3 (>= $1M)
        elif vol_30d >= 100_000.0:
            return 1.5, 4.0  # Tier 2 ($100k-$1M)
        else:
            return settings_v2.fee_maker_bps, settings_v2.fee_taker_bps  # Tier 1 (<$100k) default


class PaperBroker:
    """Systematic Paper Execution Engine.
    
    Implements:
    - Order state machine: NEW -> SUBMITTED -> PARTIAL -> FILLED | CANCELLED | EXPIRED
    - Maker-first post-only limit at touch
    - Reprice every 5 mins up to 6 times
    - Cross as taker if remaining delta > 0 and < 30 mins in 4h window
    - Through-by-1-tick fill rule with 50% queue haircut
    - Fee tiering + 18% GST + rank-based slippage
    - Weekly tracking error computation vs ideal daily-close fills
    """

    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.volume_tracker = VolumeTierTracker()
        self.tick_sizes: Dict[str, float] = {
            "BTC": 0.10,
            "ETH": 0.01,
            "SOL": 0.01,
            "DEFAULT": 0.001,
        }

    def get_tick_size(self, asset: str) -> float:
        clean = asset.replace("USDT", "").replace("/USDT", "")
        return self.tick_sizes.get(clean, self.tick_sizes["DEFAULT"])

    def get_slippage_bps(self, volume_rank: int) -> float:
        if volume_rank <= 30:
            return settings_v2.slippage_bps_tier1  # 3 bps
        elif volume_rank <= 50:
            return settings_v2.slippage_bps_tier2  # 6 bps
        else:
            return settings_v2.slippage_bps_tier3  # 10 bps

    def create_order(
        self,
        sleeve: str,
        asset: str,
        bar_open_time: str,
        side: OrderSide,
        target_qty: float,
        limit_price: float,
        asset_volume_rank: int = 15,
    ) -> Order:
        """Create idempotent order adhering to Rule 0.3 unique constraint."""
        order_id = compute_order_id(sleeve, asset, bar_open_time, side.value)
        if order_id in self.orders:
            return self.orders[order_id]

        order = Order(
            order_id=order_id,
            sleeve=sleeve,
            asset=asset,
            bar_open_time=bar_open_time,
            side=side,
            order_type=OrderType.LIMIT_POST_ONLY,
            target_qty=target_qty,
            limit_price=limit_price,
            asset_volume_rank=asset_volume_rank,
            state=OrderState.NEW,
        )
        self.orders[order_id] = order
        return order

    def submit_order(self, order_id: str) -> Order:
        order = self.orders[order_id]
        if order.state == OrderState.NEW:
            order.state = OrderState.SUBMITTED
            order.updated_at = datetime.now(timezone.utc)
        return order

    def reprice_order(self, order_id: str, new_limit_price: float) -> Order:
        """Reprice maker order at the new touch up to 6 times (every 5 mins)."""
        order = self.orders[order_id]
        if order.state not in (OrderState.SUBMITTED, OrderState.PARTIAL):
            return order

        if order.reprice_count < 6:
            order.reprice_count += 1
            order.limit_price = new_limit_price
            order.elapsed_minutes += 5.0
            order.updated_at = datetime.now(timezone.utc)
        return order

    def simulate_bar_execution(
        self,
        order_id: str,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        current_time: datetime,
        bar_duration_minutes: float = 60.0,
    ) -> Order:
        """Executes paper fill logic using through-by-1-tick with 50% queue haircut."""
        order = self.orders[order_id]
        if order.state in (OrderState.FILLED, OrderState.CANCELLED, OrderState.EXPIRED):
            return order

        if order.state == OrderState.NEW:
            order.state = OrderState.SUBMITTED

        tick = self.get_tick_size(order.asset)
        maker_bps, taker_bps = self.volume_tracker.get_fee_bps(current_time)
        slippage_bps = self.get_slippage_bps(order.asset_volume_rank)

        # Check if we must cross as taker:
        # 4-hour window = 240 mins. If fewer than 30 mins remain (elapsed >= 210 mins)
        # and target delta is still open, cross as taker at market.
        order.elapsed_minutes += bar_duration_minutes
        must_taker_cross = (order.elapsed_minutes >= 210.0) and (order.remaining_qty > 0)

        if must_taker_cross:
            # Cross as taker
            rem_qty = order.remaining_qty
            if order.side == OrderSide.BUY:
                exec_price = bar_close * (1.0 + slippage_bps / 10000.0)
            else:
                exec_price = bar_close * (1.0 - slippage_bps / 10000.0)

            notional = rem_qty * exec_price
            fee = notional * (taker_bps / 10000.0)
            gst = fee * settings_v2.gst_rate
            slip = notional * (slippage_bps / 10000.0)

            total_cost_usd = (order.avg_fill_price * order.filled_qty) + (exec_price * rem_qty)
            order.filled_qty += rem_qty
            order.avg_fill_price = total_cost_usd / order.filled_qty
            order.fee_paid_usd += fee
            order.gst_paid_usd += gst
            order.slippage_usd += slip
            order.order_type = OrderType.MARKET_TAKER
            order.state = OrderState.FILLED
            order.updated_at = current_time
            self.volume_tracker.record_trade(current_time, notional)
            return order

        # Otherwise, maker execution at limit_price
        fill_fraction = 0.0
        if order.side == OrderSide.BUY:
            if bar_low <= (order.limit_price - tick):
                # Penetrated through by >= 1 tick -> 100% fill
                fill_fraction = 1.0
            elif math.isclose(bar_low, order.limit_price, abs_tol=tick):
                # Touched exactly -> 50% queue haircut
                fill_fraction = 0.50
        else:  # SELL
            if bar_high >= (order.limit_price + tick):
                # Penetrated through by >= 1 tick -> 100% fill
                fill_fraction = 1.0
            elif math.isclose(bar_high, order.limit_price, abs_tol=tick):
                # Touched exactly -> 50% queue haircut
                fill_fraction = 0.50

        if fill_fraction > 0.0:
            qty_to_fill = order.remaining_qty * fill_fraction
            if qty_to_fill > 0:
                exec_price = order.limit_price
                notional = qty_to_fill * exec_price
                fee = notional * (maker_bps / 10000.0)
                gst = fee * settings_v2.gst_rate
                # Maker post-only earns touch price with 0 slippage
                slip = 0.0

                new_filled = order.filled_qty + qty_to_fill
                order.avg_fill_price = (
                    (order.avg_fill_price * order.filled_qty) + (exec_price * qty_to_fill)
                ) / new_filled
                order.filled_qty = new_filled
                order.fee_paid_usd += fee
                order.gst_paid_usd += gst
                order.slippage_usd += slip
                self.volume_tracker.record_trade(current_time, notional)

                if math.isclose(order.filled_qty, order.target_qty, rel_tol=1e-5):
                    order.state = OrderState.FILLED
                else:
                    order.state = OrderState.PARTIAL

        # If execution window expired (> 240 mins) and not filled, mark EXPIRED
        if order.elapsed_minutes >= 240.0 and order.state != OrderState.FILLED:
            order.state = OrderState.EXPIRED if order.filled_qty == 0 else OrderState.PARTIAL

        order.updated_at = current_time
        return order


def compute_weekly_tracking_error(
    paper_returns: pd.Series,
    ideal_close_returns: pd.Series,
) -> float:
    """Computes annualized tracking error between paper broker fills and ideal daily-close fills.
    
    Tracking error = std(r_paper - r_ideal) * sqrt(365).
    Stage B -> Stage C evidence gate requires tracking error <= 1.5% (0.015).
    """
    if len(paper_returns) < 5 or len(ideal_close_returns) < 5:
        return 0.0
    diff = paper_returns - ideal_close_returns
    diff = diff.dropna()
    daily_std = float(diff.std(ddof=1))
    ann_te = daily_std * math.sqrt(365.0)
    return ann_te
