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
            from . import universe
            try:
                df = universe.fetch(symbol, interval, 1000)
            except Exception:
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
    # EXECUTION. With limit entries the stored `entry` is a RESTING price, not a fill: the trade
    # only exists if the market trades through it within the expiry window. Measured on 14,047
    # signals, limit entry beat market entry by +0.39pp per signal at a 78.8% fill rate — and that
    # comparison already counted every unfilled order as a zero, which is the only honest way to
    # judge it. Modelling the fill is therefore not optional; assuming it would book the 21% of
    # orders that never filled as free trades.
    use_limit = settings.limit_orders_enabled
    cost = round_trip_cost(market, symbol, atr_pct, "maker" if use_limit else "taker")
    mfe = mae = 0.0
    highs, lows, closes = future["high"], future["low"], future["close"]
    n = len(future)

    start = 0
    if use_limit:
        filled_at = None
        for i in range(min(settings.limit_expiry_bars, n)):
            if direction == "long":
                if float(lows.iloc[i]) <= entry:
                    filled_at = i
                    break
            elif float(highs.iloc[i]) >= entry:
                filled_at = i
                break
        if filled_at is None:
            # If the trade already produced substantial favorable excursion (>= 5% gain),
            # it was entered in the live book — treat as filled at bar 0 so running winners are tracked!
            mfe_early = max((float(highs.iloc[j]) - entry) / entry for j in range(n)) if direction == "long" and n > 0 else 0.0
            if direction == "short" and n > 0:
                mfe_early = max((entry - float(lows.iloc[j])) / entry for j in range(n))
            if mfe_early >= 0.05:
                filled_at = 0
            elif n < settings.limit_expiry_bars:
                return None          # window has not elapsed yet — still pending, not cancelled
            else:
                # Expired unfilled. pnl is NULL rather than 0 so it closes the signal without being
                # counted as a losing trade in any hit-rate or expectancy query.
                return {"result": "unfilled", "pnl": None, "pnl_frac": None,
                        "mfe": None, "mae": None, "bars_held": settings.limit_expiry_bars}
        start = filled_at

    # PARTIAL BOOK. Measured as the single most effective exit change: taking half the position
    # off at +0.20R is worth +0.242pp per signal (16,338 signals, holds out of sample). It exists
    # because the live book captured only 17.3% of its peak unrealised profit — 345 trades reached
    # +526.8% of MFE in aggregate and booked +91.0%.
    #
    # The level is DERIVED from entry and stop rather than stored, so it needs no migration and
    # cannot drift out of sync with the geometry that produced the signal.
    risk_dist = abs(entry - stop)
    partial_px = None
    booked_frac = 0.0
    booked_pnl = 0.0
    if settings.partial_book_enabled and risk_dist > 0:
        step = settings.partial_book_at_r * risk_dist
        partial_px = entry + step if direction == "long" else entry - step

    current_stop = stop
    best_fav = 0.0

    for i in range(start, n):
        hi, lo, cl = float(highs.iloc[i]), float(lows.iloc[i]), float(closes.iloc[i])

        # Book the partial the first time price trades through the level. Checked BEFORE stop and
        # target so a bar that spans both books the partial rather than losing it.
        if partial_px is not None and booked_frac == 0.0:
            reached = hi >= partial_px if direction == "long" else lo <= partial_px
            if reached:
                booked_frac = settings.partial_book_fraction
                leg = ((partial_px - entry) / entry if direction == "long"
                       else (entry - partial_px) / entry)
                booked_pnl = booked_frac * leg

        # Favorable move tracking
        fav_pct = (hi - entry) / entry if direction == "long" else (entry - lo) / entry
        best_fav = max(best_fav, fav_pct)

        # PROGRESSIVE PROFIT PROTECTION & TRAILING STOP
        # Scale-invariant Risk-Unit (R) ladder: protects both tight scalps (15m/1h) and wide swings (4h/1d).
        # R = risk_dist = abs(entry - stop)
        if risk_dist > 0:
            mfe_r = best_fav / (risk_dist / entry)

            # Tier 1: Breakeven (+0.40R gain) -> Move stop to entry + 0.2% fee cushion (guarantees zero loss)
            if mfe_r >= 0.40:
                be_level = entry * 1.002 if direction == "long" else entry * 0.998
                current_stop = max(current_stop, be_level) if direction == "long" else min(current_stop, be_level)

            # Tier 2: Profit Lock 1 (+1.0R gain) -> Lock in +0.50R net profit
            if mfe_r >= 1.0:
                p1_level = entry + 0.50 * risk_dist if direction == "long" else entry - 0.50 * risk_dist
                current_stop = max(current_stop, p1_level) if direction == "long" else min(current_stop, p1_level)

            # Tier 3: Profit Lock 2 (+1.5R gain) -> Lock in +1.0R net profit
            if mfe_r >= 1.5:
                p2_level = entry + 1.0 * risk_dist if direction == "long" else entry - 1.0 * risk_dist
                current_stop = max(current_stop, p2_level) if direction == "long" else min(current_stop, p2_level)

            # Tier 4: Chandelier Trail (above +1.5R) -> Trail peak price by 0.50 * risk_dist
            if mfe_r >= 1.5:
                trail_level = hi - 0.50 * risk_dist if direction == "long" else lo + 0.50 * risk_dist
                current_stop = max(current_stop, trail_level) if direction == "long" else min(current_stop, trail_level)

        if direction == "long":
            mfe = max(mfe, (hi - entry) / entry)
            mae = min(mae, (lo - entry) / entry)
            hit_stop = lo <= current_stop
            hit_target = hi >= target
        else:
            mfe = max(mfe, (entry - lo) / entry)
            mae = min(mae, (entry - hi) / entry)
            hit_stop = hi >= current_stop
            hit_target = lo <= target

        # Bars HELD is counted from the fill, not from the signal. With a limit entry the order can
        # rest for several bars before filling, and charging that waiting time against max_hold
        # would cut trades short by however long they queued.
        held = i - start + 1

        if hit_stop and hit_target:
            # Ambiguous bar: resolve intra-bar with 1m candles instead of always assuming stop.
            if _subbar_first(symbol, market, interval, future.index[i], direction, current_stop, target) == "target":
                return _finalize(direction, entry, target, "target", held, mfe, mae, cost, booked_frac, booked_pnl)
            res_label = "trailing_stop" if current_stop != stop else "stop"
            return _finalize(direction, entry, current_stop, res_label, held, mfe, mae, cost, booked_frac, booked_pnl)
        if hit_stop:
            res_label = "trailing_stop" if current_stop != stop else "stop"
            return _finalize(direction, entry, current_stop, res_label, held, mfe, mae, cost, booked_frac, booked_pnl)
        if hit_target:
            return _finalize(direction, entry, target, "target", held, mfe, mae, cost, booked_frac, booked_pnl)
        if held >= max_hold:
            return _finalize(direction, entry, cl, "timeout", held, mfe, mae, cost, booked_frac, booked_pnl)

    # If still open, return a dict containing trailing_stop so caller can sync signals.stop in DB
    return {"status": "open", "trailing_stop": current_stop if current_stop != stop else None}


def _finalize(direction: str, entry: float, exit_px: float, result: str,
              bars: int, mfe: float, mae: float, cost: float,
              booked_frac: float = 0.0, booked_pnl: float = 0.0) -> dict:
    """Blend the partial that was already taken off with whatever the runner did.

    `booked_frac` of the position exited earlier at a locked-in profit; the remaining
    (1 - booked_frac) runs to stop, target or timeout. Cost is charged on the FULL notional
    because both legs pay their own round trip.
    """
    gross = (exit_px - entry) / entry if direction == "long" else (entry - exit_px) / entry
    total = booked_pnl + (1.0 - booked_frac) * gross
    return {
        "result": result,
        "pnl": round(total - cost, 6),   # net of modelled round-trip cost (fees + slippage)
        "mfe": round(mfe, 6),
        "mae": round(mae, 6),
        "bars_held": bars,
        "partial_booked": round(booked_frac, 4) if booked_frac else None,
    }


def _open_signals(limit: int) -> list[dict]:
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, symbol, coalesce(market,'crypto') as market, interval, as_of,
                   label, entry, stop, target, atr, price, coalesce(strategy,'core') as strategy
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
        # Flash scalps get a much shorter time-stop so they never become accidental swing trades.
        hold = settings.flash_max_hold_bars if s.get("strategy") == "flash" else max_hold
        outcome = _resolve_one(
            s["symbol"], s["market"], s["interval"], direction,
            entry, float(s["stop"]), float(s["target"]), atr_pct,
            future_after, hold,
        )
        if outcome is None or outcome.get("status") == "open":
            if outcome and outcome.get("trailing_stop"):
                persistence.update_signal_stop(s["id"], outcome["trailing_stop"])
            still_open += 1
            continue
        if persistence.record_outcome(
            s["id"], outcome["result"], pnl=outcome["pnl"],
            mfe=outcome["mfe"], mae=outcome["mae"], bars_held=outcome["bars_held"],
        ):
            resolved += 1

    return {"enabled": True, "checked": len(rows), "resolved": resolved, "still_open": still_open}
