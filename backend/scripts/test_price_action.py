"""Comprehensive Unit & Regression Test Suite for Price Action & Chart Engine."""

import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from app.price_action import (
    analyze_candle_anatomy,
    detect_candlestick_patterns,
    detect_support_resistance_zones,
    detect_liquidity_sweeps,
    analyze_market_structure,
    evaluate_price_action,
    validate_trade_price_action,
)

passed = 0
failed = 0


def check(name: str, condition: bool):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")


print("=== 1. Candle Anatomy & Rejection Diagnosis ===")
c1 = pd.Series({"open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0})
a1 = analyze_candle_anatomy(c1)
check("Normal candle range is 7.0", abs(a1["range"] - 7.0) < 0.0001)
check("Normal candle body is 4.0", abs(a1["body"] - 4.0) < 0.0001)
check("Normal candle is bullish", a1["is_bullish"] is True)
check("Normal candle rejection is none", a1["rejection"] == "none")

# Shooting Star (Upper wick rejection)
c_star = pd.Series({"open": 100.0, "high": 110.0, "low": 99.5, "close": 101.0})
a_star = analyze_candle_anatomy(c_star)
check("Shooting star upper wick ratio >= 0.5", a_star["upper_wick_ratio"] >= 0.5)
check("Shooting star rejection is bearish_rejection", a_star["rejection"] == "bearish_rejection")

# Hammer (Lower wick absorption)
c_hammer = pd.Series({"open": 108.0, "high": 109.0, "low": 98.0, "close": 107.0})
a_hammer = analyze_candle_anatomy(c_hammer)
check("Hammer lower wick ratio >= 0.5", a_hammer["lower_wick_ratio"] >= 0.5)
check("Hammer rejection is bullish_rejection", a_hammer["rejection"] == "bullish_rejection")

# Flat candle safety
c_flat = pd.Series({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0})
a_flat = analyze_candle_anatomy(c_flat)
check("Flat candle handled safely without div-by-zero", a_flat["range"] > 0)

print("\n=== 2. Pattern Recognition ===")
rows = [
    {"open": 100.0, "high": 102.0, "low": 98.0, "close": 99.0, "volume": 1000},
    {"open": 98.5, "high": 105.0, "low": 98.0, "close": 104.5, "volume": 2500},
]
df_engulf = pd.DataFrame(rows)
pats = detect_candlestick_patterns(df_engulf)
check("Detected bullish engulfing pattern", any(p["pattern"] == "bullish_engulfing" for p in pats))

rows_ib = [
    {"open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 1000},
    {"open": 102.0, "high": 107.0, "low": 98.0, "close": 104.0, "volume": 800},
]
df_ib = pd.DataFrame(rows_ib)
pats_ib = detect_candlestick_patterns(df_ib)
check("Detected inside bar pattern", any(p["pattern"] == "inside_bar" for p in pats_ib))

print("\n=== 3. Dynamic Support & Resistance Zones ===")
n = 100
t = np.linspace(0, 4 * np.pi, n)
base = 100.0 + 10.0 * np.sin(t)
df_sr = pd.DataFrame({
    "open": base,
    "high": base + 1.0,
    "low": base - 1.0,
    "close": base + 0.5,
    "volume": 1000,
    "atr": 2.0,
})
sr = detect_support_resistance_zones(df_sr)
check("Detected resistance zones", len(sr["resistance_zones"]) > 0 or sr["nearest_resistance"] is not None)
check("Nearest resistance is above current price", sr["nearest_resistance"] is None or sr["nearest_resistance"] > df_sr["close"].iloc[-1])

print("\n=== 4. Liquidity Sweeps (Stop Hunts) ===")
rows_sweep = [{"open": 100.0, "high": 105.0, "low": 95.0, "close": 100.0} for _ in range(30)]
rows_sweep.append({"open": 102.0, "high": 108.0, "low": 101.0, "close": 103.0})  # Pierced 105 but closed at 103
df_sweep = pd.DataFrame(rows_sweep)
sweep = detect_liquidity_sweeps(df_sweep)
check("Detected bearish liquidity sweep", sweep is not None and sweep["type"] == "bearish_liquidity_sweep")

print("\n=== 5. Pre-Trade Validation Gate (Flash, Core, Long-Term) ===")
rows_gate = [{"open": 100.0 + i, "high": 102.0 + i, "low": 99.0 + i, "close": 101.0 + i} for i in range(20)]
rows_gate.append({"open": 100.0, "high": 110.0, "low": 99.5, "close": 101.0})  # Severe upper wick
df_blocked_wick = pd.DataFrame(rows_gate)
allowed, reason, _ = validate_trade_price_action(df_blocked_wick, "long")
check("Blocked Long on severe upper wick rejection", not allowed and "upper wick" in reason)

rows_clean = [{"open": 100.0 + i, "high": 102.0 + i, "low": 99.0 + i, "close": 101.0 + i} for i in range(20)]
rows_clean.append({"open": 100.0, "high": 106.0, "low": 99.8, "close": 105.5})  # Clean bullish expansion
df_clean = pd.DataFrame(rows_clean)
allowed_clean, reason_clean, _ = validate_trade_price_action(df_clean, "long")
check("Allowed Long on clean price action", allowed_clean is True)

rows_short_gate = [{"open": 100.0 - i, "high": 101.0 - i, "low": 98.0 - i, "close": 99.0 - i} for i in range(20)]
rows_short_gate.append({"open": 101.0, "high": 101.5, "low": 91.0, "close": 100.0})  # Severe lower wick
df_blocked_short = pd.DataFrame(rows_short_gate)
allowed_short, reason_short, _ = validate_trade_price_action(df_blocked_short, "short")
check("Blocked Short on severe lower wick rejection", not allowed_short and "lower wick" in reason_short)

print("\n=== 6. Edge Cases & Resilience (NaNs, Zero Volume, Empty Frames) ===")
pa_empty = evaluate_price_action(pd.DataFrame())
check("Empty DataFrame handled gracefully", pa_empty["score"] == 0.0 and pa_empty["bias"] == "neutral")

df_single = pd.DataFrame([{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}])
pa_single = evaluate_price_action(df_single)
check("Single-row DataFrame handled gracefully", pa_single["score"] == 0.0)

df_nan = pd.DataFrame([{"open": np.nan, "high": np.nan, "low": np.nan, "close": np.nan}])
pa_nan = evaluate_price_action(df_nan)
check("NaN DataFrame handled without crashing", pa_nan is not None)

allow_sparse, reason_sparse, _ = validate_trade_price_action(df_single, "long")
check("Trade validation bypasses safely on insufficient data", allow_sparse is True and "insufficient" in reason_sparse)

print("\n==========================================")
print(f"TEST RESULTS: {passed} passed, {failed} failed.")
if failed > 0:
    sys.exit(1)
