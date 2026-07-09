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
from .costs import round_trip_cost
from .data import INTERVAL_SECONDS, fetch_klines, fetch_klines_range, fetch_klines_td
from .data.validate import validate_ohlcv

_LONG = {"Buy", "Strong Buy"}
_SHORT = {"Sell", "Strong Sell"}
_CRYPTO = {"crypto"}


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
        df, _ = validate_ohlcv(df, interval)  # clean before resolving outcomes
    except Exception:
        return pd.DataFrame()
    return df[df.index > after]


def _subbar_first(symbol: str, market: str, interval: str, bar_close: datetime,
                  direction: str, stop: float, target: float) -> str:
    """When one bar's range spans BOTH stop and target, replay 1m candles inside that bar to
    decide which was hit FIRST. Crypto only (1m mirror available); best-effort. Falls back to
    the conservative 'stop' (never flatters) on any failure or for non-crypto markets."""
    if (market or "crypto").lower() not in _CRYPTO:
        return "stop"
    try:
        secs = INTERVAL_SECONDS.get(interval, 3600)
        end_ms = int(pd.Timestamp(bar_close).timestamp() * 1000)
        start_ms = end_ms - secs * 1000
        sub = fetch_klines_range(symbol, "1m", start_ms, end_ms)
        for _, r in sub.iterrows():
            hi, lo = float(r["high"]), float(r["low"])
            if direction == "long":
                if lo <= stop:
                    return "stop"
                if hi >= target:
                    return "target"
            else:
                if hi >= stop:
                    return "stop"
                if lo <= target:
                    return "target"
    except Exception:
        return "stop"
    return "stop"


def _resolve_one(symbol: str, market: str, interval: str, direction: str,
                 entry: float, stop: float, target: float, atr_pct: float,
                 future: pd.DataFrame, max_hold: int) -> dict | None:
    """Return an outcome dict, or None if the trade is still open (not enough data yet)."""
    cost = round_trip_cost(market, symbol, atr_pct)  # round-trip fees + slippage, fraction
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

        if hit_stop and hit_target:
            # Ambiguous bar: resolve intra-bar with 1m candles instead of always assuming stop.
            if _subbar_first(symbol, market, interval, future.index[i], direction, stop, target) == "target":
                return _finalize(direction, entry, target, "target", i + 1, mfe, mae, cost)
            return _finalize(direction, entry, stop, "stop", i + 1, mfe, mae, cost)
        if hit_stop:
            return _finalize(direction, entry, stop, "stop", i + 1, mfe, mae, cost)
        if hit_target:
            return _finalize(direction, entry, target, "target", i + 1, mfe, mae, cost)
        if i + 1 >= max_hold:
            return _finalize(direction, entry, cl, "timeout", i + 1, mfe, mae, cost)

    return None  # still open — fewer than max_hold bars and no level hit


def _finalize(direction: str, entry: float, exit_px: float, result: str,
              bars: int, mfe: float, mae: float, cost: float) -> dict:
    gross = (exit_px - entry) / entry if direction == "long" else (entry - exit_px) / entry
    return {
        "result": result,
        "pnl": round(gross - cost, 6),   # net of modelled round-trip cost (fees + slippage)
        "mfe": round(mfe, 6),
        "mae": round(mae, 6),
        "bars_held": bars,
    }


def _open_signals(limit: int) -> list[dict]:
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, symbol, coalesce(market,'crypto') as market, interval, as_of,
                   label, entry, stop, target, atr, price
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

        entry = float(s["entry"])
        # ATR% drives crypto slippage; fall back to the stop distance if atr/price are absent.
        atr = s.get("atr")
        price = s.get("price") or entry
        if atr is not None and price:
            atr_pct = abs(float(atr)) / float(price)
        else:
            atr_pct = abs(entry - float(s["stop"])) / entry
        outcome = _resolve_one(
            s["symbol"], s["market"], s["interval"], direction,
            entry, float(s["stop"]), float(s["target"]), atr_pct,
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
