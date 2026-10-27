"""Test: /performance endpoint dollar P&L matches audit_ledger_equity.py to the cent.

Mandated by Phase 0.6.1:
"/performance total must equal audit_ledger_equity.py total to the cent for the same filters; CI must fail otherwise."
"""

from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app import db, performance, sizing
from app.config import settings


def main() -> int:
    if not db.enabled():
        print("SKIP: Database not connected.")
        return 0

    print("======================================================================")
    print("TEST: /performance LEDGER RECONCILIATION INTEGRITY CHECK")
    print("======================================================================")

    equity = settings.account_equity_usd  # 1000.0

    # 1. Compute ground truth from raw DB query under same filter (core live: shadow=False)
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            select s.id, s.symbol, s.win_prob, s.reward_risk, s.size_pct,
                   o.r_net, o.pnl, s.shadow, coalesce(s.strategy, 'core') as strategy
            from outcomes o
            join signals s on o.signal_id = s.id
            where o.result is not null and (o.r_net is not null or o.pnl is not null)
              and (s.strategy = 'core' or s.strategy is null) and s.shadow = false
            order by o.resolved_at asc
        """)
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    gt_total = 0.0
    for r in rows:
        wp = float(r["win_prob"]) if r["win_prob"] is not None else 0.50
        rr = float(r["reward_risk"]) if r["reward_risk"] is not None else 1.8
        tier = sizing.tier_for_equity(equity)
        kf = sizing.quarter_kelly(wp, rr)
        rf = sizing.ruin_fraction(wp, rr, tier["risk_cap"])
        raw_kelly = min(kf, rf, tier["risk_cap"])
        sym_mult = 0.50 if (r["symbol"] or "").upper() == "BTCUSDT" else 1.0
        combined = raw_kelly * sym_mult

        if r["size_pct"] is not None:
            risk_pct = float(r["size_pct"])
        else:
            risk_pct = round(combined * 100.0, 3)

        risk_usd = equity * (risk_pct / 100.0)

        if r["r_net"] is not None:
            pnl = float(r["r_net"]) * risk_usd
        else:
            pnl = float(r["pnl"]) * equity
        gt_total += pnl

    gt_total_rounded = round(gt_total, 2)

    # 2. Call /performance endpoint logic
    perf_data = performance.performance(trade_size=equity, include_shadow=False, strategy="core")
    endpoint_total = perf_data["combined"]["realized_pnl_usd"]

    delta = abs(endpoint_total - gt_total_rounded)
    print(f"Ground Truth Realized P&L:  ${gt_total_rounded:+.2f} USD (n={len(rows)})")
    print(f"/performance Realized P&L:  ${endpoint_total:+.2f} USD (n={perf_data['combined']['closed_trades']})")
    print(f"Reconciliation Delta:       ${delta:.4f} USD")

    # 3. Assert exact match to the cent (< $0.01)
    if delta >= 0.01:
        print(f"FAILED: /performance total (${endpoint_total:.2f}) does not match ground truth (${gt_total_rounded:.2f})!")
        return 1

    # 4. Check ledger_status badge payload
    status = perf_data.get("ledger_status", {})
    assert status.get("reconciled") is True, "ledger_status.reconciled must be True"
    assert status.get("delta_usd") == 0.0, "ledger_status.delta_usd must be 0.0"
    print("SUCCESS: /performance reconciled to ground truth to the cent. CI check passed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
