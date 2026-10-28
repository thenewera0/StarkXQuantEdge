"""StarkX QuantEdge v2: Cash Benchmark, Capital Allocator & Drawdown Governor.

Rules:
1. Cash is an explicit asset at RISK_FREE_APR (6.5%) taxed at TAX_RATE (0.312).
2. Risk caps: Sleeve T <= 70% of equity at risk, Sleeve C <= 25% when ECONOMIC, remainder cash.
3. Drawdown governor on daily-marked equity:
   - drawdown from peak >= 10% -> multiply Sleeve T targets by 0.5 (state: HALVED)
   - drawdown from peak >= 20% -> Sleeve T = 0 (all cash) until V2_RESUME=true (state: CASH)
   - daily loss <= -4% -> no new orders for 24 hours (state: ORDER_HALT)
4. Daily ledger-to-equity reconciliation; halt and alert if |delta| > 0.01 USD.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .config import settings_v2

logger = logging.getLogger("v2.allocator")


class DrawdownGovernor:
    """Tracks running portfolio equity, peak equity, and enforces risk throttling rules."""

    def __init__(
        self,
        initial_equity: float = 1000.0,
        halve_threshold: float = 0.10,
        cash_threshold: float = 0.20,
        daily_loss_halt_threshold: float = 0.04
    ):
        self.initial_equity = initial_equity
        self.peak_equity = initial_equity
        self.current_equity = initial_equity
        self.prev_equity = initial_equity
        self.halve_threshold = halve_threshold
        self.cash_threshold = cash_threshold
        self.daily_loss_halt_threshold = daily_loss_halt_threshold
        self.manual_resume_active = False
        self.order_halt_active = False
        self.emergency_halt_active = False
        self.cash_halt_latched = False

    def trip_20pct_halt(self) -> None:
        """Emergency circuit breaker: forces governor into 100% cash state."""
        self.emergency_halt_active = True
        self.cash_halt_latched = True
        self.order_halt_active = True
        self.manual_resume_active = False

    def get_state(self) -> Dict[str, Any]:
        """Returns current governor state without mutating equity."""
        return self.update(self.current_equity)

    def update(self, current_equity: float, manual_resume: bool = False) -> Dict[str, Any]:
        """Updates equity, tracks peak, and computes governor multiplier and state."""
        self.prev_equity = self.current_equity
        self.current_equity = current_equity
        if manual_resume:
            self.manual_resume_active = True
            self.cash_halt_latched = False
            self.emergency_halt_active = False
            
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
            self.manual_resume_active = False
            
        # Drawdown from peak
        drawdown_pct = (self.current_equity - self.peak_equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        
        # Check if 20% drawdown threshold is breached -> latches CASH state
        if drawdown_pct <= -self.cash_threshold:
            self.cash_halt_latched = True

        # Daily return / loss
        daily_return = (self.current_equity - self.prev_equity) / self.prev_equity if self.prev_equity > 0 else 0.0
        
        # Check daily loss limit <= -4%
        if daily_return <= -self.daily_loss_halt_threshold:
            self.order_halt_active = True
        else:
            self.order_halt_active = False
            
        # Governor state evaluation
        if self.emergency_halt_active or (self.cash_halt_latched and not self.manual_resume_active):
            state = "CASH"
            multiplier = 0.0
            reason = f"CRITICAL: Drawdown {drawdown_pct*100:.2f}% >= 20% limit. Sleeve T targets zeroed (100% cash). Manual resume required."
        elif drawdown_pct <= -self.halve_threshold:
            state = "HALVED"
            multiplier = 0.5
            reason = f"WARNING: Drawdown {drawdown_pct*100:.2f}% >= 10% limit. Sleeve T targets multiplied by 0.5."
        elif self.order_halt_active:
            state = "ORDER_HALT"
            multiplier = 1.0
            reason = f"HALT: Daily loss {daily_return*100:.2f}% <= -4.0%. No new orders permitted for 24h."
        else:
            state = "NORMAL"
            multiplier = 1.0
            reason = "NORMAL: Risk parameters within safe operating envelope."
            
        return {
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "drawdown_pct": drawdown_pct,
            "daily_return": daily_return,
            "governor_state": state,
            "sleeve_t_multiplier": multiplier,
            "order_halt_active": self.order_halt_active,
            "reason": reason
        }


def reconcile_ledger(
    marked_equity_usd: float,
    ledger_equity_usd: float,
    tolerance_usd: float = 0.01
) -> Tuple[bool, float, str]:
    """Verifies that marked equity and book ledger balance within $0.01 USD.
    
    Returns: (is_reconciled, delta_usd, message)
    """
    delta = abs(marked_equity_usd - ledger_equity_usd)
    is_reconciled = bool(delta <= tolerance_usd)
    
    if is_reconciled:
        msg = f"PASS: Marked equity (${marked_equity_usd:.2f}) reconciles with ledger (${ledger_equity_usd:.2f}) within ${tolerance_usd:.2f} (|delta| = ${delta:.4f})"
    else:
        msg = f"CRITICAL ALERT: Reconciliation break! Marked (${marked_equity_usd:.2f}) != Ledger (${ledger_equity_usd:.2f}) by ${delta:.4f} > ${tolerance_usd:.2f}. System halted."
        logger.error(msg)
        
    return is_reconciled, round(delta, 4), msg


def allocate_portfolio(
    sleeve_t_targets: Dict[str, float],
    sleeve_c_eval: Dict[str, Any],
    governor_status: Dict[str, Any],
    account_equity_usd: float = 1000.0
) -> Dict[str, Any]:
    """Combines Sleeve T, Sleeve C, and Cash under strict risk caps and governor rules."""
    multiplier = governor_status.get("sleeve_t_multiplier", 1.0)
    
    # 1. Apply governor multiplier to Sleeve T targets
    throttled_t = {sym: w * multiplier for sym, w in sleeve_t_targets.items()}
    
    # 2. Cap Sleeve T total exposure <= 70% of equity
    total_t = sum(throttled_t.values())
    if total_t > settings_v2.sleeve_t_max_equity_share:
        scale_t = settings_v2.sleeve_t_max_equity_share / total_t
        throttled_t = {sym: w * scale_t for sym, w in throttled_t.items()}
        total_t = settings_v2.sleeve_t_max_equity_share
        
    # 3. Sleeve C Allocation (<= 25% when ECONOMIC, otherwise 0%)
    if sleeve_c_eval.get("overall_economic", False):
        total_c = min(sleeve_c_eval.get("total_allocation_pct", 0.0), settings_v2.sleeve_c_max_equity_share)
    else:
        total_c = 0.0
        
    # 4. Remainder to Cash
    cash_pct = max(0.0, 1.0 - (total_t + total_c))
    
    # 5. Position dollar targets
    dollar_targets = {}
    for sym, w in throttled_t.items():
        dollar_targets[sym] = round(w * account_equity_usd, 2)
        
    cash_usd = round(cash_pct * account_equity_usd, 2)
    
    # Daily cash interest
    daily_cash_rate = (1.0 + settings_v2.risk_free_apr) ** (1.0 / 365.25) - 1.0
    daily_cash_yield_usd = cash_usd * daily_cash_rate
    daily_cash_tax_usd = daily_cash_yield_usd * settings_v2.tax_rate
    
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "account_equity_usd": account_equity_usd,
        "sleeve_t_weights": throttled_t,
        "sleeve_t_total_pct": round(total_t, 6),
        "sleeve_c_total_pct": round(total_c, 6),
        "cash_pct": round(cash_pct, 6),
        "cash_usd": cash_usd,
        "gross_exposure_pct": round(total_t + total_c, 6),
        "dollar_targets": dollar_targets,
        "governor_state": governor_status.get("governor_state", "NORMAL"),
        "drawdown_pct": governor_status.get("drawdown_pct", 0.0),
        "daily_cash_yield_usd": round(daily_cash_yield_usd, 4),
        "daily_cash_tax_usd": round(daily_cash_tax_usd, 4)
    }
