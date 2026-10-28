"""StarkX QuantEdge v2: Test Tax & Statutory Compliance Engine.

Asserts:
1. FIFO lot accounting: oldest lot consumed first upon disposal.
2. Transfer events: every disposal (to cash, stablecoin, or crypto-to-crypto) is a transfer event.
3. Scenario A: 31.2% flat tax on every positive trade gain, NO loss offset permitted.
4. Scenario B: 31.2% tax on net annual gains (positive and negative gains netted per Financial Year).
5. Section 194S TDS: 1% transfer value withheld as cash-flow credit, self_deducted=True.
6. Financial Year demarcation: April 1 to March 31 boundary rules.
7. Estimated tax cost preview on proposed rebalance orders.
8. Chartered Accountant CSV export formatting and statutory disclaimer.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from app.v2.tax import (
    TaxLedger,
    get_financial_year,
    MANDATORY_TAX_DISCLAIMER,
)


def test_financial_year_parser():
    print("Testing Indian Financial Year (Apr 1 - Mar 31) boundary dates...")
    assert get_financial_year("2026-04-01") == "FY2026-27"
    assert get_financial_year("2026-10-28") == "FY2026-27"
    assert get_financial_year("2027-03-31") == "FY2026-27"
    assert get_financial_year("2027-04-01") == "FY2027-28"
    assert get_financial_year("2026-03-31") == "FY2025-26"
    assert get_financial_year("2026-01-15") == "FY2025-26"
    print("PASS: Financial Year boundary transitions verified.")


def test_fifo_accounting_and_tax_scenarios():
    print("Testing FIFO lot depletion and Scenarios A & B calculation...")
    ledger = TaxLedger()
    
    # Lot 1: Bought 1.0 BTC @ $20,000 on 2026-05-01
    ledger.record_acquisition("BTC", "2026-05-01T10:00:00Z", quantity=1.0, unit_price_usd=20000.0)
    
    # Lot 2: Bought 1.0 BTC @ $30,000 on 2026-06-01
    ledger.record_acquisition("BTC", "2026-06-01T10:00:00Z", quantity=1.0, unit_price_usd=30000.0)
    
    # Trade 1: Sell 0.5 BTC @ $25,000 on 2026-07-01
    # Under FIFO, this must consume from Lot 1 (cost $20,000)
    # Gain: 0.5 * (25000 - 20000) = +$2,500.00
    # Proceeds: $12,500.00 -> TDS (1%): $125.00
    # Scenario A tax (31.2%): $780.00
    events1 = ledger.record_disposal("BTC", "2026-07-01T10:00:00Z", quantity=0.5, unit_proceeds_usd=25000.0)
    assert len(events1) == 1
    e1 = events1[0]
    assert e1.total_cost_usd == 10000.0  # 0.5 * 20,000
    assert e1.total_proceeds_usd == 12500.0
    assert e1.gross_gain_usd == 2500.0
    assert abs(e1.scenario_a_tax_usd - 780.0) < 1e-4
    assert abs(e1.tds_withheld_usd - 125.0) < 1e-4
    assert e1.self_deducted is True
    
    # Lot 1 now has 0.5 remaining.
    assert abs(ledger.open_lots["BTC"][0].remaining_quantity - 0.5) < 1e-6
    
    # Trade 2: Sell 1.0 BTC @ $22,000 on 2026-08-01
    # Under FIFO, this consumes the remaining 0.5 from Lot 1 (gain = 0.5 * (22000 - 20000) = +$1,000)
    # and 0.5 from Lot 2 (loss = 0.5 * (22000 - 30000) = -$4,000)
    events2 = ledger.record_disposal("BTC", "2026-08-01T10:00:00Z", quantity=1.0, unit_proceeds_usd=22000.0)
    assert len(events2) == 2
    
    # Event 2a: consumed from Lot 1
    assert events2[0].gross_gain_usd == 1000.0
    assert abs(events2[0].scenario_a_tax_usd - 312.0) < 1e-4  # 31.2% of 1,000
    
    # Event 2b: consumed from Lot 2
    assert events2[1].gross_gain_usd == -4000.0
    # Under Scenario A: NO loss offset, tax on loss is strictly 0.00
    assert events2[1].scenario_a_tax_usd == 0.0
    
    # Annual FY Summary Verification:
    # Total Gross Realized PnL: +2500 + 1000 - 4000 = -$500.00 (Net loss overall!)
    # Scenario A: Taxes positive gains only (+2500 + 1000 = +3500) @ 31.2% = $1,092.00 tax despite overall net loss!
    # Scenario B: Taxes net gain (max(-500, 0)) @ 31.2% = $0.00 tax!
    summaries = ledger.get_financial_year_summaries()
    assert len(summaries) == 1
    s = summaries[0]
    assert s.financial_year == "FY2026-27"
    assert s.net_realized_pnl_usd == -500.0
    assert abs(s.scenario_a_tax_usd - 1092.0) < 1e-4, f"Scenario A tax should be 1092.0, got {s.scenario_a_tax_usd}"
    assert s.scenario_b_tax_usd == 0.0, f"Scenario B tax on net loss should be 0.0, got {s.scenario_b_tax_usd}"
    assert s.tds_credits_usd == 125.0 + (22000.0 * 0.01)  # 125 + 220 = 345
    print("PASS: FIFO lot accounting and Scenarios A & B asymmetric tax rules verified.")


def test_order_estimated_tax_preview_and_ca_export():
    print("Testing rebalance tax cost estimator and CA CSV format...")
    ledger = TaxLedger()
    ledger.record_acquisition("ETH", "2026-05-01T10:00:00Z", quantity=2.0, unit_price_usd=2000.0)
    
    # Estimate rebalancing 1.0 ETH at $2500
    # Gain: 1.0 * (2500 - 2000) = $500 -> 31.2% tax = $156.00
    tax_cost, log_msg = ledger.estimate_rebalance_tax_cost("ETH", quantity_to_sell=1.0, estimated_unit_price=2500.0)
    assert abs(tax_cost - 156.0) < 1e-4
    assert "estimated tax cost of this rebalance: $156.00" in log_msg
    assert MANDATORY_TAX_DISCLAIMER in log_msg
    
    # Execute disposal and verify CA export
    ledger.record_disposal("ETH", "2026-05-15T10:00:00Z", quantity=1.0, unit_proceeds_usd=2500.0)
    csv_text = ledger.export_ca_csv()
    assert "Disposal ID" in csv_text
    assert "Cost Basis (USD)" in csv_text
    assert "194S TDS Deducted (USD)" in csv_text
    assert MANDATORY_TAX_DISCLAIMER in csv_text
    print("PASS: CA CSV export format and rebalance tax estimation verified.")


if __name__ == "__main__":
    test_financial_year_parser()
    test_fifo_accounting_and_tax_scenarios()
    test_order_estimated_tax_preview_and_ca_export()
    print("SUCCESS: All v2 tax lot, statutory scenario, and compliance tests passed.")
