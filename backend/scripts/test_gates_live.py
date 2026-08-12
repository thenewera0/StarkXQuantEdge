"""Every performance gate must be able to REACH its own sample threshold.

The direction gate was dead code from the day it shipped until 2026-08-07. It required 10 resolved
trades inside a 2-DAY window. The engine resolves ~7.6 core trades per 2 days across BOTH
directions and roughly 1 short, so the threshold was unreachable by construction: the gate silently
fell back to "allow everything" and never fired once.

What it failed to catch: crypto SHORTS went 2 wins in 45 trades (4.4% hit, -1.94%/trade) while
longs ran 59.5% and +1.51%. The short book erased 44% of what the long book earned.

A gate that cannot reach its own sample is WORSE than no gate, because it reads as protection that
is not there. These tests make that failure mode visible: for each gate, compare the trades its
window can realistically contain against the sample it demands.

    python -m scripts.test_gates_live
"""

from __future__ import annotations

from app import db, learning
from app.config import settings

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"   ok {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"   FAIL {name} — {detail}")


def resolved_in(days: int, extra: str = "") -> int:
    if not db.enabled():
        return 0
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""select count(*) from outcomes o join signals s on s.id = o.signal_id
                where s.strategy = 'core' and not s.shadow and o.pnl is not null
                  and o.resolved_at > now() - interval '{int(days)} days' {extra}"""
        )
        return int(cur.fetchone()[0])


print("=== 1. Each gate's window can actually contain its required sample ===")
rate90 = resolved_in(90) / 90.0 if db.enabled() else 0.0
print(f"   (measured throughput: {rate90:.1f} resolved core trades per day)\n")

GATES = [
    ("regime", settings.regime_perf_min_sample, settings.regime_perf_window_days, ""),
    # The direction gate splits the flow in two, so it sees roughly HALF the throughput per
    # direction — the reason a whole-flow estimate hid the problem for so long.
    ("direction", settings.direction_perf_min_sample, settings.direction_perf_window_days,
     "and s.label like '%Sell%'"),
    ("symbol", settings.symbol_perf_min_sample, settings.symbol_perf_window_days, ""),
]
for name, min_sample, window, extra in GATES:
    actual = resolved_in(window, extra)
    expected = (resolved_in(90, extra) / 90.0) * window
    check(f"{name:10} can reach {min_sample} trades in {window}d",
          expected >= min_sample,
          f"window realistically holds ~{expected:.1f} trades, needs {min_sample} — gate is inert")
    print(f"      (currently in window: {actual})")

print("\n=== 2. The direction gate is actually LIVE, not silently permissive ===")
if db.enabled():
    allowed = learning.tradeable_directions(
        settings.direction_perf_min_sample, settings.direction_perf_window_days)
    check("gate returns a decision", isinstance(allowed, set) and len(allowed) >= 1,
          f"got {allowed}")
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""select count(*), count(*) filter (where o.pnl > 0), avg(o.pnl)
                       from outcomes o join signals s on s.id = o.signal_id
                       where s.strategy='core' and not s.shadow and o.pnl is not null
                         and coalesce(s.market,'crypto')='crypto' and s.label like '%Sell%'""")
        n, w, avg = cur.fetchone()
    if n and n >= 20:
        hit = w / n
        losing = float(avg) < 0 and hit < 0.20
        print(f"      shorts on record: n={n} hit={hit*100:.1f}% per-trade={float(avg)*100:+.3f}%")
        # If a direction is demonstrably losing on a real sample, the gate must have excluded it.
        check("a demonstrably losing direction is excluded",
              (not losing) or ("short" not in allowed),
              f"shorts are {hit*100:.1f}% over {n} trades and the gate still allows them")

print("\n=== 3. Gate windows are not so long that they stop reacting ===")
for name, _min_sample, window, _extra in GATES:
    check(f"{name:10} window <= 120d", window <= 120,
          f"{window}d is too slow to respond to a regime change")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("ALL LIVE-GATE TESTS PASSED")
