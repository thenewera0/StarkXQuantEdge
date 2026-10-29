"""test_lab_idempotent_signals.py

Section 0.4 & 9:
Enforces UNIQUE(strategy_id, variant_id, symbol, direction, bar_open_time).
Tests that:
1. Signal ID is deterministic and idempotent across executions.
2. An identical signal emitted a second time is rejected by the database integrity constraint.
3. Multiple signals on different variants or different bar times are accepted cleanly.
4. Order ID generation (compute_lab_order_id) is strictly deterministic and idempotent.
"""

import datetime
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.models import Signal, compute_lab_order_id
from app.lab.storage import LabStorage


def main():
    print("================================================================================")
    print("TEST 9.3: test_lab_idempotent_signals (Idempotency & Unique Signal Constraints)")
    print("================================================================================")

    # Use an in-memory database for testing
    storage = LabStorage(db_path=":memory:")

    bar_time = datetime.datetime(2026, 10, 28, 0, 0, 0, tzinfo=datetime.timezone.utc)

    sig1 = Signal(
        strategy_id="trend_d1",
        variant_id="trend_d1_base",
        symbol="BTCUSDT",
        direction="long",
        bar_open_time=bar_time,
        entry_mode="next_open",
        stop_atr=2.0,
        target_r=2.0,
        trail_atr=None,
        max_hold_bars=10,
        meta={"atr": 1000.0},
    )

    sig1_clone = Signal(
        strategy_id="trend_d1",
        variant_id="trend_d1_base",
        symbol="BTCUSDT",
        direction="long",
        bar_open_time=bar_time,
        entry_mode="next_open",
        stop_atr=2.0,
        target_r=2.0,
        trail_atr=None,
        max_hold_bars=10,
        meta={"atr": 1000.0},
    )

    # 1. Deterministic Signal ID
    assert sig1.signal_id == sig1_clone.signal_id, "Signal ID must be deterministic"
    print(f"[PASS] Deterministic signal ID: {sig1.signal_id}")

    # 2. Insert first signal -> success
    inserted1 = storage.record_signal(sig1)
    assert inserted1 is True, "First signal insertion should succeed"
    print(f"[PASS] First signal inserted successfully")

    # 3. Insert duplicate signal -> must return False (IntegrityError caught cleanly)
    inserted2 = storage.record_signal(sig1_clone)
    assert inserted2 is False, "Duplicate signal MUST be rejected by UNIQUE constraint"
    print(f"[PASS] Duplicate signal rejected cleanly by UNIQUE(strategy_id, variant_id, symbol, direction, bar_open_time)")

    # 4. Insert signal for different variant -> success
    sig_diff_variant = Signal(
        strategy_id="trend_d1",
        variant_id="trend_d1_fast",
        symbol="BTCUSDT",
        direction="long",
        bar_open_time=bar_time,
        entry_mode="next_open",
        stop_atr=1.5,
        target_r=2.0,
        trail_atr=None,
        max_hold_bars=10,
        meta={"atr": 1000.0},
    )
    assert storage.record_signal(sig_diff_variant) is True, "Signal with different variant_id should succeed"
    print(f"[PASS] Distinct variant_id signal inserted successfully")

    # 5. Insert signal for different direction -> success
    sig_diff_dir = Signal(
        strategy_id="trend_d1",
        variant_id="trend_d1_base",
        symbol="BTCUSDT",
        direction="short",
        bar_open_time=bar_time,
        entry_mode="next_open",
        stop_atr=2.0,
        target_r=2.0,
        trail_atr=None,
        max_hold_bars=10,
        meta={"atr": 1000.0},
    )
    assert storage.record_signal(sig_diff_dir) is True, "Signal with different direction should succeed"
    print(f"[PASS] Distinct direction signal inserted successfully")

    # 6. Idempotent Order ID calculation
    order_id_1 = compute_lab_order_id("trend_d1", "trend_d1_base", "BTCUSDT", "long", bar_time)
    order_id_2 = compute_lab_order_id("trend_d1", "trend_d1_base", "BTCUSDT", "long", bar_time)
    assert order_id_1 == order_id_2, "compute_lab_order_id must be strictly idempotent"
    print(f"[PASS] compute_lab_order_id verified idempotent: {order_id_1}")

    print("================================================================================")
    print("ALL test_lab_idempotent_signals CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
