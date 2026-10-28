import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "backend"))
sys.path.insert(0, str(root_dir))

from backend.scripts.test_tax import *

if __name__ == "__main__":
    test_gst_on_platform_fees()
    test_tax_scenario_a_no_loss_offset()
    test_tax_scenario_b_netted_gains()
    test_tax_scenario_b_loss_yields_zero_tax()
    test_tax_scenario_a_all_losing_trades()
    test_indian_financial_year()
    test_evaluate_series_after_tax()
    print("SUCCESS: All tax module tests passed!")
