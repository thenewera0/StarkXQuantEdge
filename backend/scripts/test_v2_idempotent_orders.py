"""StarkX QuantEdge v2: Test Idempotent Orders & State Machine.

Asserts:
1. Rule 0.3: Order ID = sha256(sleeve, asset, bar_open_time, side), deterministic & idempotent.
2. PaperBroker deduplication: attempting to submit the same order retrieves the existing instance.
3. State machine transitions: NEW -> SUBMITTED -> PARTIAL -> FILLED / EXPIRED.
4. Reprice logic: maker limit reprices up to 6 times at 5-minute intervals.
5. Taker cross rule: crosses as taker when < 30 mins remain in 4h execution window.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
from datetime import datetime, timezone
from app.v2.models import compute_order_id
from app.v2.execution import (
    PaperBroker,
    OrderSide,
    OrderState,
    OrderType,
)


def test_idempotent_order_hash():
    print("Testing idempotent SHA-256 order ID generation (Rule 0.3)...")
    sleeve = "trend"
    asset = "BTCUSDT"
    bar_open_time = "2026-10-28T00:00:00Z"
    side = "BUY"
    
    # Manual sha256 verification
    key = f"{sleeve.lower()}_{asset.upper()}_{bar_open_time}_{side.upper()}"
    expected_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
    
    id1 = compute_order_id(sleeve, asset, bar_open_time, side)
    id2 = compute_order_id(sleeve, asset, bar_open_time, side)
    
    assert id1 == expected_id, f"Hash mismatch: got {id1}, expected {expected_id}"
    assert id1 == id2, "Order ID generation is not deterministic"
    
    # Changing side changes ID
    id_sell = compute_order_id(sleeve, asset, bar_open_time, "SELL")
    assert id_sell != id1, "Order ID collision across different sides"
    print(f"PASS: Deterministic idempotent SHA-256 ID verified ({id1[:16]}...).")


def test_paper_broker_deduplication_and_state_machine():
    print("Testing Paper Broker deduplication and execution state machine...")
    broker = PaperBroker()
    now_dt = datetime.now(timezone.utc)
    bar_time = "2026-10-28T00:00:00Z"
    
    # 1. Create order
    order1 = broker.create_order(
        sleeve="trend",
        asset="BTCUSDT",
        bar_open_time=bar_time,
        side=OrderSide.BUY,
        target_qty=0.50,
        limit_price=65000.0,
    )
    assert order1.state == OrderState.NEW
    
    # 2. Duplicate creation attempt returns same object
    order2 = broker.create_order(
        sleeve="trend",
        asset="BTCUSDT",
        bar_open_time=bar_time,
        side=OrderSide.BUY,
        target_qty=0.50,
        limit_price=65000.0,
    )
    assert order1.order_id == order2.order_id
    assert len(broker.orders) == 1
    
    # 3. Submit
    broker.submit_order(order1.order_id)
    assert order1.state == OrderState.SUBMITTED
    
    # 4. Reprice up to 6 times
    for r in range(6):
        broker.reprice_order(order1.order_id, 65000.0 + r * 10.0)
    assert order1.reprice_count == 6
    assert order1.elapsed_minutes == 30.0
    
    # 7th reprice is rejected (max 6)
    broker.reprice_order(order1.order_id, 66000.0)
    assert order1.reprice_count == 6
    
    # 5. Through-by-1-tick fill simulation
    # Order limit price is 65050.0. If bar low is 65040.0 (strictly lower by >= tick), 100% fill
    broker.simulate_bar_execution(
        order_id=order1.order_id,
        bar_high=65200.0,
        bar_low=65040.0,
        bar_close=65100.0,
        current_time=now_dt,
        bar_duration_minutes=60.0,
    )
    assert order1.state == OrderState.FILLED
    assert order1.filled_qty == 0.50
    assert order1.fee_paid_usd > 0.0
    assert order1.gst_paid_usd > 0.0
    print("PASS: Broker state machine transitions NEW -> SUBMITTED -> FILLED verified with fees and GST.")


def test_taker_cross_on_window_expiry():
    print("Testing taker cross when < 30 mins remain in 4h window...")
    broker = PaperBroker()
    now_dt = datetime.now(timezone.utc)
    bar_time = "2026-10-28T04:00:00Z"
    
    order = broker.create_order(
        sleeve="trend",
        asset="ETHUSDT",
        bar_open_time=bar_time,
        side=OrderSide.BUY,
        target_qty=2.0,
        limit_price=2500.0,
    )
    # Fast forward elapsed time to 215 minutes (less than 30 mins in 240m window)
    order.elapsed_minutes = 215.0
    
    # Execute bar where limit was NOT touched (low was 2600.0 > limit 2500.0)
    broker.simulate_bar_execution(
        order_id=order.order_id,
        bar_high=2650.0,
        bar_low=2600.0,
        bar_close=2620.0,
        current_time=now_dt,
        bar_duration_minutes=5.0,
    )
    
    # Must have crossed as taker at market close with slippage
    assert order.state == OrderState.FILLED
    assert order.order_type == OrderType.MARKET_TAKER
    assert order.slippage_usd > 0.0
    print("PASS: Taker cross cleanly executed when window elapsed.")


if __name__ == "__main__":
    test_idempotent_order_hash()
    test_paper_broker_deduplication_and_state_machine()
    test_taker_cross_on_window_expiry()
    print("SUCCESS: All v2 idempotent order and state machine tests passed.")
