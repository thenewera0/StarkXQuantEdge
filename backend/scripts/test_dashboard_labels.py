"""test_dashboard_labels.py

Section 7.1 & 9:
test_dashboard_labels:
Enforces:
1. NO "REAL CAPITAL" string anywhere in the frontend files (case-insensitive check for 'REAL CAPITAL').
2. "PAPER · VIRTUAL" label is properly present in frontend dashboard cards and lab page.
3. Overview card uses ledger-true figures (-241 / -240.81) and includes the ledger-verified badge.
4. "Frozen forward test: quiet by design" notice exists under Core.
"""

import os
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"


def main():
    print("================================================================================")
    print("TEST 9.12: test_dashboard_labels (Zero 'REAL CAPITAL' & 'PAPER · VIRTUAL' Audit)")
    print("================================================================================")

    assert FRONTEND_DIR.exists(), f"Frontend dir not found at {FRONTEND_DIR}"

    scanned_exts = {".tsx", ".ts", ".jsx", ".js", ".html", ".json"}
    ignore_dirs = {".next", "node_modules", ".git", "build", "dist"}

    found_forbidden = []
    scanned_count = 0

    for root, dirs, files in os.walk(FRONTEND_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            p = Path(root) / f
            if p.suffix in scanned_exts:
                scanned_count += 1
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as file:
                        content = file.read()
                        # Search for "REAL CAPITAL", "LIVE INCL", "CAPITAL AT RISK" (case-insensitive)
                        matches = re.finditer(r"\b(REAL\s+CAPITAL|LIVE\s+INCL|REAL\s+CAPITAL\s+AT\s+RISK)\b", content, re.IGNORECASE)
                        for m in matches:
                            line_num = content[:m.start()].count("\n") + 1
                            found_forbidden.append(f"{p.relative_to(FRONTEND_DIR)}:{line_num} -> '{m.group(0)}'")
                except Exception as e:
                    print(f"Warning: could not read {p}: {e}")

    print(f"Scanned {scanned_count} frontend source files.")

    if found_forbidden:
        print("[FAIL] Found forbidden 'REAL CAPITAL' occurrences in frontend:")
        for item in found_forbidden:
            print(f"  - {item}")
        sys.exit(1)

    print("[PASS] ZERO occurrences of 'REAL CAPITAL' found anywhere in the frontend.")

    # Check that CombinedPnl.tsx contains 'PAPER · VIRTUAL'
    combined_pnl_file = FRONTEND_DIR / "components" / "CombinedPnl.tsx"
    assert combined_pnl_file.exists()
    with open(combined_pnl_file, "r", encoding="utf-8") as f:
        pnl_text = f.read()
        assert "PAPER · VIRTUAL" in pnl_text, "CombinedPnl.tsx missing 'PAPER · VIRTUAL' label!"
        assert "Ledger-verified" in pnl_text or "ShieldCheck" in pnl_text, "CombinedPnl.tsx missing Ledger-verified badge!"
        assert "Frozen forward test: quiet by design" in pnl_text, "CombinedPnl.tsx missing quiet by design note!"
        assert "-240.81" in pnl_text or "-241" in pnl_text, "CombinedPnl.tsx missing ledger-true figures (-241 / -240.81)!"
    print("[PASS] CombinedPnl.tsx verified: 'PAPER · VIRTUAL', ledger-verified badge, quiet by design note, and ledger-true figures.")

    # Check DashboardComponents.tsx contains Open Lab Positions and Active Variants
    dash_comp_file = FRONTEND_DIR / "components" / "DashboardComponents.tsx"
    assert dash_comp_file.exists()
    with open(dash_comp_file, "r", encoding="utf-8") as f:
        dash_text = f.read()
        assert "Open Lab Positions" in dash_text, "DashboardComponents.tsx missing 'Open Lab Positions' card!"
        assert "Active Variants" in dash_text, "DashboardComponents.tsx missing 'Active Variants' card!"
    print("[PASS] DashboardComponents.tsx verified: 'Open Lab Positions' and 'Active Variants' cards present.")

    # Check Lab page contains 'PAPER · VIRTUAL'
    lab_page_file = FRONTEND_DIR / "app" / "lab" / "page.tsx"
    assert lab_page_file.exists()
    with open(lab_page_file, "r", encoding="utf-8") as f:
        lab_text = f.read()
        assert "PAPER · VIRTUAL" in lab_text, "Lab page.tsx missing 'PAPER · VIRTUAL' badge!"
    print("[PASS] app/lab/page.tsx verified: 'PAPER · VIRTUAL' banner present.")

    # Check LayoutComponents.tsx contains all 11 navigation tabs with ZERO dead '#' links
    layout_comp_file = FRONTEND_DIR / "components" / "LayoutComponents.tsx"
    assert layout_comp_file.exists(), "LayoutComponents.tsx missing!"
    with open(layout_comp_file, "r", encoding="utf-8") as f:
        layout_text = f.read()
        required_tabs = [
            "overview", "flash", "live", "markets", "investments",
            "fund", "analytics", "history", "arbitrage", "portfolio", "lab"
        ]
        for tab in required_tabs:
            assert f'key: "{tab}"' in layout_text, f"Navigation tab '{tab}' missing in LayoutComponents.tsx!"
        assert 'href="#"' not in layout_text, "Found dead href='#' in LayoutComponents.tsx!"
    print("[PASS] LayoutComponents.tsx verified: all 11 navigation tabs wired with zero dead href='#' links.")

    print("================================================================================")
    print("ALL test_dashboard_labels CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
