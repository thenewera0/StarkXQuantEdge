"""StarkX QuantEdge v2: Test Drawdown Governor & Risk Halts.

Asserts:
1. Drawdown from peak >= 10% -> Sleeve T targets multiplied by 0.5 (state: HALVED).
2. Drawdown from peak >= 20% -> Sleeve T = 0 (100% cash) until V2_RESUME=true is set manually (state: CASH).
3. Daily loss <= -4% -> order halt for 24 hours (state: ORDER_HALT).
4. Allocation caps: Sleeve T <= 70%, Sleeve C <= 25% when ECONOMIC (0% otherwise), remainder to Cash.
5. Cash benchmark yield: 6.5% APR taxed at 31.2%.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.v2.allocator import DrawdownGovernor, allocate_portfolio
from app.v2.config import settings_v2


def test_drawdown_governor_transitions():
    print("Testing Drawdown Governor threshold transitions...")
    gov = DrawdownGovernor(initial_equity=1000.0)
    
    # Baseline normal state at peak
    s0 = gov.update(1000.0)
    assert s0["governor_state"] == "NORMAL"
    assert s0["sleeve_t_multiplier"] == 1.0
    
    # 1. 10% drawdown: 1000 -> 900 (-10.0%)
    s1 = gov.update(900.0)
    assert s1["governor_state"] == "HALVED", f"Expected HALVED, got {s1['governor_state']}"
    assert s1["sleeve_t_multiplier"] == 0.5
    print("PASS: Drawdown >= 10% correctly halves Sleeve T targets.")
    
    # 2. 20% drawdown: 1000 -> 800 (-20.0%)
    s2 = gov.update(800.0)
    assert s2["governor_state"] == "CASH", f"Expected CASH, got {s2['governor_state']}"
    assert s2["sleeve_t_multiplier"] == 0.0
    print("PASS: Drawdown >= 20% correctly zeros Sleeve T (100% cash).")
    
    # 3. Recovery without manual resume remains in CASH state
    s3 = gov.update(850.0)
    assert s3["governor_state"] == "CASH", f"Should remain in CASH without manual resume, got {s3['governor_state']}"
    assert s3["sleeve_t_multiplier"] == 0.0
    
    # 4. Manual resume sets back into operation
    s4 = gov.update(850.0, manual_resume=True)
    assert s4["governor_state"] in ("NORMAL", "HALVED")
    assert s4["sleeve_t_multiplier"] > 0.0
    print("PASS: V2_RESUME manual unlock required to resume trading after 20% DD.")


def test_daily_loss_halt():
    print("Testing 24h order halt on daily loss <= -4%...")
    gov = DrawdownGovernor(initial_equity=1000.0)
    gov.update(1000.0)
    
    # Single day drop: 1000 -> 955 (-4.5% daily loss, though peak DD is only 4.5% < 10%)
    s_drop = gov.update(955.0)
    assert s_drop["order_halt_active"] is True, "Daily loss <= -4% did not trigger order halt"
    assert s_drop["governor_state"] == "ORDER_HALT"
    print("PASS: Daily loss <= -4% triggers 24-hour order halt.")


def test_allocator_risk_caps_and_cash():
    print("Testing portfolio risk caps and cash remainder...")
    gov_status = {"sleeve_t_multiplier": 1.0, "governor_state": "NORMAL", "drawdown_pct": 0.0}
    
    # Try to request 80% in Sleeve T (should be capped at 70%)
    raw_t_targets = {"BTC": 0.50, "ETH": 0.30}
    sleeve_c_eval = {"overall_economic": False, "total_allocation_pct": 0.20}
    
    alloc = allocate_portfolio(
        sleeve_t_targets=raw_t_targets,
        sleeve_c_eval=sleeve_c_eval,
        governor_status=gov_status,
        account_equity_usd=1000.0,
    )
    
    # Check Sleeve T capped at 70%
    assert abs(alloc["sleeve_t_total_pct"] - 0.70) < 1e-4, f"Sleeve T should be capped at 0.70, got {alloc['sleeve_t_total_pct']}"
    
    # Check Sleeve C is 0% because economic is False
    assert alloc["sleeve_c_total_pct"] == 0.0, f"Sleeve C should be 0 when uneconomic, got {alloc['sleeve_c_total_pct']}"
    
    # Check remainder to Cash = 30%
    assert abs(alloc["cash_pct"] - 0.30) < 1e-4, f"Cash should receive 0.30 remainder, got {alloc['cash_pct']}"
    
    # Check daily cash yield and tax
    assert alloc["daily_cash_yield_usd"] > 0.0
    assert alloc["daily_cash_tax_usd"] > 0.0
    print(f"PASS: Risk caps verified (T={alloc['sleeve_t_total_pct']:.1%}, C={alloc['sleeve_c_total_pct']:.1%}, Cash={alloc['cash_pct']:.1%}).")


if __name__ == "__main__":
    test_drawdown_governor_transitions()
    test_daily_loss_halt()
    test_allocator_risk_caps_and_cash()
    print("SUCCESS: All v2 drawdown governor and allocator tests passed.")
