"""Tests for the triangular-arb detector (Blueprint v2 §6.2). Run: python -m scripts.test_p3_tri"""
from __future__ import annotations

import math
import unittest.mock as m

from app import arb

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

print("== Bellman-Ford negative cycle ==")
# No arbitrage: rates all 1.0 -> weights 0 -> no negative cycle.
nodes = ["A", "B", "C"]
noedge = [("A", "B", 0.0), ("B", "C", 0.0), ("C", "A", 0.0)]
check("no negative cycle when rates break even", arb.bellman_ford_neg_cycle(nodes, noedge) is None)

# Arbitrage: A->B->C->A multiplies to 1.05 -> weights = -log(rate), cycle sum < 0.
rate = {("A", "B"): 1.0, ("B", "C"): 1.0, ("C", "A"): 1.05}
edges = [(a, b, -math.log(r)) for (a, b), r in rate.items()]
cyc = arb.bellman_ford_neg_cycle(nodes, edges)
check("finds a negative cycle when arb exists", cyc is not None)
net = arb._cycle_net(cyc, rate) if cyc else None
check("cycle net ~ +5%", net is not None and abs(net - 0.05) < 1e-6)

print("== _build_edges from tickers ==")
# ETH/BTC and the two USD legs priced so the loop USDT->BTC->ETH->USDT is break-even-ish.
tickers = {
    "BTCUSDT": {"bid": 60000.0, "ask": 60000.0},
    "ETHUSDT": {"bid": 3000.0, "ask": 3000.0},
    "ETHBTC":  {"bid": 0.05, "ask": 0.05},   # 3000/60000 = 0.05 -> perfectly consistent (no arb)
}
nodes2, edges2, rate2 = arb._build_edges(tickers, fee=0.001)
check("edges built for both directions", ("USDT" in nodes2 and "BTC" in nodes2 and "ETH" in nodes2))
check("consistent prices + fees -> no arb cycle", arb.bellman_ford_neg_cycle(nodes2, edges2) is None)

# Now mis-price ETHBTC so a cycle profits (ETHBTC cheap: buy ETH with BTC cheaply).
tickers["ETHBTC"] = {"bid": 0.056, "ask": 0.056}   # ETH worth 0.056 BTC vs 0.05 fair -> arb
nodes3, edges3, rate3 = arb._build_edges(tickers, fee=0.001)
cyc3 = arb.bellman_ford_neg_cycle(nodes3, edges3)
check("mispriced cross -> arb cycle found", cyc3 is not None)
net3 = arb._cycle_net(cyc3, rate3) if cyc3 else None
check("mispriced cycle net > 0 after fees", net3 is not None and net3 > 0)

print("== triangular_scan (mocked tickers) ==")
with m.patch.object(arb, "fetch_book_tickers", return_value=tickers), \
     m.patch.object(arb, "_log_triangular", return_value=None):
    res = arb.triangular_scan()
check("scan reports an opportunity object", res["opportunity"] is not None)
check("scan flags positive after mispricing", res["opportunity"]["positive"] is True)

# Consistent (no-arb) market -> no opportunity.
fair = {"BTCUSDT": {"bid": 60000.0, "ask": 60000.0}, "ETHUSDT": {"bid": 3000.0, "ask": 3000.0},
        "ETHBTC": {"bid": 0.05, "ask": 0.05}}
with m.patch.object(arb, "fetch_book_tickers", return_value=fair), \
     m.patch.object(arb, "_log_triangular", return_value=None):
    res2 = arb.triangular_scan()
check("consistent market -> no (positive) opportunity", res2["opportunity"] is None or res2["opportunity"]["positive"] is False)

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL TRIANGULAR TESTS PASSED")
