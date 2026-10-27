#!/usr/bin/env python3
"""Phase 7.4 — Forward Evaluation Script (backend copy)."""
from pathlib import Path
import sys

# Delegate directly to root scripts/evaluate_forward.py
root_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root_dir / "scripts"))
import evaluate_forward

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate Post-Freeze Forward Trades")
    parser.add_argument("--append", action="store_true", help="Append run output to docs/FORWARD_LOG.md")
    args = parser.parse_args()
    evaluate_forward.evaluate_forward(append_log=args.append)
