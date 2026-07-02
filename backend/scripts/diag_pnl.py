"""Diagnose the P&L numbers: duplicates, realized-sum integrity, timeline, learning readiness."""

from __future__ import annotations

from app import db

SIZE = 1000.0


def main() -> None:
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("select count(*) from signals")
        print("signals:", cur.fetchone()[0])
        cur.execute("select count(*), count(distinct signal_id) from outcomes")
        total, distinct = cur.fetchone()
        print(f"outcomes rows: {total}  distinct signal_id: {distinct}  DUPLICATES: {total - distinct}")

        cur.execute("select coalesce(sum(pnl),0), count(*), count(*) filter (where pnl>0) from outcomes")
        s, n, w = cur.fetchone()
        print(f"realized: sum(pnl_frac)={float(s):.5f}  -> ${float(s)*SIZE:.2f}  over {n} trades  wins={w} hit={w/n:.1%}" if n else "no outcomes")

        print("\n-- realized P&L by day (does the cumulative make sense?) --")
        cur.execute(
            """
            select date_trunc('day', resolved_at) d, count(*), round(sum(pnl)::numeric,5) pnl
            from outcomes where resolved_at is not null group by d order by d
            """
        )
        cum = 0.0
        for d, c, pnl in cur.fetchall():
            cum += float(pnl) * SIZE
            print(f"  {str(d)[:10]}: {c:>3} trades  day ${float(pnl)*SIZE:>8.2f}  cumulative ${cum:>9.2f}")

        print("\n-- per-regime resolved (learning needs >=40 per regime) --")
        cur.execute(
            """
            select coalesce(s.regime,'?') r, count(*), count(*) filter (where o.pnl>0) w,
                   round(sum(o.pnl)::numeric,5)
            from outcomes o join signals s on s.id=o.signal_id
            group by r order by count(*) desc
            """
        )
        for r, c, w, pnl in cur.fetchall():
            print(f"  {r:<14} {c:>3} trades  {w:>3}W  hit {w/c:.0%}  ${float(pnl)*SIZE:>8.2f}")

        print("\n-- possible artificial/test rows (rationale mentions test) --")
        cur.execute("select count(*) from signals where rationale ilike '%test%'")
        print("  test-tagged signals:", cur.fetchone()[0])


if __name__ == "__main__":
    main()
