"""Cross-panel data consistency — every dashboard must tell the SAME story.

Written after the dashboard was caught contradicting itself on 2026-08-05: the Risk panel said
2 open positions, Running Trades showed 13, and Floating P&L showed $0.00 against rows that
clearly had P&L. Three separate causes, all of which these tests now pin down:

  * performance._last_price() still routed non-crypto through Twelve Data (keyed, 800/day) after
    the scanner had started opening forex/commodity/index/rates positions. It returned None for
    every one of them.
  * live_trades() then SILENTLY DROPPED any position it could not price, so the count came from
    one set of rows and the P&L from another.
  * Flash paper trades (written with shadow=true) were folded into "open positions" while the
    floating P&L deliberately excluded them — a headline that could never add up.

    python -m scripts.test_consistency
"""

from __future__ import annotations

from app import db, performance, scanner

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"   ok {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"   FAIL {name} — {detail}")


print("=== 1. Every asset class the scanner can open must be priceable ===")
# If this fails, positions in that class become invisible on the dashboard.
for sym, mkt, iv in (("BTCUSDT", "crypto", "1h"), ("EUR/USD", "forex", "4h"),
                     ("XAU/USD", "commodities", "4h"), ("SPX", "indices", "1d"),
                     ("UST20+", "rates", "1d")):
    px = performance._last_price(sym, mkt, iv)
    check(f"{mkt:12} {sym:9} has a live price", px is not None and px > 0, f"got {px}")

print("\n=== 2. live_trades() must not drop any open position ===")
lt = performance.live_trades()
rows = lt.get("trades") or []
if db.enabled():
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """select count(*), count(*) filter (where not shadow)
               from signals s
               where not exists (select 1 from outcomes o where o.signal_id = s.id)
                 and s.entry is not null and s.label <> 'Neutral'
                 and (s.shadow = false or coalesce(s.strategy,'core') = 'flash')"""
        )
        db_all, db_real = cur.fetchone()
    check("every open row is returned (none silently dropped)",
          len(rows) == int(db_all), f"db says {db_all}, live_trades returned {len(rows)}")
    check("REAL count matches the database",
          lt.get("count") == int(db_real), f"db says {db_real}, payload says {lt.get('count')}")

print("\n=== 3. Real and paper are separated and never conflated ===")
real = [t for t in rows if not t["paper"]]
paper = [t for t in rows if t["paper"]]
check("count == number of real rows", lt.get("count") == len(real),
      f"count={lt.get('count')} real rows={len(real)}")
check("paper_count == number of paper rows", lt.get("paper_count") == len(paper),
      f"paper_count={lt.get('paper_count')} paper rows={len(paper)}")
check("real and paper partition the rows", len(real) + len(paper) == len(rows),
      "a row is neither real nor paper")
check("no paper row is counted as real", all(t["paper"] is False for t in real), "leak")
check("flash rows are all flagged paper while the bot is on paper",
      all(t["paper"] for t in rows if t["strategy"] == "flash"),
      "a flash trade is being presented as real capital")

print("\n=== 4. Headline P&L is the sum of the rows it claims to describe ===")
# The exact bug: a floating P&L that excluded rows the count included.
expect_real = round(sum(t["pnl_usd"] or 0.0 for t in real if t["priced"]), 2)
check("open_pnl_usd == sum of REAL priced rows",
      abs((lt.get("open_pnl_usd") or 0.0) - expect_real) < 0.02,
      f"payload={lt.get('open_pnl_usd')} rows sum to {expect_real}")
expect_paper = round(sum(t["pnl_usd"] or 0.0 for t in paper if t["priced"]), 2)
check("paper_pnl_usd == sum of PAPER priced rows",
      abs((lt.get("paper_pnl_usd") or 0.0) - expect_paper) < 0.02,
      f"payload={lt.get('paper_pnl_usd')} rows sum to {expect_paper}")
check("a zero P&L is only reported when there is genuinely nothing real open",
      not (lt.get("open_pnl_usd") == 0.0 and lt.get("count", 0) > 0
           and any(t["priced"] for t in real)),
      "real positions are priced but floating P&L reads zero")

print("\n=== 5. Unpriced positions are surfaced, never hidden ===")
unpriced_rows = [t for t in rows if not t["priced"]]
check("unpriced counter matches the rows", lt.get("unpriced") == len(unpriced_rows),
      f"unpriced={lt.get('unpriced')} rows={len(unpriced_rows)}")
check("unpriced rows carry no fabricated P&L",
      all(t["pnl_usd"] is None and t["pnl_pct"] is None for t in unpriced_rows),
      "an unpriced position reported a P&L number")

print("\n=== 6. Risk panel and Live Trades agree on what is open ===")
# These read the database through different queries. When they disagree, the operator cannot
# tell which number to believe — which is exactly what was reported.
book = scanner._book_state(force=True)
check("risk open count == live_trades real count",
      sum(book["per_market"].values()) == lt.get("count"),
      f"risk says {sum(book['per_market'].values())}, live trades says {lt.get('count')}")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("ALL CONSISTENCY TESTS PASSED")
