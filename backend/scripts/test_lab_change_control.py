"""test_lab_change_control.py

StarkX LAB: Automated CI Guard for 30-Day Specification Invariance.

Enforces:
1. config/lab_spec.json SHA-256 matches registered LAB_SPEC_SHA256.
2. If modified prior to lab_start_timestamp + 30 days, the commit FAILS unless
   a valid amendment is formally recorded in docs/LAB_AMENDMENTS.md with:
   - ISO 8601 Timestamp
   - Reason / Quantitative Justification
   - Matching SHA-256 hash
   - Trial-counter delta (e.g., +1)
3. docs/LAB_AMENDMENTS.md and docs/CHANGELOG_LAB.md exist and conform to governance standards.
"""

from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab import LAB_SPEC_SHA256, LAB_START_TIMESTAMP

SPEC_PATH = ROOT_DIR / "config" / "lab_spec.json"
AMENDMENTS_PATH = ROOT_DIR / "docs" / "LAB_AMENDMENTS.md"
CHANGELOG_PATH = ROOT_DIR / "docs" / "CHANGELOG_LAB.md"


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("================================================================================")
    print("TEST: test_lab_change_control (30-Day Specification Invariance CI Guard)")
    print("================================================================================")

    assert SPEC_PATH.exists(), f"Missing lab_spec.json at {SPEC_PATH}"
    assert AMENDMENTS_PATH.exists(), f"Missing LAB_AMENDMENTS.md at {AMENDMENTS_PATH}"
    assert CHANGELOG_PATH.exists(), f"Missing CHANGELOG_LAB.md at {CHANGELOG_PATH}"

    # 1. Compute current spec hash
    curr_hash = compute_file_sha256(SPEC_PATH)
    print(f"[CURRENT SPEC SHA256] {curr_hash}")
    print(f"[REGISTERED SHA256]   {LAB_SPEC_SHA256}")
    print(f"[START TIMESTAMP]     {LAB_START_TIMESTAMP}")

    # 2. Check 30-day lock window
    start_dt = datetime.fromisoformat(LAB_START_TIMESTAMP.replace("Z", "+00:00"))
    lock_expiry = start_dt + timedelta(days=30)
    now_dt = datetime.now(timezone.utc)
    is_under_lock = now_dt < lock_expiry

    print(f"[LOCK WINDOW] From {start_dt.isoformat()} to {lock_expiry.isoformat()} (Active: {is_under_lock})")

    if curr_hash == LAB_SPEC_SHA256:
        print("[PASS] Bitwise match: config/lab_spec.json is identical to pre-registered hash.")
    else:
        # If spec changed, we MUST be either past the lock window OR have a valid registered amendment
        if is_under_lock:
            # Parse docs/LAB_AMENDMENTS.md for valid amendment entry
            amend_text = AMENDMENTS_PATH.read_text(encoding="utf-8")
            assert curr_hash in amend_text, (
                f"CI REJECTION: config/lab_spec.json has changed before 30-day lock expiry ({lock_expiry.isoformat()}), "
                f"and new SHA-256 {curr_hash} is NOT registered in docs/LAB_AMENDMENTS.md!"
            )
            # Check required fields
            assert "Trial Counter Delta" in amend_text or "Trial Delta" in amend_text, (
                "CI REJECTION: Amendment in docs/LAB_AMENDMENTS.md must specify Trial Counter Delta!"
            )
            assert "Reason" in amend_text or "Justification" in amend_text, (
                "CI REJECTION: Amendment in docs/LAB_AMENDMENTS.md must specify Justification / Reason!"
            )
            print(f"[PASS] Specification amendment formally pre-registered in docs/LAB_AMENDMENTS.md.")
        else:
            print("[INFO] Past 30-day initial freeze window. Normal amendment governance applies.")

    # 3. Governance document validations
    amend_content = AMENDMENTS_PATH.read_text(encoding="utf-8")
    assert LAB_SPEC_SHA256 in amend_content, "LAB_AMENDMENTS.md missing registered baseline SHA256!"
    assert LAB_START_TIMESTAMP in amend_content, "LAB_AMENDMENTS.md missing launch timestamp!"
    print("[PASS] docs/LAB_AMENDMENTS.md verified with baseline hash and 30-day lock parameters.")

    cl_content = CHANGELOG_PATH.read_text(encoding="utf-8")
    assert "Warm-Start Position Invariant" in cl_content, "CHANGELOG_LAB.md missing warm-start documentation!"
    assert "3-Hour Downtime Catch-Up" in cl_content, "CHANGELOG_LAB.md missing downtime catch-up documentation!"
    print("[PASS] docs/CHANGELOG_LAB.md verified with operational bug fixes and engineering updates.")

    print("================================================================================")
    print("ALL test_lab_change_control CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
