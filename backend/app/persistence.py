"""Write signals, factor scores, and outcomes to Postgres. All writes are best-effort:

a database problem must never break a signal response. Every function returns gracefully (None /
False) when persistence is disabled or errors, and logs nothing sensitive.
"""

from __future__ import annotations

from . import db


def log_decision(sig: dict) -> int | None:
    """Persist a /decision (or /explain) result + its factor scores. Returns the new signal id."""
    if not db.enabled():
        return None

    cats = sig.get("categories", {})
    levels = sig.get("levels", {})
    explanation = sig.get("explanation") or {}
    final = sig.get("final") or {}
    debate = sig.get("debate") or {}

    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into signals
                  (symbol, market, interval, as_of, label, composite, confidence, regime,
                   price, atr, rationale, entry, stop, target,
                   agreement, conviction, final_confidence, debate_source)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                returning id
                """,
                (
                    sig.get("symbol"), sig.get("market"), sig.get("interval"), sig.get("as_of"),
                    sig.get("label"), sig.get("composite"), sig.get("confidence"), sig.get("regime"),
                    sig.get("price"), sig.get("atr"), explanation.get("rationale"),
                    levels.get("entry"), levels.get("stop"), levels.get("target"),
                    final.get("agreement"), final.get("conviction"), final.get("final_confidence"),
                    debate.get("source"),
                ),
            )
            signal_id = cur.fetchone()[0]
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
) -> bool:
    """Label a stored signal with what actually happened. The fuel for the learning loop."""
    if not db.enabled():
        return False
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into outcomes (signal_id, resolved_at, result, pnl, mfe, mae, bars_held)
                values (%s, now(), %s, %s, %s, %s, %s)
                """,
                (signal_id, result, pnl, mfe, mae, bars_held),
            )
            conn.commit()
            return True
    except Exception:
        return False


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


def recent_signals(limit: int = 20) -> list[dict]:
    """Recent signals joined with any resolved outcome (for an accuracy view)."""
    if not db.enabled():
        return []
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select s.id, s.symbol, s.market, s.interval, s.as_of, s.label, s.composite,
                       s.confidence, s.final_confidence, s.agreement, o.result, o.pnl
                from signals s
                left join outcomes o on o.signal_id = s.id
                order by s.created_at desc
                limit %s
                """,
                (limit,),
            )
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []


def accuracy_stats() -> dict:
    """Hit-rate + average P&L over resolved outcomes (the learning-loop scoreboard)."""
    if not db.enabled():
        return {"enabled": False}
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select count(*) as resolved,
                       count(*) filter (where result = 'target') as wins,
                       avg(pnl) as avg_pnl
                from outcomes
                where result is not null
                """
            )
            resolved, wins, avg_pnl = cur.fetchone()
            resolved = resolved or 0
            return {
                "enabled": True,
                "resolved": resolved,
                "wins": wins or 0,
                "hit_rate": round((wins or 0) / resolved, 4) if resolved else None,
                "avg_pnl": float(avg_pnl) if avg_pnl is not None else None,
            }
    except Exception:
        return {"enabled": True, "error": "query failed"}
