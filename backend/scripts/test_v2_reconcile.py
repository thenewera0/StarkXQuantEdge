"""StarkX QuantEdge v2: Test Daily Ledger-to-Equity Reconciliation.

Asserts:
1. Daily reconciliation passes when marked equity and book ledger differ by <= $0.01 USD.
2. System triggers immediate alert and halt when |delta| > 0.01 USD.
3. Gate B -> C invariant: zero reconciliation breaks permitted.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.v2.allocator import reconcile_ledger


def test_reconciliation_tolerance_and_halt():
    print("Testing Daily Ledger Reconciliation (|delta| <= $0.01 USD)...")
    
    # 1. Exact balance -> PASS
    is_rec, delta, msg = reconcile_ledger(1000.00, 1000.00, tolerance_usd=0.01)
    assert is_rec is True
    assert delta == 0.0
    
    # 2. Sub-cent discrepancy ($0.008) -> PASS
    is_rec2, delta2, msg2 = reconcile_ledger(1000.000, 1000.008, tolerance_usd=0.01)
    assert is_rec2 is True
    assert delta2 == 0.008
    
    # 3. Discrepancy > 1 cent ($0.015) -> FAIL & HALT
    is_rec3, delta3, msg3 = reconcile_ledger(1000.00, 1000.015, tolerance_usd=0.01)
    assert is_rec3 is False, "Reconciliation break > $0.01 must fail"
    assert delta3 == 0.015
    assert "CRITICAL ALERT" in msg3
    assert "System halted" in msg3
    print(f"PASS: Reconciliation tolerance enforced: delta $0.008 passed, delta $0.015 triggered halt.")


if __name__ == "__main__":
    test_reconciliation_tolerance_and_halt()
    print("SUCCESS: All v2 reconciliation tests passed.")
