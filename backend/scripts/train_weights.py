"""Train + gate adaptive per-regime weights once, and print the report.

Usage (from backend/):
    python -m scripts.train_weights
"""

from __future__ import annotations

import json

from app import learning


def main() -> None:
    print("=== learning status (before) ===")
    print(json.dumps(learning.learning_status(), indent=2, default=str))
    print("\n=== train + gate ===")
    print(json.dumps(learning.train_and_gate(), indent=2, default=str))


if __name__ == "__main__":
    main()
