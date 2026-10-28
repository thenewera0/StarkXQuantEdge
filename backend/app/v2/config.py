"""StarkX QuantEdge v2: Configuration, Invariant Constraints & Operational Rules.

Rule 0.2: LIVE_TRADING_ENABLED stays False. Add V2_LIVE_ENABLED=false.
The v2 live adapter is an interface plus a stub that raises NotImplementedError.
The agent must never set, document how to bypass, or auto-enable any live flag.
"""

from __future__ import annotations

import os
from pydantic import BaseModel, Field


class V2Settings(BaseModel):
    # Rule 0.2: Live Trading Locks
    v2_live_enabled: bool = Field(default=False, description="Strictly False for v2 paper engine")
    v2_allow_short: bool = Field(default=False, description="Shorts disabled; long/flat only")
    
    # Sleeve T: Volatility Targeting & Sizing
    sigma_target: float = Field(default=0.15, description="Annualized portfolio target vol (default 15%)")
    vol_floor: float = Field(default=0.20, description="Per-asset annualized vol floor (20%)")
    vol_halflife_days: float = Field(default=30.0, description="EWMA vol halflife in days")
    max_asset_weight: float = Field(default=0.25, description="Maximum single-asset weight cap (25%)")
    gross_exposure_cap: float = Field(default=1.00, description="Maximum gross portfolio exposure (1.0 = no leverage)")
    sleeve_t_max_equity_share: float = Field(default=0.70, description="Max 70% of equity at risk in Sleeve T")
    
    # No-trade Band & Sizing Limits
    no_trade_band_pct: float = Field(default=0.20, description="20% relative threshold of target weight")
    no_trade_band_abs: float = Field(default=0.02, description="2.0% absolute weight threshold")
    min_notional_usd: float = Field(default=10.0, description="Minimum order notional in USD ($10)")
    account_equity_usd: float = Field(default=1000.0, description="Nominal account equity ($1,000 USD)")
    
    # Sleeve C: Carry Arbitrage & Liquidation Protection
    sleeve_c_max_equity_share: float = Field(default=0.25, description="Max 25% of equity in Sleeve C")
    max_venue_share_carry: float = Field(default=0.15, description="Max 15% per venue in Sleeve C")
    liquidation_buffer_atr_mult: float = Field(default=3.0, description="Perp-leg liquidation buffer >= 3x ATR(1d)")
    carry_hurdle_spread_apr: float = Field(default=0.02, description="2.0% spread over risk-free rate")
    carry_liquidation_premium_apr: float = Field(default=0.02, description="2.0% counterparty/liquidation risk premium")
    carry_rebalance_drag_apr: float = Field(default=0.005, description="0.5% annualized dynamic rebalancing drag")
    
    # Cash Benchmark & Statutory Tax Rates
    risk_free_apr: float = Field(default=0.065, description="Benchmark risk-free rate (6.5% APR)")
    tax_rate: float = Field(default=0.312, description="Statutory tax rate (30% + 4% cess = 31.2%)")
    tds_rate: float = Field(default=0.01, description="Section 194S TDS cash-flow withholding (1.0%)")
    gst_rate: float = Field(default=0.18, description="Goods and Services Tax on platform fees (18.0%)")
    
    # Platform Costs & Execution
    fee_maker_bps: float = Field(default=2.0, description="Maker fee in bps (0.02%)")
    fee_taker_bps: float = Field(default=5.0, description="Taker fee in bps (0.05%)")
    slippage_bps_tier1: float = Field(default=3.0, description="Slippage for rank 1-30 coins (3 bps)")
    slippage_bps_tier2: float = Field(default=6.0, description="Slippage for rank 31-50 coins (6 bps)")
    slippage_bps_tier3: float = Field(default=10.0, description="Slippage for rank 51-100 coins (10 bps)")
    
    # Risk Governor Thresholds
    drawdown_halve_threshold: float = Field(default=0.10, description="10% drawdown from peak -> halve targets")
    drawdown_cash_threshold: float = Field(default=0.20, description="20% drawdown from peak -> 100% cash")
    daily_loss_halt_threshold: float = Field(default=0.04, description="Daily loss <= -4% -> halt orders 24h")
    reconcile_tolerance_usd: float = Field(default=0.01, description="Ledger delta halt threshold ($0.01 USD)")
    v2_resume: bool = Field(default=False, description="Manual resume switch following 20% DD halt")
    
    # Stage D: Micro-Live Constraints (Owner Action Only)
    v2_max_capital_usd: float = Field(default=100.0, description="Micro-live capital cap ($100 USD)")
    v2_max_daily_loss_pct: float = Field(default=2.0, description="Micro-live max daily loss (2.0%)")
    v2_max_drawdown_pct: float = Field(default=15.0, description="Micro-live max drawdown (15.0%)")
    v2_kill_switch_secret: str = Field(
        default="starkx-v2-hmac-kill-switch-secret",
        description="HMAC secret for micro-live emergency shutdown"
    )


settings_v2 = V2Settings()
