"""Indian NSE Market Session Clock, Gap-Protection Filter & MIS Auto-Square-Off Engine.

Governs execution timing for Indian National Stock Exchange (NSE) Equities & F&O:
1. Normal Session: Monday–Friday, 09:15:00 to 15:30:00 IST (03:45:00 to 10:00:00 UTC).
2. Opening Filter: NO_NEW_ENTRY_BEFORE = 09:30 IST (skips opening auction / 15m gap noise).
3. EOD Filter: NO_NEW_ENTRY_AFTER = 14:45 IST for intraday orders.
4. MIS Auto-Square-Off: 15:15 IST force-close for product_type == 'MIS' (exit_reason = 'ist_eod_squareoff').
5. Overnight Gap-Protection Filter: Rejects swing entries if opening gap > 1.5% past planned entry.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
import pandas as pd

IST_OFFSET = timedelta(hours=5, minutes=30)
IST_TZ = timezone(IST_OFFSET)

# NSE Core Hours (IST)
MARKET_OPEN_TIME = dtime(9, 15, 0)
MARKET_CLOSE_TIME = dtime(15, 30, 0)

NO_NEW_ENTRY_BEFORE = dtime(9, 30, 0)
NO_NEW_ENTRY_AFTER = dtime(14, 45, 0)
MIS_AUTO_SQUAREOFF_TIME = dtime(15, 15, 0)

# Max allowed opening gap past planned entry price before cancellation
MAX_GAP_THRESHOLD_PCT = 1.5


def to_ist(dt: Optional[datetime | int | float | pd.Timestamp] = None) -> datetime:
    """Convert any UTC datetime, Timestamp or unix timestamp to IST (UTC+05:30). If None, returns current IST."""
    if dt is None:
        return datetime.now(IST_TZ)
    if isinstance(dt, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(dt), tz=timezone.utc)
        except Exception:
            return datetime.now(IST_TZ)
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    if not isinstance(dt, datetime):
        return datetime.now(IST_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST_TZ)


def is_nse_trading_day(dt: Optional[datetime] = None) -> bool:
    """True if Monday through Friday."""
    ist_dt = to_ist(dt)
    return ist_dt.weekday() < 5  # Mon=0, Fri=4, Sat=5, Sun=6


def is_nse_market_open(dt: Optional[datetime] = None) -> bool:
    """True if within 09:15 to 15:30 IST on a weekday."""
    ist_dt = to_ist(dt)
    if not is_nse_trading_day(ist_dt):
        return False
    t = ist_dt.time()
    return MARKET_OPEN_TIME <= t < MARKET_CLOSE_TIME


def is_entry_permitted_ist(dt: Optional[datetime] = None) -> bool:
    """True if within allowed intraday entry window (09:30 to 14:45 IST on a weekday)."""
    ist_dt = to_ist(dt)
    if not is_nse_trading_day(ist_dt):
        return False
    t = ist_dt.time()
    return NO_NEW_ENTRY_BEFORE <= t <= NO_NEW_ENTRY_AFTER


def is_mis_squareoff_time(dt: Optional[datetime] = None) -> bool:
    """True if current IST bar is at or past MIS auto-square-off cutoff (15:15 IST)."""
    ist_dt = to_ist(dt)
    if not is_nse_trading_day(ist_dt):
        return False
    t = ist_dt.time()
    return t >= MIS_AUTO_SQUAREOFF_TIME


def check_opening_gap(prev_close: float, open_price: float, threshold_pct: float = MAX_GAP_THRESHOLD_PCT) -> Tuple[bool, float]:
    """Check if opening price gapped significantly past previous close.

    Returns:
        (is_gap_excessive, gap_pct)
    """
    if prev_close <= 0:
        return False, 0.0
    gap_pct = abs(open_price - prev_close) / prev_close * 100.0
    return gap_pct > threshold_pct, round(gap_pct, 3)


def get_market_session_state(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """Returns real-time session telemetry dictionary for frontend pills and status checks."""
    ist_dt = to_ist(dt)
    is_open = is_nse_market_open(ist_dt)
    t = ist_dt.time()
    weekday = ist_dt.weekday()

    if is_open:
        if t < NO_NEW_ENTRY_BEFORE:
            status_label = "NSE OPEN · OPENING AUCTION"
            status_color = "amber"
        elif t >= MIS_AUTO_SQUAREOFF_TIME:
            status_label = "NSE OPEN · MIS SQUARE-OFF ACTIVE"
            status_color = "amber"
        else:
            status_label = "NSE OPEN · REGULAR TRADING"
            status_color = "green"
    else:
        # Calculate next open date
        if weekday < 4:  # Mon-Thu after close
            if t >= MARKET_CLOSE_TIME:
                next_day = ist_dt.date() + timedelta(days=1)
            else:
                next_day = ist_dt.date()
        elif weekday == 4:  # Fri
            if t >= MARKET_CLOSE_TIME:
                next_day = ist_dt.date() + timedelta(days=3)  # next Mon
            else:
                next_day = ist_dt.date()
        else:  # Sat (5) or Sun (6)
            days_to_mon = 7 - weekday
            next_day = ist_dt.date() + timedelta(days=days_to_mon)

        status_label = f"NSE CLOSED · NEXT OPEN {next_day.strftime('%a')} 09:15 IST"
        status_color = "yellow"

    return {
        "is_open": is_open,
        "ist_clock": ist_dt.strftime("%H:%M:%S IST"),
        "ist_date": ist_dt.strftime("%Y-%m-%d"),
        "status_label": status_label,
        "status_color": status_color,
        "entry_permitted": is_entry_permitted_ist(ist_dt),
        "mis_squareoff_active": is_mis_squareoff_time(ist_dt),
    }
