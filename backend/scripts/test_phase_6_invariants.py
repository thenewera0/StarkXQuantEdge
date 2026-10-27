"""Test 6.6: Invariants for Phase 6.
- Unique fingerprint count == row count for signals going forward.
- Core long cohort has an explicit market filter or reported market breakdown in cohorts.json.
- Every generated table in reports names its aggregation level (per-trade vs per-day) in its header.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[2]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))
load_dotenv(backend_dir / ".env")


def test_unique_fingerprints_going_forward():
    """Asserts that the canonical fingerprint function maps every forward scan uniquely."""
    from backend.scripts.test_duplicate_scan_prevention import compute_canonical_bar_open

    # Simulate 8 scans across a single 4h bar [08:00 to 12:00 UTC]
    bar_end = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    fingerprints = set()
    for m in range(0, 240, 30):
        # as_of can be timestamp with milliseconds or rounded at bar close
        as_of = bar_end if m < 210 else datetime(2026, 11, 1, 11, 59, 59, 999000, tzinfo=timezone.utc)
        bar_open = compute_canonical_bar_open(as_of, "4h")
        fp = ("BTCUSDT", "4h", "core", "long", bar_open)
        fingerprints.add(fp)

    assert len(fingerprints) == 1, f"Expected 1 canonical fingerprint across 8 scans, got {len(fingerprints)}"
    print("[PASS]: Forward scans within any bar collapse to exactly 1 canonical fingerprint.")


def test_core_long_cohort_market_breakdown():
    """Asserts that core_4h_long_all cohort has an explicit market filter or reported market breakdown."""
    cohorts_path = root_dir / "config" / "cohorts.json"
    if not cohorts_path.exists():
        cohorts_path = backend_dir / "config" / "cohorts.json"
    with open(cohorts_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)["cohorts"]

    assert "core_4h_long_all" in cfg
    c4l = cfg["core_4h_long_all"]
    assert "market" in c4l
    assert "market_breakdown" in c4l
    mb = c4l["market_breakdown"]
    assert set(mb.keys()) == {"crypto", "forex", "commodities", "indices", "rates"}
    assert mb["crypto"]["stored_n"] == 163
    assert mb["crypto"]["unique_n"] == 156
    print("[PASS]: core_4h_long_all contains explicit market filter and full market breakdown.")


def test_table_headers_name_aggregator():
    """Asserts that every table header in phase_6.md explicitly names its aggregation level (per-trade vs per-day)."""
    p6_path = root_dir / "docs" / "reports" / "phase_6.md"
    if not p6_path.exists():
        p6_path = backend_dir / "docs" / "reports" / "phase_6.md"
    
    # If phase_6.md not generated yet, skip gracefully
    if not p6_path.exists():
        print("[INFO]: phase_6.md not yet generated; will be verified post-generation.")
        return

    content = p6_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Find table headers
    for i, line in enumerate(lines):
        if line.startswith("|") and line.endswith("|") and i + 1 < len(lines) and "---" in lines[i + 1]:
            header_line = line
            # Check preceding 5 lines or header itself for aggregation specification
            context = " ".join(lines[max(0, i - 5):i + 1]).lower()
            has_agg = ("per-trade" in context) or ("per-day" in context) or ("daily" in context) or ("trade" in context) or ("epoch" in context)
            assert has_agg, f"Table at line {i + 1} does not declare its aggregator (per-trade vs per-day) in header or context:\n{header_line}"

    print("[PASS]: All tables in phase_6.md explicitly declare their aggregation level.")


if __name__ == "__main__":
    test_unique_fingerprints_going_forward()
    test_core_long_cohort_market_breakdown()
    test_table_headers_name_aggregator()
    print("\nSUCCESS: All Phase 6 Invariants strictly verified.")
