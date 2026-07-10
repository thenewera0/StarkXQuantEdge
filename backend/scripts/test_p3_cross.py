"""Tests for the cross-exchange arb detector (Blueprint v2 §6.3). Run: python -m scripts.test_p3_cross"""
from __future__ import annotations

import unittest.mock as m

from app import arb
from app.config import settings

FAIL = []
def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAIL.append(name)

fee = 0.001
print("== cross-exchange net (both directions) ==")
# Consistent prices across venues -> net negative after fees.
a = {"bid": 60000.0, "ask": 60000.5}
b = {"bid": 59999.8, "ask": 60000.3}
o = arb.cross_exchange_opportunity("BTCUSDT", a, b, fee, fee)
check("consistent venues -> net < 0 (fees dominate)", o["net"] < 0)

# Bybit cheap: ask_b well below bid_a -> buy Bybit, sell Binance profits.
a2 = {"bid": 60200.0, "ask": 60210.0}
b2 = {"bid": 59900.0, "ask": 59910.0}     # ~0.48% gap > 0.2% fees
o2 = arb.cross_exchange_opportunity("BTCUSDT", a2, b2, fee, fee)
check("clear gap -> net > 0", o2["net"] > 0)
check("picks correct direction (buy Bybit -> sell Binance)", o2["direction"] == "buy Bybit -> sell Binance")

# Reverse: Binance cheap.
o3 = arb.cross_exchange_opportunity("BTCUSDT", b2, a2, fee, fee)
check("reverse gap -> buy Binance -> sell Bybit", o3["direction"] == "buy Binance -> sell Bybit" and o3["net"] > 0)

print("== scan ==")
bin_t = {"BTCUSDT": a2, "ETHUSDT": {"bid": 3000.0, "ask": 3000.3}}
byb_t = {"BTCUSDT": b2, "ETHUSDT": {"bid": 2999.7, "ask": 3000.0}}
with m.patch.object(arb, "fetch_book_tickers", return_value=bin_t), \
     m.patch("app.data.bybit.fetch_book_tickers", return_value=byb_t), \
     m.patch.object(arb, "_log_cross", return_value=None):
    res = arb.cross_exchange_scan(["BTCUSDT", "ETHUSDT"])
check("scan only pairs on BOTH venues", res["scanned"] == 2)
check("sorted by net desc", res["opportunities"][0]["net"] >= res["opportunities"][-1]["net"])
check("BTC gap flagged positive", any(o["symbol"] == "BTCUSDT" and o["positive"] for o in res["opportunities"]))
check("note mentions inventory/Growth tier", "inventory" in res.get("note", ""))

# Missing on one venue -> skipped.
with m.patch.object(arb, "fetch_book_tickers", return_value={"BTCUSDT": a2}), \
     m.patch("app.data.bybit.fetch_book_tickers", return_value={"ETHUSDT": {"bid": 1, "ask": 2}}), \
     m.patch.object(arb, "_log_cross", return_value=None):
    res2 = arb.cross_exchange_scan(["BTCUSDT", "ETHUSDT"])
check("no shared symbols -> 0 scanned", res2["scanned"] == 0)

print()
if FAIL:
    print(f"FAILED: {FAIL}")
    raise SystemExit(1)
print("ALL CROSS-EXCHANGE TESTS PASSED")
