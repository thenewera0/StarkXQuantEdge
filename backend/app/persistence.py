"""Write signals, factor scores, and outcomes to Postgres. All writes are best-effort:

a database problem must never break a signal response. Every function returns gracefully (None /
False) when persistence is disabled or errors, and logs nothing sensitive.
"""

from __future__ import annotations

import json

from . import db


def log_decision(sig: dict) -> int | None:
    """Persist a /decision (or /explain) result + its factor scores. Returns the new signal id."""
    if not db.enabled():
        return None

    cats = sig.get("categories", {})
    explanation = sig.get("explanation") or {}
    final = sig.get("final") or {}
    debate = sig.get("debate") or {}

    # SHADOW: a candidate the live gates silenced. Persist it as a paper trade (its would-be label +
    # levels) so the learning layer keeps getting outcomes, but flag it so the P&L excludes it.
    shadow = bool(sig.get("shadow"))
    # A shadow row may carry its would-be levels in `candidate` (silenced core signal). Flash paper
    # trades set their levels directly, so only fall back to `candidate` when it's actually present.
    cand = sig.get("candidate") or {}
    use_cand = shadow and bool(cand)
    src = cand if use_cand else sig
    lv = cand if use_cand else sig.get("levels", {})
    label = cand.get("label") if use_cand else sig.get("label")
    targets = (cand.get("targets") if use_cand else sig.get("targets")) or []
    t2 = targets[1] if len(targets) > 1 else None
    t3 = targets[2] if len(targets) > 2 else None

    # Direction inference for fingerprint
    if label in ("Buy", "Strong Buy"):
        direction = "long"
    elif label in ("Sell", "Strong Sell"):
        direction = "short"
    else:
        direction = "flat"

    as_of = sig.get("as_of")
    interval = sig.get("interval")

    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                with bar_calc as (
                    select get_canonical_bar_open(%s::timestamptz, %s::text) as b_open
                )
                insert into signals
                  (symbol, market, interval, as_of, label, composite, confidence, regime,
                   price, atr, rationale, entry, stop, target,
                   agreement, conviction, final_confidence, debate_source,
                   tier, reward_risk, size_pct, invalidation, target2, target3, psychology,
                   win_prob, ev_r, features, meta_p, shadow, strategy,
                   direction, bar_open_time, scan_phase, is_duplicate)
                select
                   %s,%s,%s,%s,%s,%s,%s,%s,
                   %s,%s,%s,%s,%s,%s,
                   %s,%s,%s,%s,
                   %s,%s,%s,%s,%s,%s,%s,
                   %s,%s,%s::jsonb,%s,%s,%s,
                   %s, b_open, case when %s::timestamptz = b_open then 'bar_close' else 'mid_bar' end, false
                from bar_calc
                on conflict do nothing
                returning id
                """,
                (
                    as_of, interval,
                    sig.get("symbol"), sig.get("market"), interval, as_of,
                    label, sig.get("composite"), sig.get("confidence"), sig.get("regime"),
                    sig.get("price"), sig.get("atr"), explanation.get("rationale"),
                    lv.get("entry"), lv.get("stop"), lv.get("target"),
                    final.get("agreement"), final.get("conviction"), final.get("final_confidence"),
                    debate.get("source"),
                    sig.get("tier"), src.get("reward_risk"), src.get("size_pct"),
                    sig.get("invalidation"), t2, t3, sig.get("psychology"),
                    src.get("win_prob"), src.get("ev_r"),
                    json.dumps(sig.get("features")) if sig.get("features") is not None else None,
                    sig.get("meta_p"), shadow, sig.get("strategy", "core"),
                    direction, as_of,
                ),
            )
            row = cur.fetchone()
            if row is None:  # duplicate (fingerprint or as_of) — already logged, skip cleanly
                conn.commit()
                return None
            signal_id = row[0]
            cur.execute(
                """
                insert into factor_logs
                  (signal_id, trend, momentum, volatility, structure, flow, sentiment, macro, consensus)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    signal_id, cats.get("trend"), cats.get("momentum"), cats.get("volatility"),
                    cats.get("structure"), cats.get("flow"), cats.get("sentiment"),
                    cats.get("macro"), cats.get("consensus"),
                ),
            )
            conn.commit()
            return signal_id
    except Exception:
        return None


def record_outcome(
    signal_id: int, result: str, *, pnl: float | None = None,
    mfe: float | None = None, mae: float | None = None, bars_held: int | None = None,
    r_net: float | None = None, cost_r: float | None = None,
) -> bool:
    """Label a stored signal with what actually happened. The fuel for the learning loop."""
    if not db.enabled():
        return False
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into outcomes (signal_id, resolved_at, result, pnl, mfe, mae, bars_held, r_net, cost_r)
                values (%s, now(), %s, %s, %s, %s, %s, %s, %s)
                """,
                (signal_id, result, pnl, mfe, mae, bars_held, r_net, cost_r),
            )
            conn.commit()
            return True
    except Exception:
        return False



def update_signal_stop(signal_id: int, new_stop: float) -> bool:
    """Update an active signal's stop level in the database (e.g. trailing stop / breakeven)."""
    if not db.enabled():
        return False
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute("update signals set stop = %s where id = %s", (new_stop, signal_id))
            conn.commit()
            return True
    except Exception:
        return False


def trade_history(result_filter: str = "all", limit: int = 50, offset: int = 0,
                  trade_size: float = 1000.0, strategy: str = "core") -> dict:
    """Paginated closed-trade history with wins/losses/all counts. Newest first."""
    if not db.enabled():
        return {"trades": [], "counts": {"all": 0, "wins": 0, "losses": 0}, "limit": limit, "offset": offset}
    
    if strategy == "flash":
        strat_clause = "s.strategy = 'flash'"
    elif strategy == "all":
        strat_clause = "(s.shadow = false or s.strategy = 'flash')"
    else:  # "core"
        strat_clause = "(s.strategy = 'core' or s.strategy is null) and s.shadow = false"

    where = f"o.pnl is not null and {strat_clause}"
    if result_filter == "wins":
        where += " and o.pnl > 0"
    elif result_filter == "losses":
        where += " and o.pnl <= 0"
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""select count(*) filter (where o.pnl is not null),
                          count(*) filter (where o.pnl > 0),
                          count(*) filter (where o.pnl <= 0),
                          coalesce(sum(o.pnl) filter (where o.pnl > 0), 0),
                          coalesce(sum(o.pnl) filter (where o.pnl <= 0), 0),
                          coalesce(sum(o.pnl), 0)
                   from outcomes o join signals s on s.id = o.signal_id where {strat_clause}"""
            )
            all_c, wins, losses, gross_win_frac, gross_loss_frac, net_pnl_frac = cur.fetchone()
            all_c = int(all_c or 0)
            wins = int(wins or 0)
            losses = int(losses or 0)
            gross_profit_usd = round(float(gross_win_frac or 0.0) * trade_size, 2)
            gross_loss_usd = round(float(gross_loss_frac or 0.0) * trade_size, 2)
            net_pnl_usd = round(float(net_pnl_frac or 0.0) * trade_size, 2)
            profit_factor = round(abs(gross_profit_usd / gross_loss_usd), 2) if gross_loss_usd != 0 else None
            avg_win_usd = round(gross_profit_usd / wins, 2) if wins else 0.0
            avg_loss_usd = round(gross_loss_usd / losses, 2) if losses else 0.0
            win_rate = round(wins / all_c, 4) if all_c else 0.0

            cur.execute(
                f"""select s.id, s.symbol, s.interval, s.label, coalesce(s.regime,'unknown') regime,
                          s.entry, o.result, o.pnl, o.bars_held, o.resolved_at,
                          coalesce(s.strategy, 'core') as strategy
                    from outcomes o join signals s on s.id = o.signal_id
                    where {where}
                    order by o.resolved_at desc
                    limit %s offset %s""",
                (limit, offset),
            )
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return {"trades": [], "counts": {"all": 0, "wins": 0, "losses": 0}, "limit": limit, "offset": offset}

    trades = [{
        "id": r["id"], "symbol": r["symbol"], "interval": r["interval"], "regime": r["regime"],
        "strategy": r["strategy"],
        "direction": "long" if r["label"] in ("Buy", "Strong Buy") else "short", "result": r["result"],
        "entry": float(r["entry"]) if r.get("entry") is not None else None,
        "pnl_pct": round(float(r["pnl"]) * 100, 2), "pnl_usd": round(float(r["pnl"]) * trade_size, 2),
        "bars_held": r["bars_held"], "resolved_at": str(r["resolved_at"]),
    } for r in rows]

    perf_stats = {
        "all": all_c, "wins": wins, "losses": losses,
        "gross_profit_usd": gross_profit_usd,
        "gross_loss_usd": gross_loss_usd,
        "net_pnl_usd": net_pnl_usd,
        "profit_factor": profit_factor,
        "avg_win_usd": avg_win_usd,
        "avg_loss_usd": avg_loss_usd,
        "win_rate": win_rate,
    }
    return {
        "trades": trades,
        "counts": perf_stats,
        "performance": perf_stats,
        "limit": limit, "offset": offset,
    }


def get_trade(signal_id: int) -> dict | None:
    """Full stored detail for one signal: the signal + its 8 factor scores + resolved outcome."""
    if not db.enabled():
        return None
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select s.id, s.symbol, s.market, s.interval, s.as_of, s.label, s.composite,
                       s.confidence, s.regime, s.price, s.atr, s.rationale, s.entry, s.stop, s.target,
                       s.agreement, s.conviction, s.final_confidence, s.tier, s.reward_risk,
                       s.size_pct, s.invalidation, s.target2, s.target3, s.psychology, s.created_at,
                       coalesce(s.strategy, 'core') as strategy,
                       f.trend, f.momentum, f.volatility, f.structure, f.flow, f.sentiment, f.macro, f.consensus,
                       o.result, o.pnl, o.mfe, o.mae, o.bars_held, o.resolved_at
                from signals s
                left join factor_logs f on f.signal_id = s.id
                left join outcomes o on o.signal_id = s.id
                where s.id = %s
                """,
                (signal_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [c.name for c in cur.description]
            d = dict(zip(cols, row))

        factors = {k: d.pop(k) for k in ("trend", "momentum", "volatility", "structure",
                                          "flow", "sentiment", "macro", "consensus")}
        outcome = {k: d.pop(k) for k in ("result", "pnl", "mfe", "mae", "bars_held", "resolved_at")}

        def num(v):
            return float(v) if v is not None else None

        return {
            "id": d["id"], "symbol": d["symbol"], "market": d["market"], "interval": d["interval"],
            "as_of": str(d["as_of"]), "created_at": str(d["created_at"]), "label": d["label"],
            "regime": d["regime"], "tier": d["tier"], "strategy": d.get("strategy", "core"),
            "composite": num(d["composite"]), "confidence": num(d["confidence"]),
            "agreement": num(d["agreement"]), "conviction": num(d["conviction"]),
            "final_confidence": num(d["final_confidence"]),
            "price": num(d["price"]), "atr": num(d["atr"]),
            "direction": "long" if d["label"] in ("Buy", "Strong Buy") else
                         ("short" if d["label"] in ("Sell", "Strong Sell") else "flat"),
            "entry": num(d["entry"]), "stop": num(d["stop"]),
            "targets": [num(d["target"]), num(d["target2"]), num(d["target3"])],
            "reward_risk": num(d["reward_risk"]), "size_pct": num(d["size_pct"]),
            "invalidation": d["invalidation"], "psychology": d["psychology"], "rationale": d["rationale"],
            "factors": {k: (num(v)) for k, v in factors.items()},
            "outcome": {
                "result": outcome["result"], "pnl_frac": num(outcome["pnl"]),
                "mfe": num(outcome["mfe"]), "mae": num(outcome["mae"]),
                "bars_held": outcome["bars_held"],
                "resolved_at": str(outcome["resolved_at"]) if outcome["resolved_at"] else None,
            } if outcome["result"] else None,
        }
    except Exception:
        return None


def signal_exists(symbol: str, interval: str, as_of: str) -> bool:
    """True if a signal for this symbol/interval/bar is already logged (scanner dedupe)."""
    if not db.enabled():
        return False
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "select 1 from signals where symbol=%s and interval=%s and as_of=%s limit 1",
                (symbol, interval, as_of),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def has_active_signal(symbol: str, strategy: str = "flash") -> bool:
    """True if this symbol currently has an open (unresolved) signal in this strategy."""
    if not db.enabled():
        return False
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select 1 from signals s
                left join outcomes o on o.signal_id = s.id
                where s.symbol = %s and s.strategy = %s and o.id is null
                  and s.created_at > now() - interval '24 hours'
                limit 1
                """,
                (symbol, strategy),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def active_signals_count(strategy: str = "flash") -> dict:
    """Count of currently open (unresolved) signals by direction."""
    out = {"total": 0, "longs": 0, "shorts": 0}
    if not db.enabled():
        return out
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select count(*),
                       count(*) filter (where s.label like '%Buy%'),
                       count(*) filter (where s.label like '%Sell%')
                from signals s
                left join outcomes o on o.signal_id = s.id
                where s.strategy = %s and o.id is null
                  and s.created_at > now() - interval '24 hours'
                """,
                (strategy,),
            )
            row = cur.fetchone()
            if row:
                out["total"] = int(row[0] or 0)
                out["longs"] = int(row[1] or 0)
                out["shorts"] = int(row[2] or 0)
    except Exception:
        pass
    return out



def recent_signals(limit: int = 20, strategy: str = "all") -> list[dict]:
    """Recent signals joined with any resolved outcome (for an accuracy view)."""
    if not db.enabled():
        return []
    if strategy == "flash":
        strat_clause = "s.strategy = 'flash'"
    elif strategy == "core":
        strat_clause = "s.shadow = false and (s.strategy = 'core' or s.strategy is null)"
    else:  # "all"
        strat_clause = "(s.shadow = false or s.strategy = 'flash')"
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select s.id, s.symbol, s.market, s.interval, s.as_of, s.label, s.composite,
                       s.confidence, s.final_confidence, s.agreement, o.result, o.pnl,
                       coalesce(s.strategy, 'core') as strategy
                from signals s
                left join outcomes o on o.signal_id = s.id
                where {strat_clause}
                order by s.created_at desc
                limit %s
                """,
                (limit,),
            )
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []


def accuracy_stats(strategy: str = "core") -> dict:
    """Hit-rate + average P&L over resolved outcomes for core real-capital trades or flash paper trades."""
    if not db.enabled():
        return {"enabled": False}
    if strategy == "flash":
        strat_clause = "s.strategy = 'flash'"
    elif strategy == "all":
        strat_clause = "(s.shadow = false or s.strategy = 'flash')"
    else:  # "core"
        strat_clause = "s.shadow = false and (s.strategy = 'core' or s.strategy is null)"
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select count(*) as resolved,
                       count(*) filter (where o.pnl > 0) as wins,
                       avg(o.pnl) as avg_pnl
                from outcomes o join signals s on s.id = o.signal_id
                where o.pnl is not null and {strat_clause}
                """
            )
            resolved, wins, avg_pnl = cur.fetchone()
            resolved = resolved or 0
            return {
                "enabled": True,
                "strategy": strategy,
                "resolved": resolved,
                "wins": wins or 0,
                "hit_rate": round((wins or 0) / resolved, 4) if resolved else None,
                "avg_pnl": float(avg_pnl) if avg_pnl is not None else None,
            }
    except Exception:
        return {"enabled": True, "error": "query failed"}
