"""Unit tests for Phase 11 Tax Module (app.tax).

Verifies:
1. Scenario A: 31.2% tax on every positive trade P&L (no loss offset).
2. Scenario B: 31.2% tax on netted gains and losses.
3. Platform fees include 18% GST.
4. 1% TDS cash-flow withholding calculation.
5. Indian FY date grouping (April 1 to March 31).
"""

from __future__ import annotations

import sys
from pathlib import Path

cur_path = Path(__file__).resolve()
backend_dir = cur_path.parents[1] if (cur_path.parents[1] / "app").exists() else (cur_path.parents[1] / "backend")
root_dir = cur_path.parents[1] if (cur_path.parents[1] / "docs").exists() else cur_path.parents[0]
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))

from app.tax import (
    apply_gst_to_fee,
    calculate_tax_scenario_a,
    calculate_tax_scenario_b,
    get_financial_year,
    evaluate_series_after_tax,
    TAX_RATE,
    GST_RATE,
    TDS_RATE,
)
import pandas as pd


def test_gst_on_platform_fees():
    nominal_fee = 10.0
    fee_with_gst = apply_gst_to_fee(nominal_fee)
    assert abs(fee_with_gst - 11.80) < 1e-6, f"Expected $11.80 with 18% GST, got {fee_with_gst}"
    
    # 5 bps fee becomes 5.9 bps
    bps_fee = 0.0005
    bps_gst = apply_gst_to_fee(bps_fee)
    assert abs(bps_gst - 0.00059) < 1e-9


def test_tax_scenario_a_no_loss_offset():
    # Trade 1: +$100, Trade 2: -$50
    trades = [100.0, -50.0]
    turnovers = [1000.0, 1000.0]
    res_a = calculate_tax_scenario_a(trades, turnovers=turnovers)

    assert res_a["net_pnl_pre_tax"] == 50.0
    # Tax is 31.2% on $100 = $31.20
    assert abs(res_a["tax_liability"] - 31.20) < 1e-6
    # After tax P&L = $50.00 - $31.20 = $18.80
    assert abs(res_a["after_tax_pnl"] - 18.80) < 1e-6
    # Effective tax rate on net profit = 31.20 / 50 = 62.4%
    assert abs(res_a["effective_tax_rate"] - 0.624) < 1e-6
    # TDS = 1% on $2000 = $20.00
    assert abs(res_a["tds_cash_flow_withheld"] - 20.00) < 1e-6


def test_tax_scenario_b_netted_gains():
    # Trade 1: +$100, Trade 2: -$50
    trades = [100.0, -50.0]
    res_b = calculate_tax_scenario_b(trades)

    assert res_b["net_pnl_pre_tax"] == 50.0
    # Tax is 31.2% on netted $50 = $15.60
    assert abs(res_b["tax_liability"] - 15.60) < 1e-6
    # After tax P&L = $50.00 - $15.60 = $34.40
    assert abs(res_b["after_tax_pnl"] - 34.40) < 1e-6
    assert abs(res_b["effective_tax_rate"] - 0.312) < 1e-6


def test_tax_scenario_b_loss_yields_zero_tax():
    # Net loss of -$20
    trades = [30.0, -50.0]
    res_b = calculate_tax_scenario_b(trades)
    assert res_b["net_pnl_pre_tax"] == -20.0
    assert res_b["tax_liability"] == 0.0
    assert res_b["after_tax_pnl"] == -20.0


def test_tax_scenario_a_all_losing_trades():
    trades = [-10.0, -20.0]
    res_a = calculate_tax_scenario_a(trades)
    assert res_a["net_pnl_pre_tax"] == -30.0
    assert res_a["tax_liability"] == 0.0
    assert res_a["after_tax_pnl"] == -30.0


def test_indian_financial_year():
    assert get_financial_year("2026-03-31") == "FY2025-26"
    assert get_financial_year("2026-04-01") == "FY2026-27"
    assert get_financial_year("2026-10-28") == "FY2026-27"
    assert get_financial_year("2027-01-15") == "FY2026-27"


def test_evaluate_series_after_tax():
    df = pd.DataFrame({
        "as_of": ["2026-02-15", "2026-05-10", "2026-06-15"],
        "pnl": [50.0, 100.0, -40.0],
    })
    res = evaluate_series_after_tax(df)
    assert "FY2025-26" in res["by_fy"]
    assert "FY2026-27" in res["by_fy"]
    assert abs(res["total_pre_tax_pnl"] - 110.0) < 1e-6
    # Scenario A: FY25-26 tax on $50 = $15.60; FY26-27 tax on $100 = $31.20. Total tax = $46.80
    assert abs(res["total_tax_scenario_a"] - 46.80) < 1e-6
    # Scenario B: FY25-26 tax on $50 = $15.60; FY26-27 tax on $60 = $18.72. Total tax = $34.32
    assert abs(res["total_tax_scenario_b"] - 34.32) < 1e-6


if __name__ == "__main__":
    test_gst_on_platform_fees()
    test_tax_scenario_a_no_loss_offset()
    test_tax_scenario_b_netted_gains()
    test_tax_scenario_b_loss_yields_zero_tax()
    test_tax_scenario_a_all_losing_trades()
    test_indian_financial_year()
    test_evaluate_series_after_tax()
    print("SUCCESS: All tax module tests passed!")
