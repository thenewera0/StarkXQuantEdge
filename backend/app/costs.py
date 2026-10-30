"""Per-market transaction-cost model (Blueprint v2 §2.8 & Phase 0.4 Truth-First Edge Rehabilitation).

Every realized/backtested P&L number is only as honest as the cost assumed. This module provides:
1. Venue/product specific fees from config (spot maker/taker, perp maker/taker).
2. Conservative stop/timeout taker slippage = max(depth_model_slippage, 0.5 * spread) + STOP_EXTRA_SLIPPAGE_BPS.
3. Perp funding paid/received over holding period (8h settlements). Spot has no funding.
4. Cost in R units: cost_R = total_cost_pct / stop_distance_pct.
"""

from __future__ import annotations

import math
from typing import Dict, Any
from .config import settings

# --- Crypto liquidity tiers (Binance USDT pairs) ---------------------------
# tier -> (base_slip_per_side, vol_slip_coef, spread)
_CRYPTO_TIERS = {
    "major": (0.0001, 0.02, 0.0001),   # BTC, ETH — deep books (~1 bps spread)
    "large": (0.0002, 0.03, 0.0002),   # SOL, BNB, XRP — liquid (~2 bps spread)
    "alt":   (0.0004, 0.05, 0.0004),   # altcoins — thinner books (~4 bps spread)
}
_CRYPTO_MAJORS = {"BTCUSDT", "ETHUSDT", "BTCUSD", "ETHUSD"}
_CRYPTO_LARGE = {"SOLUSDT", "BNBUSDT", "XRPUSDT", "SOLUSD", "BNBUSD", "XRPUSD"}

# --- Forex / metals round-trip spread (fraction of price) ------------------
_FOREX_MAJOR = 0.00010   # EUR/USD, GBP/USD, USD/JPY ... ~1 pip round trip
_FOREX_CROSS = 0.00020   # crosses
_FOREX_METAL = 0.00035   # XAU/USD, XAG/USD — wider
_FOREX_MAJORS = {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD"}
_METALS = {"XAU/USD", "XAG/USD", "XAUUSD", "XAGUSD"}

_CRYPTO_MARKETS = {"crypto"}


def _crypto_tier(symbol: str) -> str:
    s = (symbol or "").upper()
    if s in _CRYPTO_MAJORS:
        return "major"
    if s in _CRYPTO_LARGE:
        return "large"
    return "alt"


def _forex_spread(symbol: str) -> float:
    s = (symbol or "").upper()
    if s in _METALS:
        return _FOREX_METAL
    if s in _FOREX_MAJORS:
        return _FOREX_MAJOR
    return _FOREX_CROSS


def trade_cost(
    market: str,
    symbol: str,
    atr_pct: float = 0.0,
    *,
    is_perp: bool = True,
    entry_execution: str = "maker",
    exit_result: str = "stop",
    direction: str = "long",
    holding_hours: float = 0.0,
    funding_rate_8h: float = 0.0001,  # default 0.01% baseline 8h funding
) -> float:
    """Compute exact total round-trip transaction cost (fraction of notional).

    Includes:
    - Entry fee: maker (2 bps perp / 10 bps spot) vs taker (5 bps perp / 10 bps spot)
    - Entry slippage: 0 for maker; depth slippage for taker
    - Exit fee: maker (if target limit) vs taker (if stop/timeout/market)
    - Exit slippage: 0 for maker target; max(depth_slip, 0.5*spread) + STOP_EXTRA_SLIPPAGE_BPS (3 bps) for stops
    - Funding cost for perps: accrued across 8h settlement periods
    """
    atr_pct = min(max(float(atr_pct or 0.0), 0.0), 0.15)
    is_crypto = (market or "crypto").lower() in _CRYPTO_MARKETS

    if not is_crypto:
        # Forex: spread-dominated
        return round(_forex_spread(symbol), 8)

    # 1. Fees from settings
    if is_perp:
        fee_maker = settings.fee_perp_maker_bps / 10000.0  # 0.0002 (2 bps)
        fee_taker = settings.fee_perp_taker_bps / 10000.0  # 0.0005 (5 bps)
    else:
        fee_maker = settings.fee_spot_maker_bps / 10000.0  # 0.0010 (10 bps)
        fee_taker = settings.fee_spot_taker_bps / 10000.0  # 0.0010 (10 bps)

    stop_extra_slip = settings.stop_extra_slippage_bps / 10000.0  # 0.0003 (3 bps)

    # 2. Slippage & spread
    base_slip, vol_coef, spread = _CRYPTO_TIERS[_crypto_tier(symbol)]
    depth_slip = base_slip + vol_coef * atr_pct
    taker_slip = max(depth_slip, 0.5 * spread)

    # Entry leg
    if entry_execution.lower() == "maker":
        entry_cost = fee_maker
    else:
        entry_cost = fee_taker + taker_slip

    # Exit leg
    if exit_result.lower() == "target":
        # Target limit order is maker
        exit_cost = fee_maker
    else:
        # Stops, timeouts, stagnation: TAKER exit with extra slippage
        exit_cost = fee_taker + taker_slip + stop_extra_slip

    # 3. Funding cost (perps only)
    funding_cost = 0.0
    if is_perp and holding_hours > 0:
        periods = holding_hours / 8.0
        # Long pays positive funding, short receives positive funding
        sign = 1.0 if direction.lower() == "long" else -1.0
        funding_cost = sign * funding_rate_8h * periods

    total_cost = entry_cost + exit_cost + funding_cost
    return round(max(total_cost, 0.0), 8)


def round_trip_cost(
    market: str,
    symbol: str,
    atr_pct: float = 0.0,
    execution: str = "taker",
) -> float:
    """Standard round-trip cost (entry + exit) as a fraction of notional.

    Maintained for backwards-compatibility across the app:
    - "maker": resting limit entry and exit (2 * maker_fee, crosses no spread, zero ATR slippage).
    - "taker": market entry and exit (2 * (taker_fee + depth_slippage)).
    """
    atr_pct = min(max(float(atr_pct or 0.0), 0.0), 0.15)
    if (market or "crypto").lower() in _CRYPTO_MARKETS:
        fee_maker = settings.fee_perp_maker_bps / 10000.0
        fee_taker = settings.fee_perp_taker_bps / 10000.0
        if (execution or "taker").lower() == "maker":
            return round(2.0 * fee_maker, 8)
        base_slip, vol_coef, spread = _CRYPTO_TIERS[_crypto_tier(symbol)]
        depth_slip = base_slip + vol_coef * atr_pct
        taker_slip = max(depth_slip, 0.5 * spread)
        return round(2.0 * (fee_taker + taker_slip), 8)
    return round(_forex_spread(symbol), 8)



def cost_in_r(
    market: str,
    symbol: str,
    atr_pct: float,
    stop_frac: float,
    execution: str = "taker",
    *,
    is_perp: bool = False,
    exit_result: str = "standard",
    direction: str = "long",
    holding_hours: float = 0.0,
    funding_rate_8h: float = 0.0001,
) -> float:
    """Round-trip cost expressed in R units: total_cost / stop_frac.

    Used by the EV gate and R-unit accounting.
    Returns float('inf') if stop_frac <= 0.
    """
    if not stop_frac or stop_frac <= 0:
        return float("inf")
    if exit_result == "standard" and not is_perp:
        cost = round_trip_cost(market, symbol, atr_pct, execution)
    else:
        cost = trade_cost(
            market=market,
            symbol=symbol,
            atr_pct=atr_pct,
            is_perp=is_perp,
            entry_execution=execution,
            exit_result=exit_result,
            direction=direction,
            holding_hours=holding_hours,
            funding_rate_8h=funding_rate_8h,
        )
    return cost / float(stop_frac)


def compute_after_tax_ev(
    p_win: float,
    reward_r: float,
    cost_r: float,
    tax_mode: str = "115bbh_netted",
    tax_rate: float = 0.312,
    gst_rate: float = 0.18,
) -> float:
    """Compute after-tax expected value (in R-multiples) under Indian Section 115BBH (Crypto) vs Section 43(5) (NSE F&O).

    - Crypto Section 115BBH Scenario A (zero loss offset): EV = p * (1 - 0.312) * (reward_r - effective_cost_r) - (1 - p) * (1 + effective_cost_r).
    - Crypto Section 115BBH Scenario B (netted): pre_tax * (1 - 0.312) if pre_tax > 0 else pre_tax.
    - NSE F&O Section 43(5) Scenario C (netted business income with loss carry-forward & full expense deduction):
      Trading losses offset gains 100%, and all fees/STT/GST are tax-deductible expenses.
    """
    effective_cost_r = cost_r * (1.0 + gst_rate)

    if tax_mode in ("115bbh_scenario_a", "scenario_a", "gross_flat"):
        ev_win = p_win * (1.0 - tax_rate) * max(0.0, reward_r - effective_cost_r)
        ev_loss = (1.0 - p_win) * (1.0 + effective_cost_r)
        return round(ev_win - ev_loss, 4)
    elif tax_mode in ("scenario_c", "43_5_netted", "nse_business"):
        # Section 43(5): 100% loss offset + full fee/STT deduction against gross business income
        pre_tax_ev = p_win * reward_r - (1.0 - p_win) * 1.0 - effective_cost_r
        # Loss carry-forward shields future profits at corporate/slab rate (~30%)
        return round(pre_tax_ev * (1.0 - 0.30), 4)
    else:
        # Crypto Scenario B: Netting allowed for the year, but losses cannot offset non-crypto income
        pre_tax_ev = p_win * reward_r - (1.0 - p_win) * 1.0 - effective_cost_r
        if pre_tax_ev > 0:
            return round(pre_tax_ev * (1.0 - tax_rate), 4)
        return round(pre_tax_ev, 4)


def compute_nse_trade_friction(
    notional_inr: float,
    segment: str = "fno_futures",
) -> Dict[str, float]:
    """Compute exact Indian statutory charges & discount broker friction on round-trip trades.

    Components:
    - Brokerage: min(₹20, 0.03% * Turnover) per executed leg (buy & sell = 2 legs).
    - STT (Securities Transaction Tax):
        - fno_futures: 0.02% on sell side only
        - eq_intraday: 0.025% on sell side only
        - fno_options: 0.125% on sell side of premium
    - NSE Exchange Transaction Charge:
        - fno_futures: 0.00188% on both legs
        - eq_intraday: 0.00322% on both legs
        - fno_options: 0.0495% on both legs
    - SEBI Turnover Charges: 0.0001% on both legs
    - Stamp Duty:
        - fno_futures: 0.002% on buy side only
        - eq_intraday: 0.003% on buy side only
        - fno_options: 0.003% on buy side only
    - GST: 18.0% strictly on (Brokerage + Exchange Charge + SEBI Charge). STT and Stamp Duty are exempt.

    Returns dict containing all individual rupee charges and total_friction_inr + total_friction_pct.
    """
    notional = max(float(notional_inr or 0.0), 1.0)
    seg = (segment or "fno_futures").lower()

    # 1. Brokerage (2 legs: entry + exit)
    brokerage_per_leg = min(20.0, 0.0003 * notional)
    brokerage = brokerage_per_leg * 2.0

    # 2. STT (Sell side only)
    if seg == "fno_futures":
        stt = 0.00020 * notional  # 0.02%
    elif seg == "eq_intraday":
        stt = 0.00025 * notional  # 0.025%
    else:  # fno_options
        stt = 0.00125 * notional  # 0.125% on premium

    # 3. NSE Exchange Transaction Charge (Both legs)
    if seg == "fno_futures":
        txn_rate = 0.0000188  # 0.00188%
    elif seg == "eq_intraday":
        txn_rate = 0.0000322  # 0.00322%
    else:
        txn_rate = 0.000495   # 0.0495%
    exchange_txn = txn_rate * 2.0 * notional

    # 4. SEBI Turnover Charge (Both legs: 0.0001%)
    sebi = 0.000001 * 2.0 * notional

    # 5. Stamp Duty (Buy leg only)
    if seg == "fno_futures":
        stamp = 0.000020 * notional  # 0.002%
    elif seg == "eq_intraday":
        stamp = 0.000030 * notional  # 0.003%
    else:
        stamp = 0.000030 * notional  # 0.003%

    # 6. GST (18% on Brokerage + Exchange Txn + SEBI)
    gst_base = brokerage + exchange_txn + sebi
    gst = 0.18 * gst_base

    total_friction_inr = round(brokerage + stt + exchange_txn + sebi + stamp + gst, 4)
    total_friction_pct = round(total_friction_inr / notional, 6)

    return {
        "notional_inr": round(notional, 2),
        "brokerage": round(brokerage, 4),
        "stt": round(stt, 4),
        "exchange_txn": round(exchange_txn, 4),
        "sebi": round(sebi, 4),
        "stamp_duty": round(stamp, 4),
        "gst": round(gst, 4),
        "total_friction_inr": total_friction_inr,
        "total_friction_pct": total_friction_pct,
    }


def compute_nse_cost_r(
    notional_inr: float,
    stop_distance_pct: float,
    segment: str = "fno_futures",
) -> float:
    """Express round-trip NSE statutory friction in R-multiples."""
    if stop_distance_pct <= 0:
        return float("inf")
    friction = compute_nse_trade_friction(notional_inr, segment)
    return round(friction["total_friction_pct"] / stop_distance_pct, 4)


