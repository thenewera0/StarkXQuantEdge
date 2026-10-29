"""send_test_alerts.py

StarkX LAB: Operational Test Alert Dispatcher.

Dispatches health-only test alerts (zero P&L figures) for:
1. FEED_STALE: Public market feed latency alert.
2. RECONCILIATION_BREAK: Ledger integrity / audit test.
3. JOB_FAILURE: Cron scheduler / background task test.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab.storage import LabStorage


def dispatch_test_alerts(storage: LabStorage | None = None) -> list[dict]:
    storage = storage or LabStorage()
    now_iso = datetime.now(timezone.utc).isoformat()

    alerts = [
        {
            "kind": "FEED_STALE",
            "variant_id": None,
            "message": f"[TEST ALERT · HEALTH ONLY] Public market data feed lag exceeded threshold (312s > 300s). No real orders, no capital at risk, no P&L affected. Automatic retry scheduled.",
        },
        {
            "kind": "RECONCILIATION_BREAK",
            "variant_id": None,
            "message": f"[TEST ALERT · HEALTH ONLY] Simulated ledger reconciliation verification. 15 virtual accounts audited; zero delta ($0.0000). System state: nominal.",
        },
        {
            "kind": "JOB_FAILURE",
            "variant_id": None,
            "message": f"[TEST ALERT · HEALTH ONLY] Simulated scheduler execution error in 1h bar evaluation. Idempotency guard active; zero duplicate signals.",
        },
    ]

    dispatched = []
    for a in alerts:
        storage.record_event(
            kind=a["kind"],
            message=a["message"],
            variant_id=a["variant_id"],
        )
        dispatched.append(a)

    return dispatched


def main():
    print("================================================================================")
    print("STARKX LAB: Test Alert Dispatch (Health-Only, Zero P&L)")
    print("================================================================================")

    storage = LabStorage()
    alerts = dispatch_test_alerts(storage)

    for i, a in enumerate(alerts, 1):
        print(f"\n[ALERT {i}] Kind: {a['kind']}")
        print(f"  Message: {a['message']}")

    print("\n[PASS] All 3 test alerts successfully dispatched and recorded in lab_events.")
    print("================================================================================")


if __name__ == "__main__":
    main()
