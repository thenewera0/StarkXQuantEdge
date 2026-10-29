"""StarkX LAB: Geometry Validator.

Rule 0.4 Requirements:
1. Stop on the correct side of entry:
   - Long: stop < entry
   - Short: stop > entry
2. Stop distance >= 0.25% (0.0025) of entry price (crypto).
3. Target 0.5R to 5.0R (or None if using trailing stop or channel exit).
4. Price rounding >= 6 significant digits.
5. Invalid signals are rejected and logged to lab_events as 'REJECTED_GEOMETRY'.
6. initial_stop is immutable; trailing stops live in trailing_stop.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple
from app.lab.models import Signal


def count_significant_digits(val: float) -> int:
    """Calculates number of significant digits in a floating point price."""
    if val == 0:
        return 1
    s = f"{val:.10f}".rstrip("0").rstrip(".")
    if "." in s:
        s = s.replace(".", "").lstrip("0")
    else:
        s = s.lstrip("0")
    return len(s)


def round_sig_digits(val: float, digits: int = 6) -> float:
    """Rounds a price to at least specified significant digits."""
    if val == 0:
        return 0.0
    order = math.floor(math.log10(abs(val)))
    factor = 10 ** (digits - 1 - order)
    return round(val * factor) / factor


class GeometryValidator:
    """Validates structural price geometry of every generated signal before execution."""

    MIN_STOP_DISTANCE_PCT: float = 0.0025  # 0.25% minimum stop distance
    MIN_TARGET_R: float = 0.50             # 0.5R minimum target
    MAX_TARGET_R: float = 5.00             # 5.0R maximum target
    MIN_SIG_DIGITS: int = 6                # Price precision requirement

    @classmethod
    def validate(
        cls,
        signal: Signal,
        entry_price: float,
        stop_price: float,
        target_price: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validates entry, stop, and target geometry.
        
        Returns (is_valid, rejection_reason).
        """
        if entry_price <= 0:
            return False, f"Invalid entry price: {entry_price} <= 0"
        if stop_price <= 0:
            return False, f"Invalid stop price: {stop_price} <= 0"

        # 1. Stop on correct side of entry
        if signal.direction == "long":
            if stop_price >= entry_price:
                return False, f"Long stop {stop_price} >= entry {entry_price}"
            stop_dist = entry_price - stop_price
        elif signal.direction == "short":
            if stop_price <= entry_price:
                return False, f"Short stop {stop_price} <= entry {entry_price}"
            stop_dist = stop_price - entry_price
        else:
            return False, f"Unknown signal direction: {signal.direction}"

        # 2. Stop distance >= 0.25%
        stop_dist_pct = stop_dist / entry_price
        if stop_dist_pct < cls.MIN_STOP_DISTANCE_PCT:
            return False, (
                f"Stop distance {stop_dist_pct:.4%} < {cls.MIN_STOP_DISTANCE_PCT:.2%} threshold"
            )

        # 3. Target 0.5R - 5.0R if specified
        if target_price is not None:
            if target_price <= 0:
                return False, f"Target price {target_price} <= 0"
            if signal.direction == "long":
                if target_price <= entry_price:
                    return False, f"Long target {target_price} <= entry {entry_price}"
                target_r = (target_price - entry_price) / stop_dist
            else:
                if target_price >= entry_price:
                    return False, f"Short target {target_price} >= entry {entry_price}"
                target_r = (entry_price - target_price) / stop_dist

            if target_r < cls.MIN_TARGET_R or target_r > cls.MAX_TARGET_R:
                return False, (
                    f"Target {target_r:.2f}R outside allowed [{cls.MIN_TARGET_R}R, {cls.MAX_TARGET_R}R] range"
                )

        return True, None
