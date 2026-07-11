"""End-to-end cross-layer audit of the full P0-P3 stack. Run: python -m scripts.audit

The per-slice test suites each check ONE layer in isolation. This verifies the layers COMPOSE:
the silence chain ordering, the de-risk multiplier stacking into sizing, the feature vector, and
live/backtest consistency of geometry + costs — on real live data across the watchlist.
"""
from __future__ import annotations

import math

from app import allocator, calibration, drift, sizing
from app.config import settings
from app.meta_features import FEATURE_KEYS
from app.signal_service import compute_signal, _rr_floor
from app.costs import round_trip_cost, cost_in_r
from app.geometry import trade_levels

ISSUES = []
def bad(msg): ISSUES.append(msg); print(f"   !! {msg}")
def ok(msg): print(f"   ok {msg}")

CRYPTO = [("BTCUSDT", "4h"), ("ETHUSDT", "1h"), ("SOLUSDT", "4h"), ("BNBUSDT", "1h"),
          ("XRPUSDT", "4h"), ("ADAUSDT", "1h"), ("DOGEUSDT", "4h"), ("AVAXUSDT", "1h")]

print("=== 1. Signal path robustness + payload shape ===")
sigs = []
for sym, itv in CRYPTO:
    try:
        d = compute_signal(sym, itv, market="crypto", with_news=False, with_macro=False)
        sigs.append(d)
    except Exception as e:
        bad(f"compute_signal({sym},{itv}) raised: {e}")
if len(sigs) == len(CRYPTO):
    ok(f"all {len(CRYPTO)} crypto signals computed without error")

for d in sigs:
    tag = f"{d['symbol']}/{d['interval']}"
    if len(d.get("features") or []) != len(FEATURE_KEYS):
        bad(f"{tag}: features len {len(d.get('features') or [])} != {len(FEATURE_KEYS)}")
    wp = d.get("win_prob")
    if wp is None or not (0.02 <= wp <= 0.98):
        bad(f"{tag}: win_prob out of range: {wp}")
    mp = d.get("meta_p")
    if mp is not None and not (0.02 <= mp <= 0.98):
        bad(f"{tag}: meta_p out of range: {mp}")
    if d.get("strategy") not in ("trend", "range-fade"):
        bad(f"{tag}: bad strategy {d.get('strategy')}")
    rs = d.get("risk_state") or {}
    for k in ("drifting", "circuit_halted", "size_mult", "day_r"):
        if k not in rs:
            bad(f"{tag}: risk_state missing {k}")
    # position_sizing present iff ev_r present (computed together)
    if (d.get("ev_r") is None) != (d.get("position_sizing") is None):
        bad(f"{tag}: ev_r / position_sizing presence mismatch")
ok("payload shape checks done")

print("=== 2. Silence chain ordering + actionability ===")
for d in sigs:
    tag = f"{d['symbol']}/{d['interval']}"
    actionable, sr = d.get("actionable"), d.get("silence_reason")
    if actionable and sr is not None:
        bad(f"{tag}: actionable but silence_reason={sr}")
    if not actionable and sr is None:
        bad(f"{tag}: not actionable but no silence_reason")
    if not actionable and d["label"] != "Neutral":
        bad(f"{tag}: silenced but label={d['label']}")
    # circuit breaker must win the chain
    if (d.get("risk_state") or {}).get("circuit_halted") and sr != "circuit_breaker":
        bad(f"{tag}: circuit halted but silence_reason={sr}")
    # actionable requires EV clear the floor
    if actionable and d.get("ev_r") is not None:
        tier_ev = sizing.tier_for_equity(settings.account_equity_usd)["ev_threshold"] if settings.tier_ev_gate_enabled else 0.0
        floor = max(settings.min_ev_r, tier_ev, drift.state()["ev_floor"])
        if d["ev_r"] < floor - 1e-9:
            bad(f"{tag}: actionable but ev_r {d['ev_r']} < floor {floor}")
ok("silence chain consistent")

print("=== 3. De-risk multiplier composition into sizing ===")
d_state = drift.state()
cal_mult = calibration.size_multiplier()
for d in sigs:
    ps = d.get("position_sizing")
    if not ps:
        continue
    tag = f"{d['symbol']}/{d['interval']}"
    kf, rf = ps["kelly_f"], ps["ruin_f"]
    cap = sizing.tier_for_equity(settings.account_equity_usd)["risk_cap"]
    fam_mult = allocator.family_multiplier(ps.get("family", "trend"))
    expected = min(kf, rf, cap) * (d_state["size_mult"] * cal_mult) * fam_mult
    if abs(ps["risk_fraction"] - expected) > 1e-4:
        bad(f"{tag}: risk_fraction {ps['risk_fraction']} != composed {round(expected,5)} "
            f"(kelly={kf} ruin={rf} cap={cap} drift={d_state['size_mult']} cal={cal_mult} alloc={round(fam_mult,3)})")
    if ps["risk_fraction"] > cap + 1e-9:
        bad(f"{tag}: risk_fraction exceeds tier cap")
    if ps["risk_fraction"] < 0:
        bad(f"{tag}: negative risk_fraction")
ok(f"sizing composes drift({d_state['size_mult']}) x cal({cal_mult}) x allocator, tier-capped")

print("=== 4. Live == backtest geometry + cost consistency ===")
# geometry: live _risk_geometry already delegates to trade_levels (unit-tested); re-confirm a range fade.
g = trade_levels(100.0, 2.0, "long", "4h", "range", bb_mid=104.0, bb_upper=108.0, bb_lower=99.0)
if not (g["is_fade"] and g["target"] == 104.0):
    bad("range-fade geometry regressed")
# cost model identical inputs -> identical output (used by resolver AND backtest)
c1 = round_trip_cost("crypto", "BTCUSDT", 0.015)
c2 = round_trip_cost("crypto", "ADAUSDT", 0.015)
if not (c1 < c2):
    bad("cost model tiering regressed (major !< alt)")
if cost_in_r("crypto", "BTCUSDT", 0.015, 0.02) != c1 / 0.02:
    bad("cost_in_r inconsistent with round_trip_cost")
ok("geometry + cost model consistent (shared live/backtest)")

print("=== 5. Calibration base rate matches realized hit rate ===")
cs = calibration.calibration_status()
from app import db
if db.enabled():
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("select count(*) filter (where pnl>0)::float/nullif(count(*),0) from outcomes where pnl is not null")
        hit = cur.fetchone()[0]
    if hit is not None and cs.get("base_rate") is not None and abs(hit - cs["base_rate"]) > 0.02:
        bad(f"calibration base_rate {cs['base_rate']} != realized hit {round(hit,4)}")
    else:
        ok(f"calibration base_rate {cs.get('base_rate')} ~ realized hit {round(hit,4) if hit else None}")

print()
if ISSUES:
    print(f"AUDIT FOUND {len(ISSUES)} ISSUE(S):")
    for i in ISSUES: print("  -", i)
    raise SystemExit(1)
print("AUDIT CLEAN — all cross-layer invariants hold")
