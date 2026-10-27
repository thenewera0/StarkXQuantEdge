"""Test 8.1: Stop Overwrite Prevention and Invariant Immutability.

Failing test first:
Verifies that when resolver evaluates trailing stops / breakeven moves on active trades:
1. Trailing stops are written strictly to signals.trailing_stop.
2. signals.stop and signals.initial_stop remain strictly IMMUTABLE.
3. Row 1281 (BNBUSDT) and similar trades cannot have their initial risk geometry altered.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[2]
backend_dir = root_dir / "backend"
load_dotenv(backend_dir / ".env")
sys.path.insert(0, str(backend_dir))

from app import db, persistence, resolver


def test_stop_overwrite_prevention():
    print("=" * 80)
    print("TEST: STOP OVERWRITE PREVENTION & TRAILING STOP ISOLATION (8.1)")
    print("=" * 80)

    # Insert a dummy signal for testing with known initial_stop
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            insert into signals (
                symbol, market, interval, as_of, label, composite, confidence, price,
                entry, stop, target, atr, strategy, direction, is_duplicate, initial_stop
            ) values (
                'TESTUSDT', 'crypto', '4h', '2026-10-01 12:00:00Z', 'Buy',
                0.75, 0.80, 100.0, 100.0, 95.0, 110.0, 4.0, 'core', 'long', false, 95.0
            ) returning id
        """)
        sig_id = cur.fetchone()[0]
        conn.commit()

    try:
        # Call update_signal_trailing_stop
        assert hasattr(persistence, "update_signal_trailing_stop"), (
            "persistence module lacks update_signal_trailing_stop function!"
        )

        persistence.update_signal_trailing_stop(sig_id, 100.25)

        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute("select stop, initial_stop, trailing_stop from signals where id = %s", (sig_id,))
            row = cur.fetchone()
            stop_val, init_stop_val, trail_stop_val = row

            # Assert signals.stop remained 95.0 and was NOT overwritten to 100.25
            assert float(stop_val) == 95.0, (
                f"VULNERABILITY DETECTED: signals.stop was overwritten to {stop_val} instead of staying 95.0!"
            )
            assert float(init_stop_val) == 95.0, (
                f"signals.initial_stop was altered: expected 95.0, got {init_stop_val}"
            )
            assert float(trail_stop_val) == 100.25, (
                f"trailing_stop was not updated: expected 100.25, got {trail_stop_val}"
            )
        print("PASS: signals.stop remains immutable; trailing stops isolated to trailing_stop column.")
    finally:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute("delete from signals where id = %s", (sig_id,))
            conn.commit()


if __name__ == "__main__":
    test_stop_overwrite_prevention()
