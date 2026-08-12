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


# --- MAKER execution ------------------------------------------------------
# Measured 2026-08-07, and it reframes the whole fast-strategy problem. Simulating every bar on
# the 20 deepest pairs shows a REAL long-only directional edge:
#
#     15m long   gross +0.0603%/trade   t = 4.50   (n = 18,180)
#     1h  long   gross +0.0487%/trade   t = 2.30
#     1h  long, 96-bar hold   gross +0.1093%   t = 4.35
#
# The edge is real and it was never the problem. TAKER cost is 0.22-0.38% per round trip — four
# to eight times the edge — so the strategy was losing on execution, not on prediction. No signal
# search can close a gap that large, which is why 11,024 indicator combinations all failed.
#
# A resting LIMIT order changes the arithmetic completely: the maker fee is ~0.02% per side, and
# nothing crosses the book, so there is no spread and no ATR-scaled slippage. Round trip ~0.04%
# against an edge of 0.05-0.11%.
#
# The catch is ADVERSE SELECTION: a resting bid fills preferentially when price is falling, so the
# fills you actually get are worse than the average bar. Callers should stress this rather than
# assume it away — at a 96-bar hold the edge survived haircuts of 25/50/75% (+0.097/+0.052/+0.006%).
_MAKER_FEE_PER_SIDE = 0.0002     # Binance spot maker; lower again with BNB or VIP tiers
_MAKER_RESIDUAL_SLIP = 0.0000    # a resting order crosses no spread


def round_trip_cost(market: str, symbol: str, atr_pct: float = 0.0,
                    execution: str = "taker") -> float:
    """Total round-trip cost (entry + exit) as a fraction of notional.

    atr_pct = ATR / price for the entry bar (drives crypto slippage). Clamped to a sane range
    so a bad data point can't produce an absurd cost.

    execution: "taker" crosses the book (market orders) and pays fee + spread + ATR slippage.
               "maker" rests a limit order and pays the maker fee only. Maker is 5-9x cheaper and
               is the difference between a losing and a winning fast strategy — but it only fills
               when price comes to the order, which is a real constraint, not free money.
    """
    atr_pct = min(max(float(atr_pct or 0.0), 0.0), 0.15)  # 0..15% guardrail
    if (market or "crypto").lower() in _CRYPTO_MARKETS:
        if (execution or "taker").lower() == "maker":
            return round(2.0 * (_MAKER_FEE_PER_SIDE + _MAKER_RESIDUAL_SLIP), 8)
        fee, base_slip, vol_coef = _CRYPTO_TIERS[_crypto_tier(symbol)]
        per_side = fee + base_slip + vol_coef * atr_pct
        return round(2.0 * per_side, 8)
    return round(_forex_spread(symbol), 8)


def cost_in_r(market: str, symbol: str, atr_pct: float, stop_frac: float,
              execution: str = "taker") -> float:
    """Round-trip cost expressed in R (risk) units: cost_fraction / stop_distance_fraction.

    Used by the EV gate (§2.6): a setup must clear EV = p*R - (1-p) - cost_in_r before it trades.
    Returns a large number if the stop distance is unknown/zero (i.e. 'too expensive to trade').

    `execution` must match how the order will actually be sent. Pricing a maker strategy at taker
    cost rejects setups that are genuinely profitable; pricing a taker strategy at maker cost
    accepts ones that are not.
    """
    if not stop_frac or stop_frac <= 0:
        return float("inf")
    return round_trip_cost(market, symbol, atr_pct, execution) / float(stop_frac)
