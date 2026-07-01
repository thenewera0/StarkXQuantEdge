"""LLM reasoning layer (Phase 1b). The LLM narrates pre-computed numbers; it never creates them."""

from .rationale import build_rationale
from .debate import run_debate

__all__ = ["build_rationale", "run_debate"]
