"""Auto-outcome resolver: replay candles after each open signal and label what happened.

This is what turns logged signals into LEARNING DATA without manual labelling. For every signal
that has trade levels but no outcome yet, we pull the candles that printed AFTER the signal's
`as_of` time and walk them forward:

  * stop touched first  -> result 'stop'   (conservative: stop wins same-bar ties, never flatters)
  * target touched      -> result 'target'
  * neither after max_hold bars -> result 'timeout' (exit at last close)
  * not enough bars elapsed yet -> leave OPEN (resolve on a later run)

P&L is net of the same fee + slippage assumptions as the backtest, so live accuracy is comparable
to backtested accuracy. All DB access is best-effort and grouped to respect data-provider limits.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import db, persistence
from .config import settings
from .data import fetch_klines, fetch_klines_td

_FEE = 0.0004
_SLIP = 0.0002
_LONG = {"Buy", "Strong Buy"}
_SHORT = {"Sell", "Strong Sell"}


def _direction(label: str) -> str | None:
    if label in _LONG:
        return "long"
    if label in _SHORT:
        return "short"
    return None


def _future_candles(symbol: str, market: str, interval: str, after: datetime) -> pd.DataFrame:
    """Recent candles that closed strictly after `after`. Empty frame on any failure."""
    try:
        if (market or "crypto").lower() == "crypto":
            df = fetch_klines(symbol, interval, 1000)
        else:
            df = fetch_klines_td(symbol, interval, outputsize=1000)
    except Exception:
        return pd.DataFrame()
    return df[df.index > after]


def _resolve_one(direction: str, entry: float, stop: float, target: float,
                 future: pd.DataFrame, max_hold: int) -> dict | None:
    """Return an outcome dict, or None if the trade is still open (not enough data yet)."""
    mfe = mae = 0.0
    highs, lows, closes = future["high"], future["low"], future["close"]
    n = len(future)

    for i in range(n):
        hi, lo, cl = float(highs.iloc[i]), float(lows.iloc[i]), float(closes.iloc[i])
        if direction == "long":
            mfe = max(mfe, (hi - entry) / entry)
            mae = min(mae, (lo - entry) / entry)
            hit_stop, hit_target = lo <= stop, hi >= target
        else:
            mfe = max(mfe, (entry - lo) / entry)
            mae = min(mae, (entry - hi) / entry)
            hit_stop, hit_target = hi >= stop, lo <= target

        if hit_stop:
            exit_px = stop * (1 - _SLIP) if direction == "long" else stop * (1 + _SLIP)
            return _finalize(direction, entry, exit_px, "stop", i + 1, mfe, mae)
        if hit_target:
            exit_px = target * (1 - _SLIP) if direction == "long" else target * (1 + _SLIP)
            return _finalize(direction, entry, exit_px, "target", i + 1, mfe, mae)
        if i + 1 >= max_hold:
            exit_px = cl * (1 - _SLIP) if direction == "long" else cl * (1 + _SLIP)
            return _finalize(direction, entry, exit_px, "timeout", i + 1, mfe, mae)

    return None  # still open — fewer than max_hold bars and no level hit


def _finalize(direction: str, entry: float, exit_px: float, result: str,
              bars: int, mfe: float, mae: float) -> dict:
    gross = (exit_px - entry) / entry if direction == "long" else (entry - exit_px) / entry
    return {
        "result": result,
        "pnl": round(gross - 2 * _FEE, 6),
        "mfe": round(mfe, 6),
        "mae": round(mae, 6),
        "bars_held": bars,
    }


def _open_signals(limit: int) -> list[dict]:
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, symbol, coalesce(market,'crypto') as market, interval, as_of,
                   label, entry, stop, target
            from signals s
            where not exists (select 1 from outcomes o where o.signal_id = s.id)
              and entry is not null and stop is not null and target is not null
            order by as_of asc
            limit %s
            """,
            (limit,),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def resolve_open_signals(max_signals: int = 50) -> dict:
    """Resolve as many open signals as possible. Returns a summary. Never raises."""
    if not db.enabled():
        return {"enabled": False, "checked": 0, "resolved": 0, "still_open": 0}

    max_hold = settings.resolver_max_hold_bars
    try:
        rows = _open_signals(max_signals)
    except Exception:
        return {"enabled": True, "error": "query failed", "checked": 0, "resolved": 0, "still_open": 0}

    # Group by (symbol, market, interval) so each data feed is fetched once.
    cache: dict[tuple, pd.DataFrame] = {}
    resolved = still_open = 0

    for s in rows:
        direction = _direction(s["label"])
        if direction is None:
            continue
        key = (s["symbol"], s["market"], s["interval"])
        if key not in cache:
            cache[key] = _future_candles(s["symbol"], s["market"], s["interval"], s["as_of"])
        future = cache[key]
        future_after = future[future.index > s["as_of"]] if not future.empty else future
        if future_after.empty:
            still_open += 1
            continue

        outcome = _resolve_one(
            direction, float(s["entry"]), float(s["stop"]), float(s["target"]),
            future_after, max_hold,
        )
        if outcome is None:
            still_open += 1
            continue
        if persistence.record_outcome(
            s["id"], outcome["result"], pnl=outcome["pnl"],
            mfe=outcome["mfe"], mae=outcome["mae"], bars_held=outcome["bars_held"],
        ):
            resolved += 1

    return {"enabled": True, "checked": len(rows), "resolved": resolved, "still_open": still_open}
