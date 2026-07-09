"""Per-market transaction-cost model (Blueprint v2 §2.8 — 'fix measurement first').

Every realized/backtested P&L number is only as honest as the cost assumed. A single flat
0.02% slippage is badly optimistic for thin alts and wrong for forex (whose cost is the spread,
not a fee). This module returns a realistic **round-trip** cost as a fraction of notional:

    round_trip_cost(market, symbol, atr_pct) -> fraction (entry + exit, fees + slippage)

Crypto  : taker fee per side + slippage that scales with the bar's ATR% and a liquidity tier
          (majors cheap, alts expensive). Volatile bars fill worse; illiquid books fill worse.
Forex   : the spread dominates; modelled per liquidity tier (majors tight, metals/crosses wide).
          Session-dependent widening (rollover/news) is a P1 refinement, noted below.

Also exposes `cost_in_r` (cost expressed in R units) for the EV-gate work in §2.6.
Pure, deterministic, dependency-free -> unit-testable and identical in live + backtest.
"""

from __future__ import annotations

# --- Crypto liquidity tiers (Binance USDT pairs) ---------------------------
# tier -> (fee_per_side, base_slip_per_side, vol_slip_coef)
#   fee: futures taker ~0.05%.  base_slip: fixed book-crossing cost.
#   vol_slip_coef: fraction of the bar's ATR% paid as slippage on a market fill.
_CRYPTO_TIERS = {
    "major": (0.0005, 0.0001, 0.02),   # BTC, ETH — deep books
    "large": (0.0005, 0.0002, 0.03),   # SOL, BNB, XRP — liquid majors-adjacent
    "alt":   (0.0005, 0.0004, 0.05),   # everything else — thin in 2026's low-liquidity tape
}
_CRYPTO_MAJORS = {"BTCUSDT", "ETHUSDT", "BTCUSD", "ETHUSD"}
_CRYPTO_LARGE = {"SOLUSDT", "BNBUSDT", "XRPUSDT", "SOLUSD", "BNBUSD", "XRPUSD"}

# --- Forex / metals round-trip spread (fraction of price) ------------------
# Conservative baseline spreads; real spreads widen 3-10x at rollover/news (P1: session clock).
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


def round_trip_cost(market: str, symbol: str, atr_pct: float = 0.0) -> float:
    """Total round-trip cost (entry + exit) as a fraction of notional.

    atr_pct = ATR / price for the entry bar (drives crypto slippage). Clamped to a sane range
    so a bad data point can't produce an absurd cost.
    """
    atr_pct = min(max(float(atr_pct or 0.0), 0.0), 0.15)  # 0..15% guardrail
    if (market or "crypto").lower() in _CRYPTO_MARKETS:
        fee, base_slip, vol_coef = _CRYPTO_TIERS[_crypto_tier(symbol)]
        per_side = fee + base_slip + vol_coef * atr_pct
        return round(2.0 * per_side, 8)
    return round(_forex_spread(symbol), 8)


def cost_in_r(market: str, symbol: str, atr_pct: float, stop_frac: float) -> float:
    """Round-trip cost expressed in R (risk) units: cost_fraction / stop_distance_fraction.

    Used by the EV gate (§2.6): a setup must clear EV = p*R - (1-p) - cost_in_r before it trades.
    Returns a large number if the stop distance is unknown/zero (i.e. 'too expensive to trade').
    """
    if not stop_frac or stop_frac <= 0:
        return float("inf")
    return round_trip_cost(market, symbol, atr_pct) / float(stop_frac)
