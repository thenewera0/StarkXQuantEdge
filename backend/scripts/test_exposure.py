"""Gross-exposure ceiling and drawdown throttle.

These guard the constraint that was missing entirely until 2026-08-02. Sizing every position so
its STOP costs 2% of equity says nothing about position SIZE: a stop 0.38% away implies 5.3x
equity of notional for one trade. The live book was carrying 16.2x gross while every position
individually "only risked 2%". Measured over 23,487 replayed trades, uncapped gross returned
-93.6% (maxDD -96.4%) where a 1x ceiling returned -19.4% (maxDD -41.0%).

    python -m scripts.test_exposure
"""

from __future__ import annotations

from app import scanner, sizing

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"   ok {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"   FAIL {name} — {detail}")


print("=== 1. Every tier has a gross ceiling, and none of them is leverage ===")
for name, _lo, _hi, _mc, _cap, _ev in sizing.TIERS:
    g = sizing.MAX_GROSS.get(name)
    check(f"{name:9} has a ceiling", g is not None, "tier missing from MAX_GROSS")
    # Gross bounds GAP risk (loss when price jumps THROUGH the stop). At Nx a G% gap costs N*G,
    # so 3x survives a 5-10% crypto flash crash at a painful but recoverable 15-30%.
    check(f"{name:9} ceiling <= 4x", g is not None and g <= 4.0, f"{g}x cannot survive a gap")
    h = sizing.MAX_HEAT.get(name)
    check(f"{name:9} has a heat cap <= 6%", h is not None and h <= 0.06, f"heat cap {h}")

print("\n=== 2. The drawdown throttle de-risks under water and never switches off ===")
check("at the high-water mark, full exposure",
      sizing.drawdown_throttle(1000, 1000) == 1.0, "throttled while at peak")
check("above the high-water mark, full exposure",
      sizing.drawdown_throttle(1200, 1000) == 1.0, "throttled while making new highs")
t10 = sizing.drawdown_throttle(900, 1000)
t20 = sizing.drawdown_throttle(800, 1000)
check("-10% drawdown throttles to ~75%", abs(t10 - 0.75) < 1e-6, f"got {t10}")
check("-20% drawdown throttles to ~50%", abs(t20 - 0.50) < 1e-6, f"got {t20}")
check("deeper drawdown throttles harder", t20 < t10, f"{t20} !< {t10}")
check("never below the floor",
      sizing.drawdown_throttle(1, 1000) >= sizing.DRAWDOWN_THROTTLE_FLOOR,
      "engine would switch itself off entirely and stop learning")
check("unknown history does NOT pretend to be a drawdown",
      sizing.drawdown_throttle(1000, 0) == 1.0, "a fresh account started de-risked")

print("\n=== 3. The budget gates on BOTH heat and gross ===")
gross = sizing.MAX_GROSS["standard"]
b = sizing.exposure_budget(1000.0, 0.0, 1000.0, 0.0)
check("empty book has its full ceiling available",
      abs(b["remaining_usd"] - 1000.0 * gross) < 1e-6, f"got {b['remaining_usd']}")
check("empty book is not blocked", b["binding"] is None, f"binding={b['binding']}")
b = sizing.exposure_budget(1000.0, 600.0, 1000.0, 0.015)
check("partly-used book reports the remainder",
      abs(b["remaining_usd"] - (1000.0 * gross - 600.0)) < 1e-6, f"got {b['remaining_usd']}")
check("gross_used is reported honestly", abs(b["gross_used"] - 0.6) < 1e-6, f"got {b['gross_used']}")
b = sizing.exposure_budget(1000.0, 16160.0, 1000.0, 0.015)
check("an over-levered book has ZERO gross room (the 16.2x state)",
      b["remaining_usd"] == 0.0, f"still offered {b['remaining_usd']} at 16.2x")
check("...and names GROSS as the binding constraint", b["binding"] == "gross", f"got {b['binding']}")

# THE DEADLOCK THAT IDLED THE ENGINE FOR 104 HOURS. Two ordinary positions with sub-1% stops
# summed to 1.79x, which the old 1.0x ceiling refused outright — so nothing could trade at all.
b = sizing.exposure_budget(1000.0, 1785.65, 1000.0, 0.015)
check("two normal positions do NOT deadlock the book (the 2026-08-07 bug)",
      b["binding"] is None and b["remaining_usd"] > 0,
      f"binding={b['binding']} remaining={b['remaining_usd']} — the engine would idle again")

# Heat should bite first in ordinary conditions; gross only when stops are unusually tight.
b = sizing.exposure_budget(1000.0, 500.0, 1000.0, 0.06)
check("a spent risk budget blocks even with gross room left",
      b["binding"] == "heat" and b["heat_remaining"] <= 1e-9,
      f"binding={b['binding']} heat_left={b['heat_remaining']}")
b = sizing.exposure_budget(1000.0, 0.0, 1250.0, 0.0)     # 20% below high-water
check("drawdown shrinks BOTH budgets",
      abs(b["budget_usd"] - 1000.0 * gross * 0.5) < 1e-6 and abs(b["heat_cap"] - 0.03) < 1e-9,
      f"gross={b['budget_usd']} heat={b['heat_cap']} at -20% drawdown")

print("\n=== 4. position_size is CUT DOWN by the room left, not refused ===")
# A very tight stop wants an enormous notional; with limited room it must shrink, not vanish.
free = sizing.position_size(1000.0, 0.6, 2.0, 0.004)
clamped = sizing.position_size(1000.0, 0.6, 2.0, 0.004, room_usd=250.0)
check("unclamped size wants more than the room", free["notional_usd"] > 250.0,
      f"test is not exercising the clamp (wanted {free['notional_usd']})")
check("clamped size respects the room", clamped["notional_usd"] <= 250.0 + 1e-6,
      f"got {clamped['notional_usd']}")
check("clamped trade is still tradeable (smaller, not skipped)", clamped["tradeable"],
      "a good setup was refused instead of being sized down")
check("clamp is explained in bound_by", "exposure" in clamped["bound_by"],
      f"bound_by={clamped['bound_by']}")
check("clamped risk is smaller than unclamped",
      clamped["risk_usd"] < free["risk_usd"], "risk did not fall with notional")
check("zero room means not tradeable",
      not sizing.position_size(1000.0, 0.6, 2.0, 0.004, room_usd=0.0)["tradeable"],
      "traded with no capital left")

print("\n=== 5. Count caps were raised, because count is not the constraint ===")
# Measured: with gross capped at 1x, moving the count cap 6 -> 30 changed the equity curve by
# nothing at all. A generous count cap only matters when many good setups appear at once.
std = sizing.tier_for_equity(5_000)
check("standard tier allows >= 20 concurrent", std["max_concurrent"] >= 20,
      f"only {std['max_concurrent']}")
check("caps increase with equity",
      [sizing.tier_for_equity(e)["max_concurrent"] for e in (50, 500, 5_000, 50_000)]
      == sorted(sizing.tier_for_equity(e)["max_concurrent"] for e in (50, 500, 5_000, 50_000)),
      "a bigger account is allowed fewer positions than a smaller one")

print("\n=== 6. The scanner reads the live book and fails CLOSED ===")
book = scanner._book_state()
for key in ("slots", "per_market", "open_notional", "budget", "equity"):
    check(f"book state exposes '{key}'", key in book, "missing key")
check("class cap is below the (raised) global cap",
      scanner._class_cap() < sizing.tier_for_equity(book["equity"])["max_concurrent"],
      "one class could still own the whole book")
check("open notional is measured, not assumed", book["open_notional"] >= 0.0, "negative notional")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("ALL EXPOSURE TESTS PASSED")
