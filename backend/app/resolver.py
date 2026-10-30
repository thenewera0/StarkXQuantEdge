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


def _fetch_candles(symbol: str, market: str, interval: str) -> pd.DataFrame:
    """Fetch raw candles for an instrument. Empty frame on any failure."""
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
        return df
    except Exception:
        return pd.DataFrame()


def _future_candles(symbol: str, market: str, interval: str, after: datetime) -> pd.DataFrame:
    """Recent candles that closed strictly after `after`. Empty frame on any failure."""
    df = _fetch_candles(symbol, market, interval)
    if df.empty:
        return df
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
                 future: pd.DataFrame, max_hold: int, strategy: str = "core") -> dict | None:
    """Return an outcome dict, or None if the trade is still open (not enough data yet)."""
    # EXECUTION. With limit entries the stored `entry` is a RESTING price, not a fill: the trade
    # only exists if the market trades through it within the expiry window. Measured on 14,047
    # signals, limit entry beat market entry by +0.39pp per signal at a 78.8% fill rate — and that
    # comparison already counted every unfilled order as a zero, which is the only honest way to
    # judge it. Modelling the fill is therefore not optional; assuming it would book the 21% of
    # orders that never filled as free trades.
    use_limit = settings.limit_orders_enabled
    cost_exec = settings.flash_execution if strategy == "flash" else ("maker" if use_limit else "taker")
    cost = round_trip_cost(market, symbol, atr_pct, cost_exec)
    mfe = mae = 0.0
    highs, lows, closes = future["high"], future["low"], future["close"]
    n = len(future)

    start = 0
    risk_dist = abs(entry - stop)
    if use_limit:
        from .execution import tick_size
        t = tick_size(entry)
        filled_at = None
        target_1r = entry + risk_dist if direction == "long" else entry - risk_dist
        expiry_bars = settings.limit_expiry_bars
        for i in range(min(expiry_bars, n)):
            hi_i = float(highs.iloc[i])
            lo_i = float(lows.iloc[i])
            # Runaway check: if price touches +1.0R before filling, order is cancelled cleanly
            if direction == "long":
                if hi_i >= target_1r:
                    return {"result": "unfilled", "pnl": None, "pnl_frac": None,
                            "mfe": None, "mae": None, "bars_held": i + 1,
                            "r_net": None, "cost_r": None, "status": "EXPIRED_UNFILLED"}
                if lo_i <= (entry - t):
                    filled_at = i
                    break
            elif direction == "short":
                if lo_i <= target_1r:
                    return {"result": "unfilled", "pnl": None, "pnl_frac": None,
                            "mfe": None, "mae": None, "bars_held": i + 1,
                            "r_net": None, "cost_r": None, "status": "EXPIRED_UNFILLED"}
                if hi_i >= (entry + t):
                    filled_at = i
                    break
        if filled_at is None:
            if n < expiry_bars:
                return None          # window has not elapsed yet — still pending, not cancelled
            else:
                # Expired unfilled. pnl is NULL rather than 0 so it closes the signal without being
                # counted as a losing trade in any hit-rate or expectancy query.
                return {"result": "unfilled", "pnl": None, "pnl_frac": None,
                        "mfe": None, "mae": None, "bars_held": expiry_bars,
                        "r_net": None, "cost_r": None, "status": "EXPIRED_UNFILLED"}
        start = filled_at

    # PARTIAL BOOK / 2-TRANCHE SCALE-OUT.
    # Phase 2: Tranche 1 (50%) books at T1 = +1.5R (or strategy configured partial).
    # Stop ratchets to Breakeven + fees (+0.15R), while Tranche 2 trails dynamically via Chandelier Exit or T2 (+3.5R).
    partial_px = None
    booked_frac = 0.0
    booked_pnl = 0.0
    is_v3 = strategy in ("core_v3", "flash_v3", "v3", "lab") or getattr(settings, "two_tranche_scaleout", False)
    if (settings.partial_book_enabled or is_v3) and risk_dist > 0:
        if is_v3:
            partial_at_r = 1.50
            partial_frac = 0.50
        elif strategy == "flash":
            partial_at_r = settings.flash_partial_book_at_r
            partial_frac = getattr(settings, "flash_partial_book_fraction", 0.35)
        else:
            partial_at_r = settings.partial_book_at_r
            partial_frac = settings.partial_book_fraction
        step = partial_at_r * risk_dist
        partial_px = entry + step if direction == "long" else entry - step

    current_stop = stop
    best_fav = 0.0
    peak_price = entry

    for i in range(start, n):
        hi, lo, cl = float(highs.iloc[i]), float(lows.iloc[i]), float(closes.iloc[i])
        held = i - start + 1
        bar_start_stop = current_stop
        if direction == "long":
            peak_price = max(peak_price, hi)
        else:
            peak_price = min(peak_price, lo)

        # Book the partial the first time price trades through the level. Checked BEFORE stop and
        # target so a bar that spans both books the partial rather than losing it.
        if partial_px is not None and booked_frac == 0.0:
            reached = hi >= partial_px if direction == "long" else lo <= partial_px
            if reached:
                booked_frac = partial_frac
                leg = ((partial_px - entry) / entry if direction == "long"
                       else (entry - partial_px) / entry)
                booked_pnl = booked_frac * leg
                # Immediately upon T1 hit, ratchet Stop Loss on remaining runner to Breakeven + Round-Trip Fees (+0.15R)
                be_fees_px = entry + 0.15 * risk_dist if direction == "long" else entry - 0.15 * risk_dist
                current_stop = max(current_stop, be_fees_px) if direction == "long" else min(current_stop, be_fees_px)

        # Favorable move tracking
        fav_pct = (hi - entry) / entry if direction == "long" else (entry - lo) / entry
        best_fav = max(best_fav, fav_pct)
        mfe_r = (best_fav / (risk_dist / entry)) if risk_dist > 0 else 0.0

        # PROGRESSIVE PROFIT PROTECTION & TRAILING STOP
        # Strategy-aware R-ladder:
        # - Flash (1h fast scalps): gives trades room to reach 2.0R; locks in +0.35R at +1.20R MFE to avoid premature +$1 suffocation.
        # - Core (4h/1d patient swings): gives 4h candles room to breathe, locking profit progressively.
        if risk_dist > 0:
            if strategy == "flash":
                # Tier 1: Profit Lock 1 (+1.20R gain) -> Lock in +0.35R net profit
                # Eliminates premature +0.15% (+1$) suffocation. Gives 1h trades breathing room to reach full target
                # and guarantees a meaningful win (+0.35R, ~$5-$7) if price retraces.
                if mfe_r >= 1.20:
                    p1_level = entry + 0.35 * risk_dist if direction == "long" else entry - 0.35 * risk_dist
                    current_stop = max(current_stop, p1_level) if direction == "long" else min(current_stop, p1_level)

                # Tier 2: Profit Lock 2 (+1.60R gain) -> Lock in +0.80R net profit
                if mfe_r >= 1.60:
                    p2_level = entry + 0.80 * risk_dist if direction == "long" else entry - 0.80 * risk_dist
                    current_stop = max(current_stop, p2_level) if direction == "long" else min(current_stop, p2_level)

                # Tier 3: Chandelier Trail (above +2.00R target) -> Trail peak price by 0.60 * risk_dist
                if mfe_r >= 2.00:
                    trail_level = hi - 0.60 * risk_dist if direction == "long" else lo + 0.60 * risk_dist
                    current_stop = max(current_stop, trail_level) if direction == "long" else min(current_stop, trail_level)
            else:
                # Tier 1: Breakeven (+0.75R gain) -> Move stop to entry + 0.25% fee cushion
                if mfe_r >= 0.75:
                    be_level = entry * 1.0025 if direction == "long" else entry * 0.9975
                    current_stop = max(current_stop, be_level) if direction == "long" else min(current_stop, be_level)

                # Tier 2: Profit Lock 1 (+1.25R gain) -> Lock in +0.60R net profit
                if mfe_r >= 1.25:
                    p1_level = entry + 0.60 * risk_dist if direction == "long" else entry - 0.60 * risk_dist
                    current_stop = max(current_stop, p1_level) if direction == "long" else min(current_stop, p1_level)

                # Tier 3: Profit Lock 2 (+1.75R gain) -> Lock in +1.20R net profit
                if mfe_r >= 1.75:
                    p2_level = entry + 1.20 * risk_dist if direction == "long" else entry - 1.20 * risk_dist
                    current_stop = max(current_stop, p2_level) if direction == "long" else min(current_stop, p2_level)

                # Tier 4: Chandelier Trail (above +2.0R) -> Trail peak price by 0.60 * risk_dist
                if mfe_r >= 2.00:
                    trail_level = hi - 0.60 * risk_dist if direction == "long" else lo + 0.60 * risk_dist
                    current_stop = max(current_stop, trail_level) if direction == "long" else min(current_stop, trail_level)

        # Stop and target evaluation:
        # Avoid the intra-bar lookahead bug: if a stop was raised by *this* bar's high,
        # it cannot be stopped out by this bar's low unless price closed below it (cl <= current_stop),
        # which proves price collapsed after the rally. On subsequent bars, bar_start_stop equals current_stop
        # and standard low/high checks protect correctly.
        if direction == "long":
            mfe = max(mfe, (hi - entry) / entry)
            mae = min(mae, (lo - entry) / entry)
            hit_stop = (lo <= bar_start_stop) or (current_stop > bar_start_stop and cl <= current_stop)
            stop_exit_px = bar_start_stop if (lo <= bar_start_stop) else current_stop
            hit_target = hi >= target
        else:
            mfe = max(mfe, (entry - lo) / entry)
            mae = min(mae, (entry - hi) / entry)
            hit_stop = (hi >= bar_start_stop) or (current_stop < bar_start_stop and cl >= current_stop)
            stop_exit_px = bar_start_stop if (hi >= bar_start_stop) else current_stop
            hit_target = lo <= target

        # Bars HELD is counted from the fill, not from the signal. With a limit entry the order can
        # rest for several bars before filling, and charging that waiting time against max_hold
        # would cut trades short by however long they queued.
        if hit_stop and hit_target:
            # Phase 0.2: Resolver Pessimism
            # When TP and SL are both touched inside the same candle, resolve as STOP (conservative)
            # under RESOLVER_SAME_BAR_RULE=stop_first (default).
            same_bar_rule = getattr(settings, "resolver_same_bar_rule", "stop_first")
            if same_bar_rule == "stop_first":
                res_label = "trailing_stop" if stop_exit_px != stop else "stop"
                return _finalize(direction, entry, stop_exit_px, res_label, held, mfe, mae, cost, booked_frac, booked_pnl, orig_stop=stop)
            else:
                if _subbar_first(symbol, market, interval, future.index[i], direction, stop_exit_px, target) == "target":
                    return _finalize(direction, entry, target, "target", held, mfe, mae, cost, booked_frac, booked_pnl, orig_stop=stop)
                res_label = "trailing_stop" if stop_exit_px != stop else "stop"
                return _finalize(direction, entry, stop_exit_px, res_label, held, mfe, mae, cost, booked_frac, booked_pnl, orig_stop=stop)
        if hit_stop:
            res_label = "trailing_stop" if stop_exit_px != stop else "stop"
            return _finalize(direction, entry, stop_exit_px, res_label, held, mfe, mae, cost, booked_frac, booked_pnl, orig_stop=stop)
        if hit_target:
            return _finalize(direction, entry, target, "target", held, mfe, mae, cost, booked_frac, booked_pnl, orig_stop=stop)

        # Velocity Decay Rule (Time-Stop for Flash Bot):
        # If held >= 12 bars and unrealized PnL is between -0.3R and +0.4R (momentum stalled),
        # exit at market close to free up capital and prevent slow stop-outs.
        if strategy == "flash" and held >= 12:
            cur_pnl_r = (((cl - entry) / entry if direction == "long" else (entry - cl) / entry) / (risk_dist / entry)) if risk_dist > 0 else 0.0
            if -0.30 <= cur_pnl_r <= 0.40 or (cur_pnl_r <= -0.50 and mfe_r < 0.25):
                return _finalize(direction, entry, cl, "velocity_decay_stop", held, mfe, mae, cost, booked_frac, booked_pnl, orig_stop=stop)

        if held >= max_hold:
            return _finalize(direction, entry, cl, "timeout", held, mfe, mae, cost, booked_frac, booked_pnl, orig_stop=stop)

    # If still open, return a dict containing trailing_stop so caller can sync signals.stop in DB
    return {"status": "open", "trailing_stop": current_stop if current_stop != stop else None}


def _finalize(direction: str, entry: float, exit_px: float, result: str,
              bars: int, mfe: float, mae: float, cost: float,
              booked_frac: float = 0.0, booked_pnl: float = 0.0,
              orig_stop: float | None = None) -> dict:
    """Blend the partial that was already taken off with whatever the runner did.

    `booked_frac` of the position exited earlier at a locked-in profit; the remaining
    (1 - booked_frac) runs to stop, target or timeout. Cost is charged on the FULL notional
    because both legs pay their own round trip.
    """
    gross = (exit_px - entry) / entry if direction == "long" else (entry - exit_px) / entry
    total = booked_pnl + (1.0 - booked_frac) * gross
    net_pnl = total - cost

    stop_dist = abs(entry - orig_stop) if orig_stop is not None else 0.0
    stop_frac = (stop_dist / entry) if (entry and stop_dist > 0) else 0.0
    if stop_frac > 0:
        cost_r = cost / stop_frac
        r_net = net_pnl / stop_frac
    else:
        cost_r = 0.0
        r_net = 0.0

    return {
        "result": result,
        "pnl": round(net_pnl, 6),
        "r_net": round(r_net, 4),
        "cost_r": round(cost_r, 4),
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
                   label, entry, coalesce(initial_stop, stop) as stop, target, atr, price,
                   coalesce(strategy,'core') as strategy, trailing_stop
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
            cache[key] = _fetch_candles(s["symbol"], s["market"], s["interval"])
        raw_df = cache[key]
        future_after = raw_df[raw_df.index > s["as_of"]] if not raw_df.empty else raw_df
        # Flash scalps get a much shorter time-stop so they never become accidental swing trades.
        hold = settings.flash_max_hold_bars if s.get("strategy") == "flash" else max_hold
        if future_after.empty:
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            sig_age_days = (now_utc - s["as_of"]).total_seconds() / 86400.0 if s.get("as_of") else 0
            if sig_age_days > 14.0:
                # Stale / dead / delisted signal with no subsequent candle data — close out as expired so it doesn't block the queue
                persistence.record_outcome(s["id"], "expired", pnl=None, bars_held=hold)
                resolved += 1
                continue
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
            future_after, hold,
            strategy=s.get("strategy") or "core",
        )
        if outcome is None or outcome.get("status") == "open":
            if outcome and outcome.get("trailing_stop"):
                persistence.update_signal_trailing_stop(s["id"], outcome["trailing_stop"])
            still_open += 1
            continue
        if persistence.record_outcome(
            s["id"], outcome["result"], pnl=outcome["pnl"],
            mfe=outcome["mfe"], mae=outcome["mae"], bars_held=outcome["bars_held"],
            r_net=outcome.get("r_net"), cost_r=outcome.get("cost_r"),
        ):
            resolved += 1


    return {"enabled": True, "checked": len(rows), "resolved": resolved, "still_open": still_open}
