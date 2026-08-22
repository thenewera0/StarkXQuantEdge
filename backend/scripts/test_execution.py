"""Limit-order execution invariants.

Maker entry is worth +0.39pp per signal (measured over 14,047 signals, already net of every order
that never filled). The danger in implementing it is silent: if an unfilled order is treated as a
trade, the engine books ~21% of its signals as free entries at a price that never traded, and every
hit-rate and expectancy number downstream becomes fiction.

These tests pin the three things that must hold:
  * the resting price is on the correct SIDE and the risk geometry survives the shift
  * an order that never trades through its limit produces NO P&L, not a zero-P&L trade
  * holding time is counted from the FILL, not from the signal

    python -m scripts.test_execution
"""

from __future__ import annotations

import numpy as np

from app import resolver
from app.config import settings
from app.costs import round_trip_cost
from app.execution import fill_bar, limit_entry
from app.geometry import trade_levels

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"   ok {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"   FAIL {name} — {detail}")


print("=== 1. The resting order sits on the correct side ===")
lp = limit_entry(100.0, 2.0, "long", offset_atr=0.20, expiry_bars=2)
sp = limit_entry(100.0, 2.0, "short", offset_atr=0.20, expiry_bars=2)
check("a long rests BELOW the close", lp.limit_price < 100.0, f"got {lp.limit_price}")
check("a short rests ABOVE the close", sp.limit_price > 100.0, f"got {sp.limit_price}")
check("offset scales with ATR (0.20 x 2.0 = 0.40)",
      abs(abs(lp.limit_price - 100.0) - 0.40) < 1e-9, f"got {abs(lp.limit_price-100.0)}")
check("execution is flagged maker", lp.execution == "maker", lp.execution)

print("\n=== 2. Risk geometry survives the shift ===")
mkt = trade_levels(100.0, 2.0, "long", "4h", "weak_trend")
lim = trade_levels(100.0, 2.0, "long", "4h", "weak_trend", limit_offset_atr=0.20, limit_expiry_bars=2)
check("limit entry is better than the close", lim["entry"] < mkt["entry"],
      f"{lim['entry']} !< {mkt['entry']}")
check("stop distance is unchanged (the plan shifts whole)",
      abs((mkt["entry"] - mkt["stop"]) - (lim["entry"] - lim["stop"])) < 1e-6,
      f"market risk {mkt['entry']-mkt['stop']} vs limit risk {lim['entry']-lim['stop']}")
check("reward:risk is unchanged", abs(mkt["reward_risk"] - lim["reward_risk"]) < 0.02,
      f"{mkt['reward_risk']} vs {lim['reward_risk']}")
check("order_type is reported", lim["order_type"] == "limit" and mkt["order_type"] == "market",
      f"{lim['order_type']} / {mkt['order_type']}")
check("stop stays BELOW the limit entry for a long", lim["stop"] < lim["entry"], "inverted")

print("\n=== 3. Maker costs less than taker, and it is wired through ===")
t = round_trip_cost("crypto", "TIAUSDT", 0.01, "taker")
m = round_trip_cost("crypto", "TIAUSDT", 0.01, "maker")
check("maker is materially cheaper", m < t / 3, f"maker {m} vs taker {t}")
check("maker ignores ATR (a resting order crosses no spread)",
      round_trip_cost("crypto", "TIAUSDT", 0.10, "maker") == m, "maker cost scaled with ATR")
check("taker still scales with ATR",
      round_trip_cost("crypto", "TIAUSDT", 0.10, "taker") > t, "taker cost ignored ATR")

print("\n=== 4. fill_bar only fills when price TRADES THROUGH the limit ===")
highs = np.array([100.0, 100.5, 101.0, 102.0])
lows_touch = np.array([100.0, 99.5, 99.0, 98.0])     # dips to 99.5 on bar 1
lows_miss = np.array([100.0, 99.9, 99.95, 100.2])    # never reaches 99.6
plan = limit_entry(100.0, 2.0, "long", offset_atr=0.20, expiry_bars=2)   # limit 99.6
check("fills when the low trades through",
      fill_bar(highs, lows_touch, 0, plan, "long", 4) == 1,
      f"got {fill_bar(highs, lows_touch, 0, plan, 'long', 4)}")
check("does NOT fill when price never reaches it",
      fill_bar(highs, lows_miss, 0, plan, "long", 4) is None,
      "filled an order the market never traded through")
check("never fills on the signal bar itself",
      fill_bar(highs, np.array([99.0, 100.2, 100.3, 100.4]), 0, plan, "long", 4) != 0,
      "filled before the signal bar had closed")

print("\n=== 5. An unfilled order is NOT a trade (the fiction this prevents) ===")
import pandas as pd
future_miss = pd.DataFrame({"high": [100.5, 100.6, 101.0, 101.5],
                            "low": [99.9, 99.95, 100.1, 100.4],
                            "close": [100.2, 100.3, 100.7, 101.2]})
out = resolver._resolve_one("TIAUSDT", "crypto", "4h", "long",
                            entry=99.6, stop=97.2, target=103.9, atr_pct=0.02,
                            future=future_miss, max_hold=24)
check("an expired unfilled order resolves as 'unfilled'",
      out is not None and out.get("result") == "unfilled", f"got {out}")
check("...and carries NULL P&L, not zero",
      out is not None and out.get("pnl") is None,
      f"pnl={out.get('pnl') if out else None} — a zero would count as a losing trade")

future_fill = pd.DataFrame({"high": [100.5, 100.6, 104.5, 105.0],
                            "low": [99.5, 100.0, 100.1, 104.0],
                            "close": [100.2, 100.3, 104.2, 104.8]})
out2 = resolver._resolve_one("TIAUSDT", "crypto", "4h", "long",
                             entry=99.6, stop=97.2, target=103.9, atr_pct=0.02,
                             future=future_fill, max_hold=24)
check("a filled order resolves normally", out2 is not None and out2["result"] in ("target", "stop", "timeout"),
      f"got {out2}")
check("...with real P&L", out2 is not None and out2.get("pnl") is not None, "no pnl on a filled trade")

print("\n=== 6. Settings are the MEASURED optimum, not a guess ===")
check("offset is 0.20 ATR", abs(settings.limit_offset_atr - 0.20) < 1e-9,
      f"got {settings.limit_offset_atr} — re-run scripts.research_limit_orders before changing")
check("expiry is 2 bars", settings.limit_expiry_bars == 2, f"got {settings.limit_expiry_bars}")
check("a longer expiry would be a real change, not free",
      settings.limit_expiry_bars <= 6, "beyond 6 bars the measured edge decays")

print("\n=== 7. PARTIAL PROFIT BOOKING (the 17.3% capture-rate fix) ===")
# The live book captured only 17.3% of peak unrealised profit: 345 trades reached +526.8% of
# aggregate MFE and booked +91.0%. Taking half off at +0.20R measured +0.242pp/signal, and the
# curve is an inverted-U (peak 0.15-0.20R, falling either side) so it is a real optimum rather
# than a degenerate "exit immediately".
check("partial booking is enabled", settings.partial_book_enabled, "disabled")
check("books at the MEASURED peak (0.20R)", abs(settings.partial_book_at_r - 0.20) < 1e-9,
      f"got {settings.partial_book_at_r} — re-run scripts.research_exits before changing")
check("takes half off", abs(settings.partial_book_fraction - 0.5) < 1e-9,
      f"got {settings.partial_book_fraction}")

g = trade_levels(100.0, 2.0, "long", "4h", "weak_trend",
                 limit_offset_atr=0.20, limit_expiry_bars=2,
                 partial_book_at_r=0.20, partial_book_fraction=0.5)
risk = g["entry"] - g["stop"]
check("partial level sits between entry and target",
      g["entry"] < g["partial_target"] < g["target"],
      f"entry {g['entry']} partial {g['partial_target']} target {g['target']}")
check("partial level is exactly 0.20R above entry",
      abs((g["partial_target"] - g["entry"]) / risk - 0.20) < 0.01,
      f"got {(g['partial_target']-g['entry'])/risk:.3f}R")

# THE POINT OF THE WHOLE CHANGE: a trade that shows profit then reverses must lose LESS.
path = pd.DataFrame({"high": [100.0, 100.6, 100.2, 99.0],
                     "low": [99.8, 100.0, 98.0, 97.0],
                     "close": [99.9, 100.5, 98.5, 97.4]})
with_p = resolver._resolve_one("BTCUSDT", "crypto", "4h", "long", 100.0, 97.6, 104.32, 0.02, path, 24)
settings.partial_book_enabled = False
without = resolver._resolve_one("BTCUSDT", "crypto", "4h", "long", 100.0, 97.6, 104.32, 0.02, path, 24)
settings.partial_book_enabled = True
check("a loser that showed profit loses LESS with partial booking",
      with_p["pnl"] > without["pnl"], f"with {with_p['pnl']} vs without {without['pnl']}")
check("the booked fraction is reported", with_p.get("partial_booked") == 0.5,
      f"got {with_p.get('partial_booked')}")

# And the honest other side: it MUST cost something on a clean winner, or the model is wrong.
runup = pd.DataFrame({"high": [100.1, 101.0, 104.5, 105.0],
                      "low": [99.9, 100.2, 101.0, 104.0],
                      "close": [100.0, 100.9, 104.4, 104.9]})
w_p = resolver._resolve_one("BTCUSDT", "crypto", "4h", "long", 100.0, 97.6, 104.32, 0.02, runup, 24)
settings.partial_book_enabled = False
w_n = resolver._resolve_one("BTCUSDT", "crypto", "4h", "long", 100.0, 97.6, 104.32, 0.02, runup, 24)
settings.partial_book_enabled = True
check("...and it COSTS something on a clean winner (the real trade-off)",
      w_p["pnl"] < w_n["pnl"],
      "partial booking looked free on a winner — the model is wrong somewhere")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("ALL EXECUTION TESTS PASSED")
