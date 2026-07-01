"""Run the auto-outcome resolver once and print the summary.

Usage (from backend/):
    python -m scripts.resolve
"""

from __future__ import annotations

from app import resolver


def main() -> None:
    print(resolver.resolve_open_signals())


if __name__ == "__main__":
    main()
