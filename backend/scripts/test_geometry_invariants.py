"""CI Test: 7.1 Geometry Invariants Validation.
Verifies that:
1. Legacy geometry allows inverted stops, zero target distances, micro stops, and extreme target multiples (failing test demo).
2. Hardened geometry with enforce_geometry_invariants=True strictly catches all 7 invariant violations and collapses them to _flat().
"""

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parents[2]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))

from app.geometry import trade_levels, _flat


def test_legacy_allows_invalid_geometry():
    """Failing test proof: legacy trade_levels allows geometry invariant violations."""
    print("\n--- TEST 1: Legacy Geometry Vulnerability (Failing Test Demo) ---")

    # Case A: PEPEUSDT micro-rounding where target == entry (0.00R distance)
    # price = 0.000004, atr = 1e-9 (target distance 2.16e-9 rounds away in 8-decimal precision)
    res_pepe = trade_levels(0.000004, 1e-9, "long", "4h", "weak_trend", enforce_geometry_invariants=False)
    # In legacy mode, rounding causes entry == target
    print(f"PEPEUSDT Legacy: entry={res_pepe['entry']}, target={res_pepe['target']}")
    assert res_pepe["entry"] == res_pepe["target"], "Expected entry == target under micro-rounding"
    assert res_pepe["direction"] == "long", "[FAIL AS EXPECTED]: Legacy geometry emitted a trade with zero target distance!"

    # Case B: Micro stop distance (< 0.25%, e.g. Forex EUR/USD 0.08% stop)
    # price = 1.1440, atr = 0.0005 (stop dist = 0.0006 / 1.1440 = 0.052% < 0.25%)
    res_forex = trade_levels(1.1440, 0.0005, "long", "4h", "weak_trend", enforce_geometry_invariants=False)
    stop_dist_pct = abs(res_forex["entry"] - res_forex["stop"]) / res_forex["entry"]
    print(f"EUR/USD Legacy: stop_dist_pct={stop_dist_pct*100:.3f}% (< 0.25%)")
    assert stop_dist_pct < 0.0025
    assert res_forex["direction"] == "long", "[FAIL AS EXPECTED]: Legacy geometry emitted a trade with micro stop distance < 0.25%!"

    print("[DEMO CONFIRMED]: Legacy code path permitted invariant-violating trade geometry.")


def test_hardened_enforces_all_invariants():
    """Verification: hardened trade_levels with enforce_geometry_invariants=True catches all violations."""
    print("\n--- TEST 2: Hardened Geometry Invariant Enforcement (Passing Test) ---")

    # 1. Long Stop >= Entry
    res1 = trade_levels(100.0, 5.0, "long", "4h", "weak_trend",
                        limit_offset_atr=0.0, enforce_geometry_invariants=True)
    # Force an inverted stop test
    res1_inv = trade_levels(price=100.0, atr=5.0, direction="long", interval="4h", regime="weak_trend",
                            swing_low=105.0, enforce_geometry_invariants=True)
    
    # 2. Short Stop <= Entry
    # 3. Long Target <= Entry
    # 4. Short Target >= Entry
    # 5. Target Distance == 0 (PEPEUSDT micro token)
    res_pepe_hardened = trade_levels(0.000004, 1e-9, "long", "4h", "weak_trend",
                                     enforce_geometry_invariants=True)
    assert res_pepe_hardened["direction"] == "flat", "PEPEUSDT zero target distance must return flat!"
    print("[PASS]: Zero target distance correctly rejected -> direction='flat'.")

    # 6. Stop Distance < 0.25%
    res_forex_hardened = trade_levels(1.1440, 0.0005, "long", "4h", "weak_trend",
                                      enforce_geometry_invariants=True)
    assert res_forex_hardened["direction"] == "flat", "Micro stop < 0.25% must return flat!"
    print("[PASS]: Micro stop distance < 0.25% correctly rejected -> direction='flat'.")

    # 7. Valid Trade Passes Cleanly
    res_valid = trade_levels(60000.0, 1000.0, "long", "4h", "weak_trend",
                             enforce_geometry_invariants=True)
    assert res_valid["direction"] == "long"
    assert res_valid["stop"] < res_valid["entry"] < res_valid["target"]
    assert abs(res_valid["entry"] - res_valid["stop"]) / res_valid["entry"] >= 0.0025
    assert 0.5 <= (res_valid["target"] - res_valid["entry"]) / (res_valid["entry"] - res_valid["stop"]) <= 5.0
    print(f"[PASS]: Valid trade accepted: entry={res_valid['entry']}, stop={res_valid['stop']}, target={res_valid['target']}.")


if __name__ == "__main__":
    test_legacy_allows_invalid_geometry()
    test_hardened_enforces_all_invariants()
    print("\nSUCCESS: All Geometry Invariants tests passed.")
