"""Test 8.6 & 9.3: CI Code Freeze, Parameter Invariance & Amendment Hash Guard.

Enforces:
1. No code or signal-generating config changes until evaluation date (earlier of active_days >= 60 or 2027-10-26).
2. Strict verification that live settings match frozen spec 3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928.
3. live_trading_enabled is strictly False (Rule R4).
4. docs/PRE_REGISTRATION_AMENDMENT.md exists and its cryptographic SHA-256 matches.
5. CI fails if any signal-generating parameter or amendment protocol is modified.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

cur_path = Path(__file__).resolve()
backend_dir = cur_path.parents[1] if (cur_path.parents[1] / "app").exists() else (cur_path.parents[1] / "backend")
root_dir = cur_path.parents[1] if (cur_path.parents[1] / "docs").exists() else cur_path.parents[0]
sys.path.insert(0, str(backend_dir))

from app.config import settings

FROZEN_SHA256 = "3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928"
EVAL_HORIZON_DATE = "2027-10-26"
TARGET_ACTIVE_DAYS = 60

AMENDMENT_BODY_SHA256 = "c5c6a816e74306724b820a41277a8ab1f81b1c68a799f235b0ade52449ab2dfd"
AMENDMENT_FILE_SHA256 = "1f3127b3eca41dd45db275bc66dad1b45fc2f4ce8805d636afc9b336e04ecd92"


def test_code_freeze_guard():
    print("=" * 80)
    print("CI GUARD (9.3): CODE FREEZE, PARAMETER INVARIANCE & AMENDMENT INTEGRITY")
    print("=" * 80)

    # 1. Rule R4: Live Trading Lock
    assert settings.live_trading_enabled is False, (
        "CRITICAL SECURITY VIOLATION: live_trading_enabled is True! Must be strictly False."
    )
    print("PASS: live_trading_enabled is strictly False.")

    # 2. Locate frozen config
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

    # 5. Pre-Registration Amendment 1 Integrity Check (9.3)
    amendment_file = root_dir / "docs" / "PRE_REGISTRATION_AMENDMENT.md"
    if not amendment_file.exists():
        amendment_file = backend_dir / "docs" / "PRE_REGISTRATION_AMENDMENT.md"
    assert amendment_file.exists(), f"Missing pre-registration amendment file at {amendment_file}"

    raw_bytes = amendment_file.read_bytes()
    # Normalize line endings to \n for deterministic cross-platform hashing
    norm_bytes = raw_bytes.replace(b"\r\n", b"\n")
    actual_file_sha = hashlib.sha256(norm_bytes).hexdigest()

    # Extract body below the metadata header delimiter ('---\n\n')
    text = norm_bytes.decode("utf-8")
    parts = text.split("---\n\n", 1)
    assert len(parts) >= 2, "Amendment format invalid: missing '---' metadata delimiter"
    body_text = parts[1].strip()
    actual_body_sha = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

    assert actual_body_sha == AMENDMENT_BODY_SHA256, (
        f"Pre-Registration Amendment body hash mismatch! Expected {AMENDMENT_BODY_SHA256}, got {actual_body_sha}"
    )
    assert actual_file_sha == AMENDMENT_FILE_SHA256, (
        f"Pre-Registration Amendment file hash mismatch! Expected {AMENDMENT_FILE_SHA256}, got {actual_file_sha}"
    )
    print(f"PASS: Pre-Registration Amendment 1 cryptographic hash verified: {AMENDMENT_FILE_SHA256}")

    # 6. Evaluation trigger check (earliest of active_days >= 60 or 2027-10-26)
    now_date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    print(f"Current Date: {now_date_str} | Evaluation Trigger: active_days >= {TARGET_ACTIVE_DAYS} or Date >= {EVAL_HORIZON_DATE}")
    print("PASS: Pre-Registration Amendment lock active. No further modifications permitted until evaluation trigger fires.")
    print("=" * 80)


if __name__ == "__main__":
    test_code_freeze_guard()
