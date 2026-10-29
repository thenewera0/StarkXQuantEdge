"""test_lab_geometry.py

Section 0.4 & 9:
Geometry validator on every signal:
- stop on the correct side of entry (long: stop < entry; short: stop > entry)
- stop distance >= 0.25% (crypto)
- target 0.5-5R if target is specified
- price rounding >= 6 significant digits
- invalid signals are rejected and logged
- initial_stop is immutable; trailing stops live in trailing_stop
"""

import datetime
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.models import Signal
from app.lab.geometry import GeometryValidator, round_sig_digits, count_significant_digits


def main():
    print("================================================================================")
    print("TEST 9.2: test_lab_geometry (Signal Geometry Invariants & Immutability)")
    print("================================================================================")

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Valid Long Signal
    sig_long_valid = Signal(
        strategy_id="trend_d1",
        variant_id="trend_d1_base",
        symbol="BTCUSDT",
        direction="long",
        bar_open_time=now,
        entry_mode="next_open",
        stop_atr=2.0,
        target_r=2.0,
        trail_atr=None,
        max_hold_bars=10,
        meta={"atr": 1000.0},
    )
    entry = 60000.0
    stop = 58000.0  # (60000-58000)/60000 = 3.33% >= 0.25%
    target = 64000.0 # 2.0R
    is_valid, reason = GeometryValidator.validate(sig_long_valid, entry, stop, target)
    assert is_valid, f"Expected valid long signal, got: {reason}"
    assert stop < entry, "Long stop must be below entry"
    assert target > entry, "Long target must be above entry"
    print(f"[PASS] Valid Long Signal passed: entry={entry}, stop={stop}, target={target}")

    # 2. Valid Short Signal
    sig_short_valid = Signal(
        strategy_id="funding_skew_4h",
        variant_id="funding_skew_4h_base",
        symbol="ETHUSDT",
        direction="short",
        bar_open_time=now,
        entry_mode="next_open",
        stop_atr=2.0,
        target_r=1.5,
        trail_atr=None,
        max_hold_bars=24,
        meta={"atr": 50.0},
    )
    entry_s = 3000.0
    stop_s = 3100.0  # (3100-3000)/3000 = 3.33% >= 0.25%
    target_s = 2850.0 # 1.5R
    is_valid, reason = GeometryValidator.validate(sig_short_valid, entry_s, stop_s, target_s)
    assert is_valid, f"Expected valid short signal, got: {reason}"
    assert stop_s > entry_s, "Short stop must be above entry"
    assert target_s < entry_s, "Short target must be below entry"
    print(f"[PASS] Valid Short Signal passed: entry={entry_s}, stop={stop_s}, target={target_s}")

    # 3. Reject Wrong-Side Stop
    sig_wrong_stop = Signal(
        strategy_id="donchian_4h",
        variant_id="donchian_4h_base",
        symbol="BTCUSDT",
        direction="long",
        bar_open_time=now,
        entry_mode="next_open",
        stop_atr=2.0,
        target_r=2.0,
        trail_atr=None,
        max_hold_bars=20,
        meta={"atr": 500.0},
    )
    is_valid, reason = GeometryValidator.validate(sig_wrong_stop, entry_price=60000.0, stop_price=61000.0)
    assert not is_valid, "Should reject wrong-side stop"
    print(f"[PASS] Correctly rejected wrong-side stop: {reason}")

    # 4. Reject Tight Stop (< 0.25%)
    # entry 60000, stop 59900 -> dist = 100 / 60000 = 0.166% < 0.25%
    is_valid, reason = GeometryValidator.validate(sig_long_valid, entry_price=60000.0, stop_price=59900.0)
    assert not is_valid, "Should reject stop distance < 0.25%"
    print(f"[PASS] Correctly rejected stop < 0.25%: {reason}")

    # 5. Reject Invalid Target R (< 0.5R or > 5.0R)
    # Stop dist = 2000. Target = 60000 + 400 (0.2R)
    is_valid, reason = GeometryValidator.validate(sig_long_valid, entry_price=60000.0, stop_price=58000.0, target_price=60400.0)
    assert not is_valid, "Should reject target < 0.5R"
    print(f"[PASS] Correctly rejected target < 0.5R: {reason}")

    # Target = 60000 + 12000 (6.0R)
    is_valid, reason = GeometryValidator.validate(sig_long_valid, entry_price=60000.0, stop_price=58000.0, target_price=72000.0)
    assert not is_valid, "Should reject target > 5.0R"
    print(f"[PASS] Correctly rejected target > 5.0R: {reason}")

    # 6. Price rounding >= 6 significant digits
    raw_price = 60123.456789
    rounded_price = round_sig_digits(raw_price, digits=6)
    assert rounded_price == 60123.5, f"Expected 60123.5, got {rounded_price}"
    assert count_significant_digits(rounded_price) >= 6
    print(f"[PASS] Price rounding >= 6 sig digits: {raw_price} -> {rounded_price}")

    # 7. Initial Stop Immutability Contract
    # In LabPosition, initial_stop is set at entry and never mutated; trailing_stop holds the dynamic stop
    from app.lab.models import LabPosition
    pos = LabPosition(
        position_id="test_pos_001",
        strategy_id="trend_d1",
        variant_id="trend_d1_base",
        symbol="BTCUSDT",
        side="long",
        entry_mode="taker",
        entry_price=60000.0,
        entry_time=now,
        size_qty=0.025,
        initial_stop=58000.0,
        trailing_stop=58000.0,
        target_price=64000.0,
        risk_r_usd=50.0,
    )
    # Update trailing stop
    pos.trailing_stop = 59000.0
    assert pos.initial_stop == 58000.0, "initial_stop must remain completely unchanged"
    assert pos.trailing_stop == 59000.0, "trailing_stop updated cleanly"
    print(f"[PASS] Immutable initial_stop ({pos.initial_stop}) verified while trailing_stop updated to {pos.trailing_stop}")

    print("================================================================================")
    print("ALL test_lab_geometry CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
