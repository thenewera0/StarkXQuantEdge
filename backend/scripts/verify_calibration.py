"""Verify the segment-conditioned calibration fix is actually improving trade flow.

Run: python -m scripts.verify_calibration

The fix (commit 496d804) stopped pooling crypto/long (70% hit) with crypto/short (4%) and forex,
which had been pricing genuinely good longs at 7-20% win probability and driving their EV negative.

This measures whether that translated into (a) more good trades reaching the gate, and (b) stored
probabilities that actually match realized outcomes. Run it every couple of days.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app import db

FIX_UTC = "2026-07-28 00:00:00+00"   # calibration fix deployed


def main() -> None:
    if not db.enabled():
        print("DB not configured"); return
    with db.get_conn() as conn, conn.cursor() as cur:
        print("=" * 72)
        print("CALIBRATION FIX VERIFICATION")
        print("=" * 72)

        # 1. Trade FLOW: are more signals actually being emitted?
        print("\n1. SIGNAL FLOW (live core, per day)")
        cur.execute("""
            select date_trunc('day', created_at)::date d, count(*)
            from signals
            where not shadow and coalesce(strategy,'core')='core' and label <> 'Neutral'
              and created_at > now() - interval '14 days'
            group by d order by d
        """)
        rows = cur.fetchall()
        for d, c in rows:
            marker = "  <- fix deployed" if str(d) >= FIX_UTC[:10] else ""
            print(f"   {d}  {'#' * min(c, 40)} {c}{marker}")
        if not rows:
            print("   (no actionable signals logged in the window)")

        # 2. Are stored win_probs now matching reality?
        print("\n2. CALIBRATION ACCURACY (resolved trades that carry a stored win_prob)")
        cur.execute("""
            select case when s.created_at >= %s then 'after fix' else 'before fix' end era,
                   count(*), round(avg(s.win_prob)::numeric,3) predicted,
                   round(avg(case when o.pnl>0 then 1.0 else 0.0 end)::numeric,3) actual
            from outcomes o join signals s on s.id=o.signal_id
            where not s.shadow and s.win_prob is not null
            group by era order by era
        """, (FIX_UTC,))
        for era, n, pred, act in cur.fetchall():
            gap = float(act) - float(pred)
            verdict = "well calibrated" if abs(gap) < 0.12 else ("UNDER-predicting" if gap > 0 else "OVER-predicting")
            print(f"   {era:11} n={n:4} predicted={float(pred):.3f} actual={float(act):.3f} "
                  f"gap={gap:+.3f}  ({verdict})")

        # 3. Segment sanity: is crypto/long now priced near its true hit rate?
        print("\n3. SEGMENT HIT RATES (what calibration must reproduce)")
        cur.execute("""
            select case when coalesce(s.market,'crypto')='crypto' then 'crypto' else 'forex' end mkt,
                   case when s.label in ('Buy','Strong Buy') then 'long' else 'short' end dir,
                   count(*), round(avg(case when o.pnl>0 then 1.0 else 0.0 end)::numeric,3)
            from outcomes o join signals s on s.id=o.signal_id
            where not s.shadow and o.pnl is not null group by 1,2 order by 4 desc
        """)
        for mkt, d, n, hit in cur.fetchall():
            print(f"   {mkt:6}/{d:5} n={n:4} hit={float(hit):.3f}")

        # 4. Did P&L actually improve after the fix?
        print("\n4. REALIZED P&L SINCE THE FIX")
        cur.execute("""
            select count(*), count(*) filter (where o.pnl>0), round(sum(o.pnl)::numeric*1000,2)
            from outcomes o join signals s on s.id=o.signal_id
            where not s.shadow and coalesce(s.strategy,'core')='core' and s.created_at >= %s
        """, (FIX_UTC,))
        n, w, pnl = cur.fetchone()
        if n:
            print(f"   {n} trades, {w}W ({100*w/n:.0f}%), {float(pnl or 0):+.2f}$")
        else:
            print("   no post-fix trades have resolved yet — re-run in a day or two")

    print("\n" + "=" * 72)
    print("WHAT GOOD LOOKS LIKE: more signals/day than the pre-fix baseline, predicted vs actual")
    print("gap inside +/-0.12, and post-fix P&L trending positive. If flow rises but P&L falls,")
    print("the fix over-corrected and min_ev_r should be raised.")


if __name__ == "__main__":
    main()
