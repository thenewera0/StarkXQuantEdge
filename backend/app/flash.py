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
    "LTCUSDT", "DOTUSDT", "ATOMUSDT", "UNIUSDT", "FILUSDT", "SEIUSDT", "AAVEUSDT", "RUNEUSDT",
    "ETCUSDT", "XLMUSDT", "GRTUSDT", "TRXUSDT",
]
# 15m + 1h: fast enough to fire many times a day, but with enough ATR that the round-trip cost is a
# SMALL fraction of risk. (5m was measured at ~69% cost-to-risk — mathematically unwinnable.)
FLASH_INTERVALS = ["15m", "1h"]


def _f(row: pd.Series, key: str) -> float | None:
    v = row.get(key)
    if v is None or pd.isna(v):
        return None
    return float(v)


def flash_score(ind: pd.DataFrame) -> dict | None:
    """Flash v2 — multi-factor confluence score in [-100, +100] for a fast trade.

    v1 used three naive triggers and measured a losing edge (35% win, PF 0.65). v2 demands agreement
    across genuinely independent evidence, so it fires far less often but on much better setups:

      F1 ORDER FLOW   (cvd_z, flow_ratio)  — are AGGRESSIVE buyers or sellers actually in control?
                       Free from Binance taker volume; independent of price pattern.
      F2 MOMENTUM     (EMA stack, RSI, MACD histogram vs ATR) — directional thrust.
      F3 EXCITATION   (Hawkes burst on range + volume) — are we inside an ACTIVE cluster? Fast
                       trades need continued activity; dead tape is where scalps die of fees.
      F4 VOL REGIME   (Parkinson vol ratio) — expansion favours continuation, compression fades.
      F5 LOCATION     (VWAP distance, band position) — is entry at a sane price or chasing?

    Returns {score, direction, factors} or None if inputs are unusable.
    """
    if len(ind) < 60:
        return None
    last = ind.iloc[-1]
    close, atr = _f(last, "close"), _f(last, "atr")
    if not close or not atr or atr <= 0:
        return None

    f: dict[str, float] = {}

    # --- F1 order flow (the edge most retail never touches) ---
    cvd_z, flow_ratio = _f(last, "cvd_z"), _f(last, "flow_ratio")
    if cvd_z is not None:
        f["flow"] = max(-100.0, min(100.0, cvd_z * 28.0 + (flow_ratio or 0.0) * 45.0))

    # --- F2 momentum ---
    ema9, ema21, ema50 = _f(last, "ema9"), _f(last, "ema21"), _f(last, "ema50")
    rsi, macd_h = _f(last, "rsi"), _f(last, "macd_hist")
    if None not in (ema9, ema21, ema50, rsi):
        stack = (1 if ema9 > ema21 else -1) + (1 if ema21 > ema50 else -1) + (1 if close > ema9 else -1)
        mom = stack / 3.0 * 55.0 + (rsi - 50.0) * 1.1
        if macd_h is not None:
            mom += max(-30.0, min(30.0, macd_h / (0.4 * atr) * 30.0))
        f["momentum"] = max(-100.0, min(100.0, mom))

    # --- F3 excitation (unsigned: gates, doesn't pick a side) ---
    burst, vol_burst = _f(last, "burst"), _f(last, "vol_burst")
    if burst is not None or vol_burst is not None:
        f["excitation"] = max(-100.0, min(100.0, 30.0 * ((burst or 0.0) + (vol_burst or 0.0))))

    # --- F4 volatility regime (unsigned) ---
    pk = _f(last, "pk_vol_ratio")
    if pk is not None:
        f["vol_regime"] = max(-100.0, min(100.0, (pk - 1.0) * 90.0))

    # --- F5 location ---
    vwap_dist, pctb = _f(last, "vwap_dist"), _f(last, "bb_pctb")
    loc = 0.0
    if vwap_dist is not None:
        loc += max(-60.0, min(60.0, -vwap_dist / 0.004 * 60.0))   # penalise chasing far from VWAP
    if pctb is not None:
        loc += max(-40.0, min(40.0, -(pctb - 0.5) * 80.0))
    f["location"] = max(-100.0, min(100.0, loc))

    directional = [f.get("flow"), f.get("momentum")]
    directional = [x for x in directional if x is not None]
    if not directional:
        return None

    # Weighted blend. Flow + momentum carry direction; location tempers chasing.
    w = {"flow": 0.40, "momentum": 0.40, "location": 0.20}
    num = sum(w[k] * f[k] for k in w if k in f)
    den = sum(w[k] for k in w if k in f)
    raw = num / den if den > 0 else 0.0

    # Agreement: flow and momentum must not fight each other.
    agree = 1.0
    if "flow" in f and "momentum" in f:
        agree = 1.0 if (f["flow"] >= 0) == (f["momentum"] >= 0) else 0.35
    score = raw * agree

    return {"score": round(score, 2), "direction": "long" if score > 0 else "short", "factors": f}


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

    # --- dip: buy a pullback INSIDE an uptrend ---
    # Research (v3/H3) made this the best-performing family by a clear margin: PF 0.67 and 37% win
    # vs 30% for breakout chasing. It mirrors what the CORE engine's winning longs actually look
    # like — mean reversion inside an intact trend, not momentum chasing.
    ema200 = _f(last, "ema200")
    if ema200 is not None and close > ema200 and rsi < 42 and close < ema21 and thrust > 0:
        return {"direction": "long", "kind": "dip", "strength": 60.0}

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
    # EV uses the win rate LEARNED for this specific trigger kind (falls back to the overall flash
    # record, then a conservative prior). So as evidence accumulates, each family is judged on its
    # own merit rather than one blended number.
    p = kind_win_rate(trig["kind"])
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


# --- self-learning: flash narrows to what its OWN record proves -------------
#
# This is the machinery that actually created the core engine's edge. Raw signals backtest
# negative; the LIVE gated system is profitable — because per-regime / per-direction / per-symbol
# gates progressively cut what loses. Flash gets the same treatment on its own outcomes:
#
#   * per-TRIGGER-KIND gate   burst / breakout / snap / dip — drop kinds that prove negative
#   * per-SYMBOL gate         drop pairs that prove negative for fast trading
#   * per-INTERVAL gate       drop timeframes that prove negative
#   * adaptive win rate       EV uses its own realized hit rate, per kind, not a fixed prior
#   * auto-promotion          paper -> live capital once the record is genuinely positive
#
# Thin buckets always get benefit of the doubt so the bot keeps exploring and can recover.

_LEARN_TTL = 180.0
_learn_cache: tuple[float, dict] | None = None


def _bucket_stats(window_days: int) -> dict:
    """Realized flash stats grouped by trigger kind, symbol and interval."""
    out = {"kind": {}, "symbol": {}, "interval": {}}
    if not db.enabled():
        return out
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""select coalesce(s.regime,'flash_?') kind, s.symbol, s.interval,
                           o.pnl
                    from outcomes o join signals s on s.id = o.signal_id
                    where o.pnl is not null and s.strategy = 'flash'
                      and o.resolved_at > now() - interval '{int(window_days)} days'"""
            )
            rows = cur.fetchall()
    except Exception:
        return out

    def add(group: str, key: str, pnl: float) -> None:
        b = out[group].setdefault(key, {"trades": 0, "wins": 0, "pnl": 0.0})
        b["trades"] += 1
        b["wins"] += 1 if pnl > 0 else 0
        b["pnl"] += pnl

    for kind, sym, itv, pnl in rows:
        p = float(pnl)
        add("kind", str(kind).replace("flash_", ""), p)
        add("symbol", sym, p)
        add("interval", itv, p)
    for g in out.values():
        for b in g.values():
            b["hit_rate"] = round(b["wins"] / b["trades"], 4) if b["trades"] else None
            b["pnl"] = round(b["pnl"], 6)
    return out


def learning_state(window_days: int | None = None) -> dict:
    """Cached view of what flash has learned, plus the gates it implies."""
    global _learn_cache
    import time as _t
    now = _t.time()
    if _learn_cache and now - _learn_cache[0] < _LEARN_TTL:
        return _learn_cache[1]

    wd = window_days or settings.flash_learn_window_days
    stats = _bucket_stats(wd)
    minn = settings.flash_learn_min_sample

    def gate(group: str) -> dict:
        allowed, blocked = [], []
        for key, b in stats[group].items():
            # thin -> keep exploring; proven-negative -> drop until it ages out
            if b["trades"] < minn or b["pnl"] > 0:
                allowed.append(key)
            else:
                blocked.append(key)
        return {"allowed": sorted(allowed), "blocked": sorted(blocked)}

    state = {
        "window_days": wd, "min_sample": minn,
        "stats": stats,
        "kinds": gate("kind"), "symbols": gate("symbol"), "intervals": gate("interval"),
    }
    _learn_cache = (now, state)
    return state


def refresh_learning() -> None:
    global _learn_cache
    _learn_cache = None


def _is_blocked(state: dict, group: str, key: str) -> bool:
    return key in state[group]["blocked"]


def kind_win_rate(kind: str) -> float:
    """Win rate for THIS trigger kind from its own record; conservative prior when thin."""
    if not settings.flash_learn_enabled:
        return flash_win_rate()
    b = learning_state()["stats"]["kind"].get(kind)
    if b and b["trades"] >= settings.flash_learn_min_sample and b["hit_rate"] is not None:
        return float(min(0.85, max(0.15, b["hit_rate"])))
    return flash_win_rate()


def promotion_status() -> dict:
    """Should flash graduate from paper to real capital? Decided purely by its own record."""
    s = flash_stats(settings.flash_perf_window_days)
    need = settings.flash_promote_min_trades
    ready = bool(s["trades"] >= need and s["pnl_frac"] > 0
                 and (s["hit_rate"] or 0) >= settings.flash_promote_min_hit)
    return {
        "paper": settings.flash_paper_mode,
        "trades": s["trades"], "needed": need,
        "pnl_frac": s["pnl_frac"], "hit_rate": s["hit_rate"],
        "ready_to_promote": ready,
        "blocker": None if ready else (
            f"needs {need - s['trades']} more trades" if s["trades"] < need
            else "record is not yet profitable"),
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
    learn = learning_state() if settings.flash_learn_enabled else None
    scanned = 0
    triggers: list[dict] = []
    emitted = 0
    gated = 0

    for symbol in FLASH_SYMBOLS:
        # Learned gate: a pair that has proven negative for FAST trading is skipped entirely.
        if learn and _is_blocked(learn, "symbols", symbol):
            continue
        for interval in FLASH_INTERVALS:
            if learn and _is_blocked(learn, "intervals", interval):
                continue
            scanned += 1
            c = evaluate(symbol, interval)
            if c is None:
                continue
            # Learned gate: drop trigger families this bot has proven it cannot trade.
            if learn and _is_blocked(learn, "kinds", c["kind"]):
                c["tradeable"] = False
                c["blocked_by"] = f"'{c['kind']}' setups have proven negative — learning gate"
                gated += 1
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
        "triggers": triggers[:25], "emitted": emitted, "gated_by_learning": gated,
        "win_rate": flash_win_rate(), "stats": flash_stats(settings.flash_perf_window_days),
        "learning": learn, "promotion": promotion_status(),
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
