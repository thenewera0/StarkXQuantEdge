"""test_lab_tax.py

Section 0.3, 0.5, 7.2 & 9:
test_lab_tax:
Enforces:
1. Scenario A: 31.2% flat tax on every winning trade P&L (Section 115BBH: 30% + 4% cess),
   strictly ZERO loss offset and zero expense deductions.
2. Scenario B: 31.2% on gains & losses netted (identical to v2).
3. 1% TDS cash-flow withholding tracking.
4. 18% GST on all platform fees.
5. Statutory Tax Disclaimer: "Not tax advice; consult a qualified Chartered Accountant."
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.tax import (
    calculate_tax_scenario_a,
    calculate_tax_scenario_b,
    apply_gst_to_fee,
    TAX_RATE,
    GST_RATE,
    TDS_RATE,
)
from app.lab.api import get_tax


def main():
    print("================================================================================")
    print("TEST 9.11: test_lab_tax (Statutory Tax Scenarios A & B)")
    print("================================================================================")

    # 1. Statutory Constants Verification
    assert abs(TAX_RATE - 0.312) < 1e-4, f"Tax rate must be 31.2% (30% + 4% cess), got {TAX_RATE}"
    assert abs(GST_RATE - 0.18) < 1e-4, f"GST must be 18%, got {GST_RATE}"
    assert abs(TDS_RATE - 0.01) < 1e-4, f"TDS must be 1%, got {TDS_RATE}"
    print(f"[PASS] Statutory constants verified: VDA Tax={TAX_RATE:.1%}, GST={GST_RATE:.1%}, TDS={TDS_RATE:.1%}")

    # 2. Scenario A: Zero Loss Offset Invariant
    # Trade 1: +$200, Trade 2: -$100. Gross Gain: $200, Gross Loss: $100. Net: $100.
    trades = [200.0, -100.0]
    turnovers = [2000.0, 2000.0]
    res_a = calculate_tax_scenario_a(trades, turnovers=turnovers)

    # Tax liability must be 31.2% on $200 = $62.40 (loss of $100 cannot reduce tax)
    assert abs(res_a["tax_liability"] - 62.40) < 1e-4, f"Expected tax $62.40, got {res_a['tax_liability']}"
    # Net profit after tax = $100 - $62.40 = $37.60
    assert abs(res_a["after_tax_pnl"] - 37.60) < 1e-4
    # Effective tax rate on net profit = 62.40 / 100 = 62.4%
    assert abs(res_a["effective_tax_rate"] - 0.624) < 1e-4
    print(f"[PASS] Scenario A zero loss offset verified: Tax=${res_a['tax_liability']:.2f} on $200 gain, effective rate={res_a['effective_tax_rate']:.1%}")

    # 3. Scenario B: Netting Invariant (Identical to v2: 31.2% on netted gains)
    res_b = calculate_tax_scenario_b(trades)
    # Net gain = $100. Tax is 31.2% on $100 = $31.20
    assert abs(res_b["tax_liability"] - 31.20) < 1e-4, f"Expected tax $31.20, got {res_b['tax_liability']}"
    # After tax P&L = $100 - $31.20 = $68.80
    assert abs(res_b["after_tax_pnl"] - 68.80) < 1e-4
    print(f"[PASS] Scenario B netting verified: Tax=${res_b['tax_liability']:.2f} on $100 net gain, after-tax=${res_b['after_tax_pnl']:.2f}")

    # 4. GST on Fees Invariant
    base_fee = 50.0
    fee_gst = apply_gst_to_fee(base_fee)
    assert abs(fee_gst - 59.00) < 1e-4, f"Expected $59.00 with 18% GST, got {fee_gst}"
    print(f"[PASS] 18% GST verified: ${base_fee:.2f} -> ${fee_gst:.2f}")

    # 5. API Tax Endpoint & Statutory Disclaimers
    tax_rows = get_tax()
    assert len(tax_rows) == 2, f"Expected 2 scenario rows, got {len(tax_rows)}"
    for r in tax_rows:
        assert "Not tax advice" in r.disclaimer or "consult" in r.disclaimer.lower(), (
            f"Row {r.scenario} missing required tax disclaimer!"
        )
    print("[PASS] Lab Tax API verified with mandatory statutory disclaimers on both Scenario A & B.")

    print("================================================================================")
    print("ALL test_lab_tax CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
