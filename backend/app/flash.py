"""Flash Bot — fast, high-frequency opportunity hunter (5m / 15m).

The core engine is a patient swing system: it waits for multi-factor confluence on 1h/4h and is
deliberately silent most of the time. The Flash Bot is the opposite by design — it hunts SHORT-LIVED
momentum bursts and breakouts on low timeframes, takes tight risk, and exits fast.

It is a SEPARATE strategy family with its own P&L, so it never contaminates the core track record:

    trigger (momentum burst | breakout | reversal snap)
      -> cost-aware EV gate (a 5m scalp must clear a REAL round-trip cost, which is brutal at that
         size — this is the honest filter that stops death-by-fees)
      -> tight ATR geometry (stop 1.0x ATR, target 1.5x ATR, hard time-stop)
      -> logged as strategy='flash'

Discipline that still applies (the lessons that keep it from blowing up):
  * every entry must clear cost_in_R — no "just trade more" without an edge
  * its own rolling performance gate: if flash bleeds over its recent window, it stands down
  * hard time-stop so a scalp never becomes an accidental swing trade
"""

from __future__ import annotations

import logging

import pandas as pd

from . import db, persistence
from .config import settings
from .costs import cost_in_r, round_trip_cost
from .data import fetch_klines
from .data.validate import validate_ohlcv
from .indicators import compute_indicators

logger = logging.getLogger("flash")

# Liquid, fast-moving pairs — flash needs volatility + depth to clear costs.
FLASH_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
    "ADAUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT", "TIAUSDT",
]
# 15m + 1h: fast enough to fire many times a day, but with enough ATR that the round-trip cost is a
# SMALL fraction of risk. (5m was measured at ~69% cost-to-risk — mathematically unwinnable.)
FLASH_INTERVALS = ["15m", "1h"]


def _f(row: pd.Series, key: str) -> float | None:
    v = row.get(key)
    if v is None or pd.isna(v):
        return None
    return float(v)


def detect_trigger(ind: pd.DataFrame) -> dict | None:
    """Find a fast setup on the LAST CLOSED bar. Returns {direction, kind, strength} or None.

    Three trigger families, all causal (computed from closed bars only):
      * burst     — price thrusts through EMA9 with volume expansion and momentum confirming
      * breakout  — close takes out the recent N-bar extreme with volatility expanding
      * snap      — stretched from VWAP then reverses (fast mean-reversion scalp)
    """
    if len(ind) < 30:
        return None
    last, prev = ind.iloc[-1], ind.iloc[-2]

    close = _f(last, "close")
    ema9 = _f(last, "ema9")
    ema21 = _f(last, "ema21")
    rsi = _f(last, "rsi")
    atr = _f(last, "atr")
    vol = _f(last, "volume")
    vol_sma = _f(last, "vol_sma20")
    vwap_dist = _f(last, "vwap_dist")
    if None in (close, ema9, ema21, rsi, atr) or atr <= 0 or close <= 0:
        return None

    vol_exp = (vol / vol_sma) if (vol and vol_sma and vol_sma > 0) else 1.0
    prev_close = _f(prev, "close") or close
    thrust = (close - prev_close) / close                      # last-bar impulse
    atr_pct = atr / close

    # --- burst: impulse through the fast EMA with participation ---
    if vol_exp >= settings.flash_vol_expansion and abs(thrust) >= 0.25 * atr_pct:
        if close > ema9 > ema21 and rsi > 52 and thrust > 0:
            return {"direction": "long", "kind": "burst", "strength": min(100.0, 40 + 30 * vol_exp)}
        if close < ema9 < ema21 and rsi < 48 and thrust < 0:
            return {"direction": "short", "kind": "burst", "strength": min(100.0, 40 + 30 * vol_exp)}

    # --- breakout: takes out the recent extreme, volatility expanding ---
    lookback = ind["high"].iloc[-(settings.flash_breakout_bars + 1):-1]
    lookback_lo = ind["low"].iloc[-(settings.flash_breakout_bars + 1):-1]
    if len(lookback) >= settings.flash_breakout_bars:
        hi_n, lo_n = float(lookback.max()), float(lookback_lo.min())
        if close > hi_n and vol_exp >= 1.1 and rsi > 50:
            return {"direction": "long", "kind": "breakout", "strength": min(100.0, 45 + 25 * vol_exp)}
        if close < lo_n and vol_exp >= 1.1 and rsi < 50:
            return {"direction": "short", "kind": "breakout", "strength": min(100.0, 45 + 25 * vol_exp)}

    # --- snap: stretched from VWAP and reversing (fast fade) ---
    if vwap_dist is not None:
        stretch = settings.flash_snap_stretch
        if vwap_dist < -stretch and rsi < 32 and thrust > 0:
            return {"direction": "long", "kind": "snap", "strength": 55.0}
        if vwap_dist > stretch and rsi > 68 and thrust < 0:
            return {"direction": "short", "kind": "snap", "strength": 55.0}
    return None


def evaluate(symbol: str, interval: str) -> dict | None:
    """Compute a full flash candidate for one symbol/interval, or None if no trigger."""
    try:
        df = fetch_klines(symbol, interval, 200)
        df, _ = validate_ohlcv(df, interval)
        ind = compute_indicators(df)
    except Exception:
        return None
    trig = detect_trigger(ind)
    if trig is None:
        return None

    last = ind.iloc[-1]
    price = _f(last, "close")
    atr = _f(last, "atr")
    if not price or not atr or atr <= 0:
        return None
    atr_pct = atr / price
    direction = trig["direction"]

    # Tight scalp geometry: stop 1.0x ATR, target = flash_rr x stop.
    stop_dist = settings.flash_stop_atr * atr
    tgt_dist = settings.flash_rr * stop_dist
    if direction == "long":
        entry, stop, target = price, price - stop_dist, price + tgt_dist
    else:
        entry, stop, target = price, price + stop_dist, price - tgt_dist

    stop_frac = stop_dist / price
    cost_r = cost_in_r("crypto", symbol, atr_pct, stop_frac)
    # Flash EV: assume the trigger's historical edge is modest; require the payoff to clear cost
    # with a real margin. p is taken from the flash performance record (falls back to a prior).
    p = flash_win_rate()
    ev_r = p * settings.flash_rr - (1.0 - p) - cost_r

    return {
        "symbol": symbol, "interval": interval, "market": "crypto",
        "direction": direction, "kind": trig["kind"], "strength": round(trig["strength"], 1),
        "as_of": str(ind.index[-1]),
        "price": round(price, 8), "atr": round(atr, 8), "atr_pct": round(atr_pct, 5),
        "entry": round(entry, 8), "stop": round(stop, 8), "target": round(target, 8),
        "reward_risk": settings.flash_rr,
        "cost_r": round(cost_r, 4), "win_prob": round(p, 4), "ev_r": round(ev_r, 4),
        "tradeable": bool(ev_r > settings.flash_min_ev_r and atr_pct >= settings.flash_min_atr_pct),
    }


# --- flash performance (its own gate + its own P&L) -------------------------

def flash_stats(window_days: int = 7) -> dict:
    """Rolling flash-only performance: {trades, wins, hit_rate, pnl_frac}."""
    out = {"trades": 0, "wins": 0, "hit_rate": None, "pnl_frac": 0.0}
    if not db.enabled():
        return out
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""select count(*), count(*) filter (where o.pnl > 0), coalesce(sum(o.pnl), 0)
                    from outcomes o join signals s on s.id = o.signal_id
                    where o.pnl is not null and s.strategy = 'flash'
                      and o.resolved_at > now() - interval '{int(window_days)} days'"""
            )
            n, w, p = cur.fetchone()
        n, w = int(n or 0), int(w or 0)
        out = {"trades": n, "wins": w, "hit_rate": round(w / n, 4) if n else None,
               "pnl_frac": float(p or 0.0)}
    except Exception:
        pass
    return out


def flash_win_rate() -> float:
    """Calibrated flash win rate — its own record once it exists, else a conservative prior."""
    s = flash_stats(settings.flash_perf_window_days)
    if s["trades"] >= settings.flash_perf_min_sample and s["hit_rate"] is not None:
        return float(min(0.85, max(0.15, s["hit_rate"])))
    return settings.flash_prior_win_rate


def is_enabled() -> bool:
    """Flash trades unless its own recent record is proven-negative (self-protecting)."""
    if not settings.flash_enabled:
        return False
    s = flash_stats(settings.flash_perf_window_days)
    if s["trades"] >= settings.flash_perf_min_sample and s["pnl_frac"] < 0:
        return False   # proven-losing over the window -> stand down until losses age out
    return True


# --- scan + log -------------------------------------------------------------

def scan(log: bool = True) -> dict:
    """Sweep the flash universe; log tradeable setups as strategy='flash'."""
    if not settings.flash_enabled:
        return {"enabled": False, "scanned": 0, "triggers": [], "emitted": 0}
    active = is_enabled()
    scanned = 0
    triggers: list[dict] = []
    emitted = 0

    for symbol in FLASH_SYMBOLS:
        for interval in FLASH_INTERVALS:
            scanned += 1
            c = evaluate(symbol, interval)
            if c is None:
                continue
            triggers.append(c)
            if log and active and c["tradeable"]:
                if persistence.signal_exists(symbol, interval, c["as_of"]):
                    continue
                if _log_flash(c) is not None:
                    emitted += 1
                    logger.info("FLASH %s %s %s %s ev=%.3f", c["kind"], c["direction"], symbol, interval, c["ev_r"])

    triggers.sort(key=lambda x: x["ev_r"], reverse=True)
    return {
        "enabled": True, "active": active, "scanned": scanned,
        "triggers": triggers[:25], "emitted": emitted,
        "win_rate": flash_win_rate(), "stats": flash_stats(settings.flash_perf_window_days),
    }


def _log_flash(c: dict) -> int | None:
    """Persist a flash setup as a signal row tagged strategy='flash'."""
    label = "Strong Buy" if c["direction"] == "long" else "Strong Sell"
    sig = {
        "symbol": c["symbol"], "market": "crypto", "interval": c["interval"], "as_of": c["as_of"],
        "label": label, "composite": c["strength"] if c["direction"] == "long" else -c["strength"],
        "confidence": c["strength"], "regime": f"flash_{c['kind']}",
        "price": c["price"], "atr": c["atr"],
        "levels": {"entry": c["entry"], "stop": c["stop"], "target": c["target"]},
        "targets": [c["target"], None, None],
        "tier": "flash", "reward_risk": c["reward_risk"], "size_pct": settings.flash_risk_pct,
        "invalidation": f"{c['interval']} close beyond {c['stop']}",
        "psychology": f"flash {c['kind']} ({c['strength']:.0f} strength)",
        "win_prob": c["win_prob"], "ev_r": c["ev_r"],
        "strategy": "flash",
        # In paper mode the row is flagged shadow -> automatically excluded from the live P&L and
        # from every decision/learning query, while flash's OWN stats still count it.
        "shadow": settings.flash_paper_mode,
    }
    return persistence.log_decision(sig)
