"""5.3 Trade-Level Proof: 20 Random Core 4h Long Trades with Stored and Recomputed Fields."""

import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[1]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app import db
from app.costs import trade_cost, _crypto_tier, _CRYPTO_TIERS


def audit_20_trades():
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            select s.id as signal_id, s.symbol, coalesce(s.market, 'crypto') as market,
                   s.interval, coalesce(s.strategy, 'core') as strategy,
                   s.regime, s.label, s.entry, s.stop, s.target, s.atr, s.as_of,
                   o.id as outcome_id, o.result, o.pnl, o.r_net, o.cost_r,
                   o.bars_held, o.mfe, o.mae
            from signals s
            join outcomes o on o.signal_id = s.id
            where s.strategy = 'core' and s.interval = '4h' and s.label in ('Buy', 'Strong Buy') and o.r_net is not null
            order by s.id asc
        """)
        cols = [c.name for c in cur.description]
        records = [dict(zip(cols, r)) for r in cur.fetchall()]

    df = pd.DataFrame(records)
    for c in ['entry', 'stop', 'target', 'atr', 'pnl', 'r_net', 'cost_r', 'bars_held', 'mfe', 'mae']:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    # Seed 42 for deterministic 20-trade sample
    rng = np.random.default_rng(42)
    sample_idx = rng.choice(len(df), size=20, replace=False)
    sample_df = df.iloc[sample_idx]

    rows = []
    for _, r in sample_df.iterrows():
        entry = float(r['entry'])
        stop = float(r['stop'])
        target = float(r['target'])
        risk_dist = abs(entry - stop)
        stop_dist_pct = risk_dist / entry if entry > 0 else 0.01
        atr_val = float(r['atr']) if pd.notna(r['atr']) else 0.02 * entry
        atr_pct = atr_val / entry
        bars = int(r['bars_held']) if pd.notna(r['bars_held']) else 12
        h_hours = bars * 4.0
        res = r['result'] or "stop"
        pnl = float(r['pnl']) if pd.notna(r['pnl']) else 0.0
        mfe = float(r['mfe']) if pd.notna(r['mfe']) else 0.0
        stored_r_net = float(r['r_net'])
        stored_cost_r = float(r['cost_r']) if pd.notna(r['cost_r']) else 0.0
        gross_r = stored_r_net + stored_cost_r

        # Institutional cost engine breakdown
        tier = _crypto_tier(r['symbol'])
        base_slip, vol_coef, spread = _CRYPTO_TIERS[tier]
        taker_slip = max(base_slip + vol_coef * min(max(atr_pct, 0.0), 0.15), 0.5 * spread)

        # Entry: hybrid maker (2 bps fee, 0 slippage)
        fee_entry = 0.0002
        slip_entry = 0.0

        # Exit: target maker (2 bps fee, 0 slip) vs stop taker (5 bps fee, taker slip + 3 bps)
        if res.lower() == "target":
            fee_exit = 0.0002
            slip_exit = 0.0
            exit_px = target
        else:
            fee_exit = 0.0005
            slip_exit = taker_slip + 0.0003
            # Exit price: if stop, stop price; if timeout/trailing_stop, deduce from gross
            if res.lower() == "stop":
                exit_px = stop
            else:
                # Deduce exit price from gross return
                gross_frac = gross_r * stop_dist_pct
                exit_px = entry * (1.0 + gross_frac)

        # Funding: 8h settlement (0.01% per 8h)
        periods = h_hours / 8.0
        funding_pct = 0.0001 * periods

        fee_r = (fee_entry + fee_exit) / stop_dist_pct
        slip_r = (slip_entry + slip_exit) / stop_dist_pct
        funding_r = funding_pct / stop_dist_pct
        total_cost_r = (fee_entry + fee_exit + slip_entry + slip_exit + funding_pct) / stop_dist_pct
        recomputed_r_net = gross_r - total_cost_r

        # Partial-book events: triggered if MFE >= +0.20R
        mfe_r = (mfe / stop_dist_pct) if stop_dist_pct > 0 else 0.0
        if mfe_r >= 0.20:
            partial_px = entry + 0.20 * risk_dist
            partial_event = f"Booked 50% @ {partial_px:.4f} (+0.20R)"
        else:
            partial_event = "None (< +0.20R)"

        rows.append({
            "signal_id": int(r['signal_id']),
            "symbol": r['symbol'],
            "entry_fill": f"{entry:.4f}",
            "exit_price": f"{exit_px:.4f}",
            "stop": f"{stop:.4f}",
            "target": f"{target:.4f}",
            "partial_book": partial_event,
            "gross_r": f"{gross_r:+.4f} R",
            "fee_r": f"{fee_r:.4f} R",
            "slip_r": f"{slip_r:.4f} R",
            "funding_r": f"{funding_r:.4f} R",
            "stored_r_net": f"{stored_r_net:+.4f} R",
            "recomputed_r_net": f"{recomputed_r_net:+.4f} R"
        })

    print(f"Audited {len(rows)} Trades.")
    for row in rows[:5]:
        print(row)
    return rows


if __name__ == "__main__":
    audit_20_trades()
