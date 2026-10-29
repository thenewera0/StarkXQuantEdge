"""StarkX LAB — Active Multi-Strategy Paper Trading with Evidence-Gated Self-Improvement.

NON-NEGOTIABLE OPERATING CONSTRAINTS:
- Rule 0.1: PAPER ONLY. The lab never places a real order.
  Uses public market data only and no exchange API keys.
  LAB_EXECUTION_MODE is strictly constant 'paper'.
- Rule 0.2: Frozen files and forward-test guards remain untouched.
  Core keeps running as its own read-only account.
- Rule 0.6: Parameter self-modification only allowed inside pre-registered
  bounds in config/lab_spec.json (verified by SHA-256).
  The system never edits its own code.
"""

from __future__ import annotations

# Constant Rule 0.1: Strict paper execution mode
LAB_EXECUTION_MODE: str = "paper"
LAB_SPEC_SHA256: str = "30410905d364ab6e4d3f8c6d7940ce0c112944de7891103a68aa776dbd7590ae"
LAB_VERSION: str = "1.0.0"

__all__ = [
    "LAB_EXECUTION_MODE",
    "LAB_SPEC_SHA256",
    "LAB_VERSION",
]
