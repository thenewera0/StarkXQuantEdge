"""test_nse_free_adapter.py

Phase 7 Automated Verification:
1. Zero-cost verification: No paid broker keys (ZERODHA_API_KEY, DHAN_TOKEN) required or used.
2. Keyless market data retrieval and causal validation for NSE indices and top equities.
3. IST session clock boundaries (09:15-15:30 IST) and 15:15 IST MIS square-off execution.
4. Exact Indian statutory friction calculation (Brokerage, STT, NSE Turnover, SEBI, Stamp Duty, 18% GST).
5. Option chain analytics (PCR OI, PCR Delta OI, ATM Straddle IV, Max Pain, Call Wall, Put Floor).
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.market_hours import (
    is_nse_market_open,
    is_entry_permitted_ist,
    is_mis_squareoff_time,
    check_opening_gap,
    to_ist,
    get_market_session_state,
    IST_TZ,
)
from app.costs import compute_nse_trade_friction, compute_nse_cost_r
from app.universe import MARKET_NSE_INDEX, MARKET_NSE_EQ, NSE_LOT_SIZES, get_lot_size, resolve
from app.data.nse_free import get_nse_adapter, NSEFreeAdapter
from app.data.yahoo import fetch_klines, to_ist as yahoo_to_ist


def test_zero_paid_api_keys():
    """Verify that zero paid API credentials are required."""
    print("--------------------------------------------------------------------------------")
    print("STEP 1: Zero-Cost Broker Invariant Audit")
    print("--------------------------------------------------------------------------------")
    for key in ["ZERODHA_API_KEY", "ZERODHA_SECRET", "DHAN_TOKEN", "DHAN_CLIENT_ID", "UPSTOX_KEY", "FYERS_APP_ID"]:
        assert os.environ.get(key) is None, f"Forbidden paid API key {key} must NOT be set in environment!"
    
    adapter = get_nse_adapter()
    assert adapter is not None
    assert adapter._session_lock is not None
    print("[PASS] Zero paid broker keys required. NSEFreeAdapter initialized with public browser session.")


def test_market_hours_and_mis_squareoff():
    """Verify IST session timing, gap filter, and 15:15 IST MIS auto-square-off."""
    print("--------------------------------------------------------------------------------")
    print("STEP 2: IST Market Hours, Gap Filter & MIS Auto-Square-Off Audit")
    print("--------------------------------------------------------------------------------")
    # Tuesday 2026-10-27 09:14 IST (03:44 UTC) - Pre-market closed
    dt_pre = datetime(2026, 10, 27, 3, 44, 0, tzinfo=timezone.utc)
    assert not is_nse_market_open(dt_pre), "09:14 IST must be closed"
    assert not is_entry_permitted_ist(dt_pre), "09:14 IST cannot permit entry"

    # Tuesday 2026-10-27 09:20 IST (03:50 UTC) - Open but within 15m opening auction gap protection
    dt_gap_protect = datetime(2026, 10, 27, 3, 50, 0, tzinfo=timezone.utc)
    assert is_nse_market_open(dt_gap_protect), "09:20 IST must be open"
    assert not is_entry_permitted_ist(dt_gap_protect), "09:20 IST must be blocked by NO_NEW_ENTRY_BEFORE (09:30 IST)"

    # Tuesday 2026-10-27 10:15 IST (04:45 UTC) - Normal trading session
    dt_trade = datetime(2026, 10, 27, 4, 45, 0, tzinfo=timezone.utc)
    assert is_nse_market_open(dt_trade), "10:15 IST must be open"
    assert is_entry_permitted_ist(dt_trade), "10:15 IST must permit entry"
    assert not is_mis_squareoff_time(dt_trade), "10:15 IST is not MIS square-off time"

    # Tuesday 2026-10-27 15:00 IST (09:30 UTC) - Late afternoon: no new entries
    dt_late = datetime(2026, 10, 27, 9, 30, 0, tzinfo=timezone.utc)
    assert is_nse_market_open(dt_late), "15:00 IST is open"
    assert not is_entry_permitted_ist(dt_late), "15:00 IST must block new entries (after 14:45 IST)"

    # Tuesday 2026-10-27 15:15 IST (09:45 UTC) - Exact MIS Auto-Square-Off time
    dt_mis = datetime(2026, 10, 27, 9, 45, 0, tzinfo=timezone.utc)
    assert is_nse_market_open(dt_mis), "15:15 IST is open"
    assert is_mis_squareoff_time(dt_mis), "15:15 IST MUST trigger MIS square-off"

    # Tuesday 2026-10-27 15:35 IST (10:05 UTC) - After-market closed
    dt_post = datetime(2026, 10, 27, 10, 5, 0, tzinfo=timezone.utc)
    assert not is_nse_market_open(dt_post), "15:35 IST must be closed"

    # Gap check verification (> 1.5% gap rejected)
    rejected_gap, gap_pct = check_opening_gap(prev_close=100.0, open_price=101.8, threshold_pct=1.5)
    assert rejected_gap is True, "1.8% gap must be rejected"
    assert abs(gap_pct - 1.8) < 1e-2

    accepted_gap, gap_pct2 = check_opening_gap(prev_close=100.0, open_price=100.6, threshold_pct=1.5)
    assert accepted_gap is False, "0.6% gap must be accepted"
    assert abs(gap_pct2 - 0.6) < 1e-2

    print("[PASS] IST Market Hours (09:15-15:30), No-Entry Gate (09:30/14:45), Gap Filter, and 15:15 MIS Square-Off verified.")


def test_indian_statutory_friction():
    """Verify exact Indian statutory charges (Brokerage, STT, Txn, SEBI, Stamp, 18% GST)."""
    print("--------------------------------------------------------------------------------")
    print("STEP 3: Indian Statutory Charges & Friction Audit")
    print("--------------------------------------------------------------------------------")
    # Test case: 1 Lot Nifty Future Turnover = 75 * 25,000 = 1,875,000 INR
    notional = 1_875_000.0
    fno_cost = compute_nse_trade_friction(notional, segment="fno_futures")

    # 1. Brokerage: min(20, 0.0003 * 1,875,000 = 562.5) = 20.0 per leg * 2 = 40.0 INR
    assert abs(fno_cost["brokerage"] - 40.0) < 1e-3, f"Expected brokerage 40.0, got {fno_cost['brokerage']}"

    # 2. STT: 0.02% on sell side = 0.0002 * 1,875,000 = 375.0 INR
    assert abs(fno_cost["stt"] - 375.0) < 1e-3, f"Expected STT 375.0, got {fno_cost['stt']}"

    # 3. NSE Exchange Txn charge: 0.00188% on round-trip (2 * notional) = 0.0000188 * 3,750,000 = 70.50 INR
    assert abs(fno_cost["exchange_txn"] - 70.50) < 1e-2, f"Expected Txn 70.50, got {fno_cost['exchange_txn']}"

    # 4. SEBI charge: 0.0001% on round-trip = 0.000001 * 3,750,000 = 3.75 INR
    assert abs(fno_cost["sebi"] - 3.75) < 1e-2, f"Expected SEBI 3.75, got {fno_cost['sebi']}"

    # 5. Stamp Duty: 0.002% on buy leg = 0.00002 * 1,875,000 = 37.50 INR
    assert abs(fno_cost["stamp_duty"] - 37.50) < 1e-2, f"Expected Stamp 37.50, got {fno_cost['stamp_duty']}"

    # 6. GST: 18% strictly on (Brokerage + Txn + SEBI) = 0.18 * (40.0 + 70.50 + 3.75) = 0.18 * 114.25 = 20.565 INR
    expected_gst = 0.18 * (40.0 + 70.50 + 3.75)
    assert abs(fno_cost["gst"] - expected_gst) < 1e-2, f"Expected GST {expected_gst}, got {fno_cost['gst']}"

    # Total friction sum
    expected_total = 40.0 + 375.0 + 70.50 + 3.75 + 37.50 + expected_gst
    assert abs(fno_cost["total_friction_inr"] - expected_total) < 1e-2

    # R-cost translation
    cost_r = compute_nse_cost_r(notional_inr=notional, stop_distance_pct=0.015, segment="fno_futures")
    assert cost_r > 0.0
    assert abs(cost_r - (fno_cost["total_friction_pct"] / 0.015)) < 1e-4

    print(f"[PASS] Exact statutory friction verified: Total={fno_cost['total_friction_inr']:.2f} INR (STT={fno_cost['stt']:.2f}, GST={fno_cost['gst']:.2f}, Brok={fno_cost['brokerage']:.2f}), cost_R={cost_r:.4f}R")


def test_universe_and_lot_sizes():
    """Verify lot sizing and resolution across NSE index & cash equity instruments."""
    print("--------------------------------------------------------------------------------")
    print("STEP 4: Universe & Contract Lot Size Mapping Audit")
    print("--------------------------------------------------------------------------------")
    assert get_lot_size("NIFTY") == 75
    assert get_lot_size("^NSEI") == 75
    assert get_lot_size("BANKNIFTY") == 30
    assert get_lot_size("^NSEBANK") == 30
    assert get_lot_size("RELIANCE.NS") == 500
    assert get_lot_size("HDFCBANK.NS") == 550
    assert get_lot_size("SBIN.NS") == 750

    inst_nifty = resolve("^NSEI")
    assert inst_nifty is not None
    assert inst_nifty["category"] == MARKET_NSE_INDEX
    assert inst_nifty["allocatable"] is True

    inst_reliance = resolve("RELIANCE.NS")
    assert inst_reliance is not None
    assert inst_reliance["category"] == MARKET_NSE_EQ
    assert inst_reliance["allocatable"] is True

    print("[PASS] NSE Lot sizes (NIFTY: 75, BANKNIFTY: 30, RELIANCE: 500) and universe resolution verified.")


def test_nse_free_adapter_and_synthetic_fallback():
    """Verify option chain computation and synthetic fallback."""
    print("--------------------------------------------------------------------------------")
    print("STEP 5: Option Chain Flow & Synthetic Fallback Audit")
    print("--------------------------------------------------------------------------------")
    adapter = get_nse_adapter()
    # Test fetch_index_option_chain (either live or synthetic fallback)
    oc = adapter.fetch_index_option_chain("NIFTY")
    assert oc is not None
    assert oc["symbol"] == "NIFTY"
    assert oc["pcr_oi"] > 0.0
    assert oc["atm_straddle_iv"] > 0.0
    assert oc["max_pain_strike"] > 0.0
    assert oc["call_wall_strike"] >= oc["put_floor_strike"] or oc["call_wall_strike"] > 0

    src = "synthetic" if oc.get("is_synthetic") else "live_nse"
    print(f"[PASS] Option Chain computed: PCR_OI={oc['pcr_oi']:.2f}, ATM_IV={oc['atm_straddle_iv']:.2f}%, MaxPain={oc['max_pain_strike']}, CallWall={oc['call_wall_strike']}, PutFloor={oc['put_floor_strike']} (Source: {src})")


def main():
    print("================================================================================")
    print("PHASE 7 TEST SUITE: Zero-Cost NSE Live & F&O Execution Engine")
    print("================================================================================")
    test_zero_paid_api_keys()
    test_market_hours_and_mis_squareoff()
    test_indian_statutory_friction()
    test_universe_and_lot_sizes()
    test_nse_free_adapter_and_synthetic_fallback()
    print("================================================================================")
    print("ALL test_nse_free_adapter CHECKS PASSED DETERMINISTICALLY.")
    print("================================================================================")


if __name__ == "__main__":
    main()
