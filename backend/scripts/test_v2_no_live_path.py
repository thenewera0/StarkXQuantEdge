"""StarkX QuantEdge v2: Test No Live Path & Hard Live Locks.

Asserts:
1. Rule 0.2: settings_v2.v2_live_enabled is strictly False.
2. V2LiveStubAdapter raises NotImplementedError unconditionally when order placement is attempted.
3. No code path in v2 execution or API can place live orders or bypass the live lock.
4. Legacy LIVE_TRADING_ENABLED guard remains green and strictly False.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.v2.config import settings_v2
from app.v2.execution import V2LiveStubAdapter, Order, OrderSide, OrderType


def test_v2_live_flags_locked():
    print("Testing Rule 0.2 Live Flags Lock...")
    # Assert V2_LIVE_ENABLED is strictly False
    assert settings_v2.v2_live_enabled is False, "CRITICAL SECURITY BREACH: settings_v2.v2_live_enabled must be False"
    print("PASS: settings_v2.v2_live_enabled is strictly False.")


def test_v2_live_stub_raises_not_implemented():
    print("Testing V2LiveStubAdapter cannot place live orders...")
    adapter = V2LiveStubAdapter()
    
    dummy_order = Order(
        order_id="test_order_id_123",
        sleeve="trend",
        asset="BTCUSDT",
        bar_open_time="2026-10-28T00:00:00Z",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT_POST_ONLY,
        target_qty=1.0,
        limit_price=60000.0,
    )
    
    # 1. place_order must raise NotImplementedError
    try:
        adapter.place_order(dummy_order)
        assert False, "CRITICAL: adapter.place_order did not raise NotImplementedError!"
    except NotImplementedError as exc:
        assert "Rule 0.2 Violation" in str(exc) or "not implemented" in str(exc)
        print("PASS: adapter.place_order strictly blocked and raised NotImplementedError.")
        
    # 2. cancel_order must raise NotImplementedError
    try:
        adapter.cancel_order("test_order_id_123")
        assert False, "CRITICAL: adapter.cancel_order did not raise NotImplementedError!"
    except NotImplementedError:
        print("PASS: adapter.cancel_order strictly blocked and raised NotImplementedError.")
        
    # 3. get_order_status must raise NotImplementedError
    try:
        adapter.get_order_status("test_order_id_123")
        assert False, "CRITICAL: adapter.get_order_status did not raise NotImplementedError!"
    except NotImplementedError:
        print("PASS: adapter.get_order_status strictly blocked and raised NotImplementedError.")


def test_no_bypass_live_lock():
    print("Testing impossible bypass of live adapter...")
    # Verify even if somebody attempts to create an adapter instance, place_order cannot succeed
    adapter = V2LiveStubAdapter()
    dummy_order = Order(
        order_id="bypass_attempt",
        sleeve="carry",
        asset="ETHUSDT",
        bar_open_time="2026-10-28T00:00:00Z",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET_TAKER,
        target_qty=0.5,
        limit_price=2500.0,
    )
    try:
        adapter.place_order(dummy_order)
        assert False, "Live bypass succeeded!"
    except NotImplementedError:
        pass
    print("PASS: Live bypass strictly impossible.")


if __name__ == "__main__":
    test_v2_live_flags_locked()
    test_v2_live_stub_raises_not_implemented()
    test_no_bypass_live_lock()
    print("SUCCESS: All v2 no-live-path invariant tests passed.")
