"""Universe + breadth invariants.

Guards the things that would silently corrupt every downstream number if they broke:
the allocatable/context-only split, provider routing, close-time bar stamping, and the
per-asset-class concurrency cap.

    python -m scripts.test_universe
"""

from __future__ import annotations

import pandas as pd

from app import scanner, universe

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"   ok {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"   FAIL {name} — {detail}")


print("=== 1. Catalog covers every asset class with real breadth ===")
counts = universe.counts()
for cat, minimum in (("crypto", 40), ("forex", 60), ("commodities", 25),
                     ("indices", 25), ("rates", 14)):
    got = counts["by_category"].get(cat, {}).get("total", 0)
    check(f"{cat} has >= {minimum} instruments", got >= minimum, f"only {got}")
check("total universe >= 250 instruments", counts["total"] >= 250, f"only {counts['total']}")

print("\n=== 2. The allocatable/context-only split (stops fake backtests) ===")
# A yield index is not ownable. If this regresses, a momentum ranker "buys" ^IRX going 0.07 -> 3.68
# and reports a fabricated +5,314%, which is exactly what happened before the flag existed.
for yld in ("US10Y/YLD", "US30Y/YLD", "US13W/YLD", "US5Y/YLD"):
    e = universe.resolve(yld)
    check(f"{yld} is barred from allocation", e is not None and not e["allocatable"],
          "yield index is marked allocatable")
check("VIX is barred from allocation",
      not universe.resolve("VIX")["allocatable"], "spot VIX is not investable")
# Non-G10 FX: spot trend is the interest differential in disguise.
for exotic in ("USD/ARS", "USD/TRY", "USD/NGN", "USD/EGP"):
    e = universe.resolve(exotic)
    check(f"{exotic} is barred from allocation", e is not None and not e["allocatable"],
          "high-carry FX marked allocatable")
for g10 in ("EUR/USD", "USD/JPY", "GBP/JPY", "AUD/CAD"):
    check(f"{g10} IS allocatable", universe.resolve(g10)["allocatable"], "G10 pair was excluded")
# The tradable expressions of rates must survive — barring the yields must not bar the bonds.
for bond in ("US10Y", "UST20+", "HY"):
    check(f"{bond} IS allocatable", universe.resolve(bond)["allocatable"], "bond instrument excluded")

alloc = universe.catalog(allocatable_only=True)
check("allocatable_only actually filters",
      all(c["allocatable"] for c in alloc) and len(alloc) < counts["total"],
      "filter let a context-only series through")
check("every non-allocatable entry explains itself",
      all(c["note"] for c in universe.catalog() if not c["allocatable"]),
      "an exclusion has no reason attached")

print("\n=== 3. Provider routing returns a usable frame per asset class ===")
for sym, cat in (("BTCUSDT", "crypto"), ("EUR/USD", "forex"), ("XAU/USD", "commodities"),
                 ("SPX", "indices"), ("UST20+", "rates")):
    try:
        df = universe.fetch(sym, "1d", 300)
        ok = (len(df) >= 250
              and list(df.columns[:5]) == ["open", "high", "low", "close", "volume"]
              and float(df["close"].iloc[-1]) > 0
              and isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None)
        check(f"{cat:12} {sym:9} fetches OHLCV", ok, f"bars={len(df)} cols={list(df.columns)}")
        # Bars must be stamped at CLOSE, like Binance. A bar stamped at open reads one bar into
        # the future in every backtest.
        check(f"{cat:12} {sym:9} index is sorted & unique",
              df.index.is_monotonic_increasing and df.index.is_unique, "index out of order")
        check(f"{cat:12} {sym:9} OHLC is coherent",
              bool(((df["high"] >= df["low"]) & (df["high"] >= df["close"])
                    & (df["low"] <= df["close"])).all()), "high/low/close inconsistent")
    except Exception as exc:  # noqa: BLE001
        check(f"{cat:12} {sym:9} fetches OHLCV", False, f"{type(exc).__name__}: {exc}")

check("unknown symbols raise rather than guess",
      universe.resolve("NOT/AREAL/THING") is None, "resolved a nonsense symbol")

print("\n=== 4. Liquidity floors are ordered by holding period ===")
check("flash floor > scan floor > hold floor",
      universe.MIN_VOLUME_FLASH > universe.MIN_VOLUME_SCAN > universe.MIN_VOLUME_HOLD,
      "a faster strategy is allowed into thinner books than a slower one")

print("\n=== 5. Scanner sweeps several classes, interleaved ===")
sweep = scanner.scan_universe()
check("sweep spans >= 4 asset classes", len(sweep) >= 4, f"only {list(sweep)}")
check("sweep is materially wider than the old 28 crypto pairs",
      sum(len(v) for v in sweep.values()) >= 100,
      f"only {sum(len(v) for v in sweep.values())} symbols")
check("non-crypto classes skip the 1h bar",
      all("1h" not in scanner.SCAN_INTERVALS.get(m, []) for m in sweep if m != "crypto"),
      "an hourly bar on a market that closes overnight spans a session gap")
# Forex was removed from the scanner on 2026-08-05 after failing probation on the live record:
# 161 resolved trades, 26.7% hit, -0.105%/trade, against crypto's +0.648% over the same window.
# Asserting the exclusion rather than the old "restricted to G10" rule, which now passes
# vacuously on an empty list and would therefore never catch a regression.
check("forex is excluded from the scanner (failed probation on live P&L)",
      not sweep.get("forex"), f"forex is back in the sweep with {len(sweep.get('forex', []))} pairs")
check("any forex that IS swept stays inside the G10 list",
      all(s in scanner._FX_PROBATION for s in sweep.get("forex", [])),
      "an exotic pair reached the scanner")
check("forex remains available outside the scanner (analysis + rebalancing)",
      len(universe.catalog(["forex"], allocatable_only=True)) > 0,
      "forex was removed from the universe entirely, not just from the scanner")

print("\n=== 6. Per-class cap reallocates risk without increasing it ===")
cap = scanner._class_cap()
from app import sizing
from app.config import settings
total_cap = sizing.tier_for_equity(settings.account_equity_usd)["max_concurrent"]
check("class cap is at most half the book", cap <= (total_cap + 1) // 2,
      f"class cap {cap} vs total {total_cap}")
check("class cap still permits at least one position", cap >= 1, f"cap is {cap}")
check("class cap is strictly below the global cap (breadth is forced)",
      cap < total_cap or total_cap == 1, f"class cap {cap} == total {total_cap}")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("ALL UNIVERSE TESTS PASSED")
