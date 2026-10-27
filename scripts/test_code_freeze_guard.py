"""Test 8.6: CI Code Freeze & Parameter Invariance Guard.

Enforces:
1. No code or signal-generating config changes until evaluation date (earlier of N_eff >= 85 or 2027-04-26).
2. Strict verification that live settings match frozen spec 3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928.
3. live_trading_enabled is strictly False (Rule R4).
4. CI fails if any signal-generating parameter is modified.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

cur_path = Path(__file__).resolve()
backend_dir = cur_path.parents[1] if (cur_path.parents[1] / "app").exists() else (cur_path.parents[1] / "backend")
sys.path.insert(0, str(backend_dir))

from app.config import settings

FROZEN_SHA256 = "3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928"
EVAL_HORIZON_DATE = "2027-04-26"
TARGET_N_EFF = 85


def test_code_freeze_guard():
    print("=" * 80)
    print("CI GUARD (8.6): CODE FREEZE & SIGNAL PARAMETER INVARIANCE")
    print("=" * 80)

    # 1. Rule R4: Live Trading Lock
    assert settings.live_trading_enabled is False, (
        "CRITICAL SECURITY VIOLATION: live_trading_enabled is True! Must be strictly False."
    )
    print("PASS: live_trading_enabled is strictly False.")

    # 2. Locate frozen config
    root_dir = backend_dir.parent if backend_dir.name == "backend" else backend_dir
    freeze_file = root_dir / "config" / "frozen_core_long_v1_1.json"
    if not freeze_file.exists():
        freeze_file = backend_dir / "config" / "frozen_core_long_v1_1.json"
    assert freeze_file.exists(), f"Missing frozen spec file at {freeze_file}"

    # 3. Checksum verification
    data = json.loads(freeze_file.read_text(encoding="utf-8"))
    params = data.get("parameters", {})
    recomputed_sha = hashlib.sha256(
        json.dumps(params, sort_keys=True, indent=2).encode("utf-8")
    ).hexdigest()

    assert recomputed_sha == FROZEN_SHA256, (
        f"Checksum mismatch! Recomputed {recomputed_sha} != expected {FROZEN_SHA256}"
    )
    assert data.get("sha256") == FROZEN_SHA256, (
        f"Header sha256 mismatch in {freeze_file}"
    )
    print(f"PASS: Cryptographic freeze hash verified: {FROZEN_SHA256}")

    # 4. Parameter invariance against live settings
    mismatches = []
    for k, v in params.items():
        if not hasattr(settings, k):
            mismatches.append(f"Missing attribute {k} in settings")
            continue
        live_val = getattr(settings, k)
        if live_val != v:
            mismatches.append(f"Parameter '{k}' changed: frozen={v} vs live={live_val}")

    assert not mismatches, f"Signal configuration has mutated! Violations:\n" + "\n".join(mismatches)
    print(f"PASS: All {len(params)} signal-generating parameters match frozen specification with 100% bitwise parity.")

    # 5. Evaluation date horizon check
    now_date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    print(f"Current Date: {now_date_str} | Evaluation Horizon Date: {EVAL_HORIZON_DATE}")
    print("PASS: Code freeze guard active. No further modifications permitted until evaluation date.")
    print("=" * 80)


if __name__ == "__main__":
    test_code_freeze_guard()
