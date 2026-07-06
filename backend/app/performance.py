"""Paper-trading P&L across every signal the engine emitted.

Assumes a FIXED notional per trade (standard_trade_size_usd) — every trade risks the same dollar
exposure, so results are comparable across assets regardless of coin price. Reports:

  * realized: closed trades (target/stop/timeout), individual $ P&L + per-asset + combined
  * open: still-open trades marked to the latest price (floating/unrealized P&L)

pnl in the DB is a net return fraction (already after fees + slippage). Dollar P&L = fraction × size.
"""

from __future__ import annotations

from . import db
from .config import settings
from .data import fetch_klines, fetch_klines_td

_LONG = {"Buy", "Strong Buy"}


def _direction(label: str) -> str:
    return "long" if label in _LONG else "short"


def _last_price(symbol: str, market: str, interval: str) -> float | None:
    try:
        if (market or "crypto").lower() == "crypto":
            df = fetch_klines(symbol, interval, 2)
        else:
            df = fetch_klines_td(symbol, interval, outputsize=2)
        return float(df["close"].iloc[-1])
    except Exception:
        return None


def summary(trade_size: float | None = None) -> dict:
    """Weekly / monthly / all-time trade + P&L summary, plus what self-learning has changed."""
    size = trade_size or settings.standard_trade_size_usd
    if not db.enabled():
        return {"enabled": False}

    from . import learning

    def window(days: int | None) -> dict:
        clause = "o.pnl is not null"
        if days:
            clause += f" and o.resolved_at >= now() - interval '{int(days)} days'"
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""select count(*), count(*) filter (where o.pnl>0),
                        coalesce(sum(o.pnl),0), coalesce(max(o.pnl),0), coalesce(min(o.pnl),0)
                    from outcomes o where {clause}"""
            )
            n, w, s, mx, mn = cur.fetchone()
        n = int(n)
        return {
            "trades": n, "wins": int(w), "losses": n - int(w),
            "hit_rate": round(int(w) / n, 4) if n else None,
            "realized_pnl_usd": round(float(s) * size, 2),
            "best_usd": round(float(mx) * size, 2),
            "worst_usd": round(float(mn) * size, 2),
        }

    perf = learning.regime_performance()
    tradeable = sorted(learning.tradeable_regimes())
    dir_perf = learning.direction_performance()
    tradeable_dirs = sorted(learning.tradeable_directions())
    direction_performance = {
        d: {"trades": p["trades"], "pnl_usd": round(p["pnl_frac"] * size, 2),
            "hit_rate": round(p["wins"] / p["trades"], 3) if p["trades"] else None,
            "tradeable": d in tradeable_dirs}
        for d, p in dir_perf.items()
    }
    regime_perf = {
        r: {"trades": p["trades"], "pnl_usd": round(p["pnl_frac"] * size, 2),
            "hit_rate": round(p["wins"] / p["trades"], 3) if p["trades"] else None,
            "tradeable": r in tradeable}
        for r, p in sorted(perf.items(), key=lambda x: -x[1]["pnl_frac"])
    }
    champions = learning.learning_status().get("champions", {}) if db.enabled() else {}

    return {
        "enabled": True,
        "trade_size_usd": size,
        "week": window(7),
        "month": window(30),
        "all_time": window(None),
        "learning": {
            "tradeable_regimes": tradeable,
            "excluded_regimes": [r for r in regime_perf if r not in tradeable],
            "regime_performance": regime_perf,
            "tradeable_directions": tradeable_dirs,
            "direction_performance": direction_performance,
            "champion_weight_profiles": len(champions),
        },
    }


def performance(trade_size: float | None = None) -> dict:
    """Combined + per-asset realized and floating P&L in USD at a fixed notional per trade."""
    size = trade_size or settings.standard_trade_size_usd
    if not db.enabled():
        return {"enabled": False}

    # --- Realized (closed) trades, oldest first for the equity curve ---
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select s.symbol, coalesce(s.market,'crypto') as market, s.interval, s.label,
                       coalesce(s.regime,'unknown') as regime,
                       o.result, o.pnl, o.bars_held, o.resolved_at
                from outcomes o join signals s on s.id = o.signal_id
                where o.result is not null and o.pnl is not null
                order by o.resolved_at asc
                """
            )
            cols = [c.name for c in cur.description]
            closed = [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return {"enabled": True, "error": "query failed"}

    per_symbol: dict[str, dict] = {}
    per_regime: dict[str, dict] = {}
    trades: list[dict] = []
    equity_curve: list[dict] = [{"i": 0, "cum_pnl_usd": 0.0, "time": None}]
    realized_usd = 0.0
    wins = 0
    for i, c in enumerate(closed, start=1):
        pnl_frac = float(c["pnl"])
        pnl_usd = pnl_frac * size
        realized_usd += pnl_usd
        won = pnl_frac > 0
        wins += 1 if won else 0

        sym = c["symbol"]
        agg = per_symbol.setdefault(sym, {"symbol": sym, "trades": 0, "wins": 0, "pnl_usd": 0.0})
        agg["trades"] += 1
        agg["wins"] += 1 if won else 0
        agg["pnl_usd"] += pnl_usd

        reg = c["regime"]
        ragg = per_regime.setdefault(reg, {"regime": reg, "trades": 0, "wins": 0, "pnl_usd": 0.0})
        ragg["trades"] += 1
        ragg["wins"] += 1 if won else 0
        ragg["pnl_usd"] += pnl_usd

        equity_curve.append({"i": i, "cum_pnl_usd": round(realized_usd, 2), "time": str(c["resolved_at"])})
        trades.append({
            "symbol": sym, "interval": c["interval"], "direction": _direction(c["label"]),
            "regime": reg, "result": c["result"], "pnl_pct": round(pnl_frac * 100, 2),
            "pnl_usd": round(pnl_usd, 2), "bars_held": c["bars_held"], "resolved_at": str(c["resolved_at"]),
        })

    n_closed = len(closed)
    for agg in per_symbol.values():
        agg["pnl_usd"] = round(agg["pnl_usd"], 2)
    per_regime_list = []
    for r in per_regime.values():
        r["pnl_usd"] = round(r["pnl_usd"], 2)
        r["hit_rate"] = round(r["wins"] / r["trades"], 4) if r["trades"] else None
        per_regime_list.append(r)
    per_regime_list.sort(key=lambda x: x["pnl_usd"], reverse=True)
    trades.reverse()  # most recent first for the log

    # --- Open trades marked to market (floating) ---
    open_usd = 0.0
    open_positions: list[dict] = []
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select s.id, s.symbol, coalesce(s.market,'crypto') as market, s.interval, s.label, s.entry
                from signals s
                where not exists (select 1 from outcomes o where o.signal_id = s.id)
                  and s.entry is not null and s.label <> 'Neutral'
                order by s.created_at desc
                """
            )
            cols = [c.name for c in cur.description]
            open_rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        open_rows = []

    price_cache: dict[tuple, float | None] = {}
    for o in open_rows:
        key = (o["symbol"], o["market"], o["interval"])
        if key not in price_cache:
            price_cache[key] = _last_price(*key)
        last = price_cache[key]
        entry = float(o["entry"])
        if last is None or entry <= 0:
            continue
        direction = _direction(o["label"])
        frac = (last - entry) / entry if direction == "long" else (entry - last) / entry
        pnl_usd = frac * size
        open_usd += pnl_usd
        open_positions.append({
            "symbol": o["symbol"], "interval": o["interval"], "direction": direction,
            "entry": entry, "price": last, "pnl_pct": round(frac * 100, 2), "pnl_usd": round(pnl_usd, 2),
        })

    per_symbol_list = sorted(per_symbol.values(), key=lambda x: x["pnl_usd"], reverse=True)

    return {
        "enabled": True,
        "trade_size_usd": size,
        "combined": {
            "realized_pnl_usd": round(realized_usd, 2),
            "open_pnl_usd": round(open_usd, 2),
            "total_pnl_usd": round(realized_usd + open_usd, 2),
            "closed_trades": n_closed,
            "open_trades": len(open_positions),
            "wins": wins,
            "losses": n_closed - wins,
            "hit_rate": round(wins / n_closed, 4) if n_closed else None,
            "total_return_pct": round(realized_usd / (size * n_closed) * 100, 2) if n_closed else None,
        },
        "per_symbol": per_symbol_list,
        "per_regime": per_regime_list,
        "equity_curve": equity_curve,
        "trades": trades[:40],
        "open_positions": open_positions[:40],
    }
