"""test_lab_resolver_1m.py

Section 0.4 & 9:
Tests 1-minute candle resolution:
- Same-minute collision: candle hits both stop and target -> strictly STOP FIRST.
- Stop-loss resolution at initial_stop / trailing_stop.
- Take-profit resolution at target_price.
- Volume rank slippage: 3 bps (rank <= 30), 6 bps (31-50), 10 bps (51-100).
- Fee & GST calculations: 18% GST on fees.
- Execution twins: taker baseline and maker twin generation.
"""

import datetime
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.models import LabPosition, Signal
from app.lab.resolver import LabResolver


def main():
    print("================================================================================")
    print("TEST 9.4: test_lab_resolver_1m (1-Minute Resolution & Stop-First Collision)")
    print("================================================================================")

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Volume rank slippage schedule
    assert LabResolver.get_slippage_rate(10) == 0.0003, "Rank <= 30 must have 3 bps slippage"
    assert LabResolver.get_slippage_rate(30) == 0.0003, "Rank 30 must have 3 bps slippage"
    assert LabResolver.get_slippage_rate(35) == 0.0006, "Rank 31-50 must have 6 bps slippage"
    assert LabResolver.get_slippage_rate(50) == 0.0006, "Rank 50 must have 6 bps slippage"
    assert LabResolver.get_slippage_rate(75) == 0.0010, "Rank 51-100 must have 10 bps slippage"
    print("[PASS] Slippage rates verified: 3 bps (<=30), 6 bps (31-50), 10 bps (51-100)")

    # 2. Stop-First on Same-Minute Collision
    # Long position: entry = 60000, stop = 58000, target = 64000
    pos_collision = LabPosition(
        position_id="test_col_001",
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

    # Candle that spans from 57000 (below stop) to 65000 (above target) in the SAME minute
    closed = LabResolver.resolve_minute_candle(
        pos=pos_collision,
        candle_open=60000.0,
        candle_high=65000.0,  # Hits target (64000)
        candle_low=57000.0,   # Hits stop (58000)
        candle_close=61000.0,
        candle_time=now,
    )

    assert closed is True, "Position should be closed"
    assert pos_collision.status == "closed"
    assert pos_collision.exit_reason == "stop_collision_first", f"Must be stop_collision_first, got {pos_collision.exit_reason}"
    assert pos_collision.exit_price == 58000.0, f"Exit price must be stop price (58000), got {pos_collision.exit_price}"
    assert pos_collision.realized_r < 0, "Collision must result in negative R (stop loss)"
    print(f"[PASS] Same-minute collision strictly resolved STOP FIRST: reason='{pos_collision.exit_reason}', exit_price={pos_collision.exit_price}")

    # 3. Clean Take Profit
    pos_tp = LabPosition(
        position_id="test_tp_001",
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
    closed_tp = LabResolver.resolve_minute_candle(
        pos=pos_tp,
        candle_open=62000.0,
        candle_high=64500.0,  # Hits target only
        candle_low=61500.0,   # Well above stop
        candle_close=64200.0,
        candle_time=now,
    )
    assert closed_tp is True
    assert pos_tp.exit_reason == "take_profit"
    assert pos_tp.exit_price == 64000.0
    assert pos_tp.realized_r > 0
    print(f"[PASS] Take profit resolved cleanly: reason='{pos_tp.exit_reason}', realized_r={pos_tp.realized_r:.2f}R")

    # 4. Clean Stop Loss
    pos_sl = LabPosition(
        position_id="test_sl_001",
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
    closed_sl = LabResolver.resolve_minute_candle(
        pos=pos_sl,
        candle_open=59000.0,
        candle_high=59500.0,  # Below target
        candle_low=57500.0,   # Hits stop only
        candle_close=57800.0,
        candle_time=now,
    )
    assert closed_sl is True
    assert pos_sl.exit_reason == "stop_loss"
    assert pos_sl.exit_price == 58000.0
    assert pos_sl.realized_r < 0
    print(f"[PASS] Stop loss resolved cleanly: reason='{pos_sl.exit_reason}', realized_r={pos_sl.realized_r:.2f}R")

    # 5. Execution Twins Generation & GST Verification
    sig = Signal(
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
    taker_pos, maker_pos = LabResolver.open_position_from_signal(
        signal=sig,
        next_bar_open=60000.0,
        next_bar_low=59800.0,  # Maker limit (60000 - 0.15*1000 = 59850) -> through by 1 tick (59850 - 0.10) = 59849.9
        next_bar_high=60500.0,
        volume_rank=10,
        account_equity=10000.0,
        risk_pct=0.005,
    )
    assert taker_pos is not None, "Taker twin must always be created"
    # GST check: GST is exactly 18% of fee
    expected_gst = taker_pos.fee_paid_usd * 0.18
    assert abs(taker_pos.gst_paid_usd - expected_gst) < 1e-4, "GST must be exactly 18% of fees"
    print(f"[PASS] GST verified: fee=${taker_pos.fee_paid_usd:.4f}, GST(18%)=${taker_pos.gst_paid_usd:.4f}")

    if maker_pos:
        assert maker_pos.entry_mode == "maker"
        print(f"[PASS] Maker twin generated at limit {maker_pos.entry_price}")

    print("================================================================================")
    print("ALL test_lab_resolver_1m CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
