"""StarkX LAB: Core Data Models, Protocols, and Domain Types.

Strictly adheres to Section 1 Protocol & Dataclass specifications:
- Signal dataclass with exact attributes.
- Strategy Protocol with on_bar_close(ctx: MarketContext) -> list[Signal].
- Deterministic idempotent order / signal IDs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Protocol
import pandas as pd


@dataclass(frozen=True)
class Signal:
    """Canonical Lab Strategy Signal.
    
    Section 1 specification:
    strategy_id: str
    variant_id: str
    symbol: str
    direction: Literal['long', 'short']
    bar_open_time: datetime
    entry_mode: Literal['next_open', 'maker']
    stop_atr: float
    target_r: float | None
    trail_atr: float | None
    max_hold_bars: int
    meta: dict
    """
    strategy_id: str
    variant_id: str
    symbol: str
    direction: Literal["long", "short"]
    bar_open_time: datetime
    entry_mode: Literal["next_open", "maker"]
    stop_atr: float
    target_r: float | None
    trail_atr: float | None
    max_hold_bars: int
    meta: dict = field(default_factory=dict)

    @property
    def signal_id(self) -> str:
        """Deterministic fingerprint satisfying UNIQUE(strategy_id, variant_id, symbol, direction, bar_open_time)."""
        t_str = self.bar_open_time.isoformat() if hasattr(self.bar_open_time, "isoformat") else str(self.bar_open_time)
        raw = f"{self.strategy_id}:{self.variant_id}:{self.symbol}:{self.direction}:{t_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class MarketContext:
    """Point-in-time market context presented to a Strategy on bar close."""
    symbol: str
    timeframe: Literal["1h", "4h", "1d"]
    bars: pd.DataFrame  # OHLCV bars strictly closed before current time
    as_of: datetime
    funding_rate: float | None = None
    open_interest: float | None = None
    volume_rank: int = 15
    extra_data: Dict[str, Any] = field(default_factory=dict)


class Strategy(Protocol):
    """Canonical Lab Strategy Protocol per Section 1."""
    id: str
    timeframe: Literal["1h", "4h", "1d"]
    params: dict

    def on_bar_close(self, ctx: MarketContext) -> list[Signal]:
        ...


class OrderState(str, Enum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass
class LabPosition:
    """Virtual paper position per Rule 0.4 and 0.5."""
    position_id: str
    strategy_id: str
    variant_id: str
    symbol: str
    side: Literal["long", "short"]
    entry_mode: Literal["taker", "maker"]
    entry_price: float
    entry_time: datetime
    size_qty: float
    initial_stop: float            # Rule 0.4: initial_stop is IMMUTABLE
    trailing_stop: float | None     # Rule 0.4: trailing stops live in trailing_stop
    target_price: float | None
    risk_r_usd: float              # Rule 0.5: flat 0.5% risk ($50 on $10k)
    max_hold_bars: int = 48
    age_bars: int = 0
    unrealized_r: float = 0.0
    status: Literal["open", "closed"] = "open"
    exit_price: float | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None
    realized_r: float | None = None
    realized_pnl_usd: float | None = None
    fee_paid_usd: float = 0.0
    gst_paid_usd: float = 0.0
    slippage_usd: float = 0.0
    funding_paid_usd: float = 0.0
    twin_pnl_usd: float = 0.0      # Section 4 twin execution tracking
    is_backfill: bool = False      # Section 6 backfill flag
    warm_start: bool = False       # Flagged True if entered before next bar open; excluded from tier evidence

    @property
    def net_pnl_usd(self) -> float:
        gross = self.realized_pnl_usd if self.realized_pnl_usd is not None else 0.0
        return gross - (self.fee_paid_usd + self.gst_paid_usd + self.slippage_usd + self.funding_paid_usd)


@dataclass
class LabEvent:
    """Audit log entry for lab_events."""
    ts: str
    kind: Literal[
        "SIGNAL",
        "FILL",
        "EXIT",
        "PAUSE",
        "RETIRE",
        "SPAWN",
        "SWAP",
        "TIER_UP",
        "REJECTED_GEOMETRY",
        "FEED_STALE",
        "RECONCILIATION_BREAK",
        "JOB_FAILURE",
    ]
    variant_id: str | None
    message: str


def compute_lab_order_id(
    strategy_id: str,
    variant_id: str,
    symbol: str,
    direction: str,
    bar_open_time: datetime | str,
) -> str:
    """Rule 0.3 & 0.4: Idempotent order hash."""
    t_str = bar_open_time.isoformat() if hasattr(bar_open_time, "isoformat") else str(bar_open_time)
    raw = f"{strategy_id}:{variant_id}:{symbol}:{direction}:{t_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
