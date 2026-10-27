"""CI verification test: Checksum & Parameter Integrity of Frozen Core 4h Long.

Rule 0.5.7: Forward test rule: no parameter, gate, or weight change to core_4h_long
until >= 100 new paper trades after freeze_timestamp. This test fails if the frozen
parameter set or checksum changes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings

FROZEN_V1_SHA256 = "e224027c42f068fca34db70e2f60e0a8fcc27acfc9c6e946765563556d837cf3"
FROZEN_V1_1_SHA256 = "3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928"


def main() -> int:
    root_dir = Path(__file__).resolve().parents[2]
    # Check v1.1 first
    v1_1_file = root_dir / "config" / "frozen_core_long_v1_1.json"
    if not v1_1_file.exists():
        v1_1_file = Path(__file__).resolve().parents[1] / "config" / "frozen_core_long_v1_1.json"

    if v1_1_file.exists():
        data = json.loads(v1_1_file.read_text(encoding="utf-8"))
        stored_sha = data.get("sha256")
        params = data.get("parameters", {})
        recomputed_sha = hashlib.sha256(json.dumps(params, sort_keys=True, indent=2).encode("utf-8")).hexdigest()

        if recomputed_sha != FROZEN_V1_1_SHA256 or stored_sha != FROZEN_V1_1_SHA256:
            print(f"FAILED: Frozen v1.1 parameter checksum mismatch!")
            print(f"  Expected:   {FROZEN_V1_1_SHA256}")
            print(f"  Stored:     {stored_sha}")
            print(f"  Recomputed: {recomputed_sha}")
            return 1

        mismatches = []
        for k, v in params.items():
            if not hasattr(settings, k):
                mismatches.append(f"Missing attribute {k} in settings")
                continue
            live_val = getattr(settings, k)
            if live_val != v:
                mismatches.append(f"Parameter '{k}' changed: frozen={v} vs live={live_val}")

        if mismatches:
            print("FAILED: Live settings do not match frozen v1.1 parameter set:")
            for m in mismatches:
                print(f"  - {m}")
            return 1

        print(f"SUCCESS: Frozen v1.1 parameter integrity verified (SHA256: {FROZEN_V1_1_SHA256}).")
        return 0
        return 1

    print(f"SUCCESS: Frozen parameter integrity verified (SHA256: {FROZEN_SHA256}).")
    print(f"Core 4h Long parameters are locked for paper forward-testing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
