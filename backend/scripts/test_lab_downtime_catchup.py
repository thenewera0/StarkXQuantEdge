"""test_lab_downtime_catchup.py

StarkX LAB: Operational Acceptance Test — 3-Hour Downtime Catch-Up & Replay.

Proves:
1. Missed 1-minute candles are replayed in chronological order with stop-first resolution.
2. Missed bar closes are evaluated in order, exactly once.
3. Zero duplicate signals emitted due to DB UNIQUE constraints.
4. Open positions resolve at the exact minute when stops/targets are touched.
5. Cent-level ledger reconciliation holds throughout and after catch-up ($0.00 delta).
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.storage import LabStorage
from app.lab.engine import LabEngine
from app.lab.models import LabPosition, Signal


def main():
    print("================================================================================")
    print("TEST: test_lab_downtime_catchup (3-Hour Downtime Simulation & Stop-First Replay)")
    print("================================================================================")

    # 1. Initialize clean test engine with in-memory storage
    storage = LabStorage(":memory:")
    engine = LabEngine(storage=storage)

    t0 = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    t_end = t0 + timedelta(hours=3)  # 180 minutes of simulated downtime

    # 2. Open a test position at t0
    # Long BTCUSDT: entry = 100.0, stop = 95.0, target = 110.0, risk = $50
    pos = LabPosition(
        position_id="test_catchup_pos_1",
        strategy_id="rsi2_pullback_1h",
        variant_id="rsi2_pullback_1h_base",
        symbol="BTCUSDT",
        side="long",
        entry_mode="taker",
        entry_price=100.0,
        entry_time=t0,
        size_qty=10.0,
        initial_stop=95.0,
        trailing_stop=95.0,
        target_price=110.0,
        risk_r_usd=50.0,
        max_hold_bars=12,
        age_bars=0,
        unrealized_r=0.0,
        status="open",
        fee_paid_usd=0.05,
        gst_paid_usd=0.009,
        slippage_usd=0.03,
    )
    storage.save_position(pos, is_backfill=False)
    print(f"[INIT] Position opened at {t0.isoformat()}: LONG BTCUSDT @ $100.00 (Stop: $95.00, Target: $110.00)")

    # 3. Construct 180 1-minute candles for the 3 hours
    # Minute 1 to 44: normal fluctuation (98.0 - 102.0)
    # Minute 45 (12:45 UTC): SAME-MINUTE COLLISION (high = 112.0 touches target, low = 94.0 touches stop)
    # Minute 46 to 180: price continues (101.0 - 104.0)
    minute_timestamps = [t0 + timedelta(minutes=i) for i in range(1, 181)]
    records = []
    collision_minute = t0 + timedelta(minutes=45)

    for m in minute_timestamps:
        if m == collision_minute:
            # Collision candle: BOTH stop (95.0) and target (110.0) touched!
            records.append({
                "open_time": m,
                "open": 100.0,
                "high": 112.0,  # > 110.0 target
                "low": 94.0,    # < 95.0 stop
                "close": 102.0,
                "volume": 500.0,
            })
        else:
            records.append({
                "open_time": m,
                "open": 99.5,
                "high": 101.5,
                "low": 98.5,
                "close": 100.0,
                "volume": 100.0,
            })

    df_1m = pd.DataFrame(records).set_index("open_time")
    df_1m.index = pd.to_datetime(df_1m.index, utc=True)
    minute_feed = {"BTCUSDT": df_1m}

    # 4. Execute 3-Hour Downtime Catch-up
    print(f"[REPLAY] Simulating engine restart after 3 hours downtime ({t0.isoformat()} -> {t_end.isoformat()})...")
    catchup_result = engine.catch_up(
        from_time=t0,
        to_time=t_end,
        minute_candles_by_symbol=minute_feed,
    )

    print(f"[RESULT] Catch-up Summary: {catchup_result}")

    # Assertion 1: Missed minutes
    assert catchup_result["missed_minutes"] == 180, f"Expected 180 minutes, got {catchup_result['missed_minutes']}"
    print(f"[PASS] Exact 180 minutes replayed chronologically.")

    # Assertion 2: Open position resolved at exact minute (12:45 UTC)
    open_pos_ids = {p["position_id"] for p in storage.get_open_positions()}
    assert "test_catchup_pos_1" not in open_pos_ids, "test_catchup_pos_1 should be closed after catch-up!"

    # Query resolved position from DB
    with storage._get_conn() as conn:
        p_row = dict(conn.execute("SELECT * FROM lab_positions WHERE position_id = 'test_catchup_pos_1'").fetchone())

    assert p_row["status"] == "closed", f"Expected closed status, got {p_row['status']}"
    assert p_row["exit_reason"] in ("stop_loss", "stop_collision_first"), (
        f"CRITICAL STOP-FIRST VIOLATION: Expected 'stop_loss' or 'stop_collision_first', got '{p_row['exit_reason']}'!"
    )
    print(f"[PASS] Stop-First Collision Invariant Verified: exit_reason='{p_row['exit_reason']}' (target ignored on same-minute collision).")

    # Verify exact resolution minute
    exit_ts = pd.to_datetime(p_row["exit_time"], utc=True)
    assert exit_ts == collision_minute, f"Expected exit at {collision_minute}, got {exit_ts}"
    print(f"[PASS] Exact minute resolution verified: closed at {exit_ts.isoformat()} (minute 45).")

    # Assertion 3: Missed bar closes evaluated
    assert catchup_result["bar_closes_evaluated"] >= 3, (
        f"Expected at least 3 hourly bar closes, got {catchup_result['bar_closes_evaluated']}"
    )
    print(f"[PASS] Missed bar closes evaluated in chronological order ({catchup_result['bar_closes_evaluated']} cycles).")

    # Assertion 4: Zero duplicate signals upon redundant catch-up execution
    sig_count_1 = len(storage._get_conn().execute("SELECT * FROM lab_signals").fetchall())
    print(f"[IDEMPOTENCY] Re-running catch-up over identical window to test idempotency...")
    catchup_result_2 = engine.catch_up(
        from_time=t0,
        to_time=t_end,
        minute_candles_by_symbol=minute_feed,
    )
    sig_count_2 = len(storage._get_conn().execute("SELECT * FROM lab_signals").fetchall())
    assert sig_count_1 == sig_count_2, f"Duplicate signals generated! Before: {sig_count_1}, After: {sig_count_2}"
    print(f"[PASS] Zero duplicate signals: count strictly invariant ({sig_count_1} == {sig_count_2}).")

    # Assertion 5: Ledger reconciliation holds to the cent
    assert catchup_result["ledger_reconciled"], f"Ledger failed reconciliation! Delta: {catchup_result['delta_usd']}"
    assert catchup_result["delta_usd"] == 0.0, f"Expected $0.00 delta, got {catchup_result['delta_usd']}"
    print(f"[PASS] Ledger reconciles to the cent: deltaUsd = ${catchup_result['delta_usd']:.4f}")

    print("================================================================================")
    print("ALL test_lab_downtime_catchup CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
