"""Test Cohort Invariants against Single Source of Truth (config/cohorts.json).

Rule 5.1 CI Invariant Test:
- core_4h_long_all n=191 with sum R_net = +59.5535 and regimes 151 / 29 / 11 with sums +25.5262 / +27.6633 / +6.3640
- flash_short_burst n=125 sum +5.82
- flash_long_burst n=479 sum -28.53
- core_short_all n=120 sum -65.65
- Reports separately how many of the 120 are forex/commodity (forex=69, commodities=2, total=71)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[2]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app import db
import pandas as pd


def test_cohort_invariants():
    cohorts_path = root_dir / "config" / "cohorts.json"
    if not cohorts_path.exists():
        cohorts_path = backend_dir / "config" / "cohorts.json"
    assert cohorts_path.exists(), f"Missing cohorts single source of truth at {cohorts_path}"

    with open(cohorts_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    cohorts_cfg = config["cohorts"]

    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            select s.id, s.symbol, coalesce(s.market, 'crypto') as market,
                   coalesce(s.strategy, 'core') as strategy, s.interval, s.label,
                   s.regime, coalesce(s.shadow, false) as shadow, o.r_net
            from signals s
            join outcomes o on o.signal_id = s.id
            where o.r_net is not null
        """)
        cols = [c.name for c in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)

    df["r_net"] = pd.to_numeric(df["r_net"], errors="coerce")

    print("=" * 80)
    print("TEST: COHORT SINGLE SOURCE OF TRUTH INVARIANTS (5.1)")
    print("=" * 80)

    # 1. core_4h_long_all
    c4l = df[(df["strategy"] == "core") & (df["interval"] == "4h") & (df["label"].isin(["Buy", "Strong Buy"]))]
    assert len(c4l) == 191, f"core_4h_long_all count mismatch: expected 191, got {len(c4l)}"
    assert math.isclose(float(c4l["r_net"].sum()), 59.5535, abs_tol=1e-3), f"core_4h_long_all sum mismatch: got {c4l['r_net'].sum():.4f}"
    print(f"PASS: core_4h_long_all (n={len(c4l)}, sum={c4l['r_net'].sum():+.4f} R, mean={c4l['r_net'].mean():+.4f} R)")

    # 1b. Regimes: 151 / 29 / 11
    trending = c4l[c4l["regime"].isin(["strong_trend", "weak_trend", "trending"])]
    ranging = c4l[c4l["regime"].isin(["range", "ranging"])]
    choppy = c4l[c4l["regime"].isin(["high_vol", "squeeze", "choppy", "chop"])]

    assert len(trending) == 151, f"core_4h_long_trending count mismatch: expected 151, got {len(trending)}"
    assert math.isclose(float(trending["r_net"].sum()), 25.5262, abs_tol=1e-3), f"trending sum mismatch: got {trending['r_net'].sum():.4f}"
    print(f"PASS: core_4h_long_trending (n={len(trending)}, sum={trending['r_net'].sum():+.4f} R, mean={trending['r_net'].mean():+.4f} R)")

    assert len(ranging) == 29, f"core_4h_long_ranging count mismatch: expected 29, got {len(ranging)}"
    assert math.isclose(float(ranging["r_net"].sum()), 27.6633, abs_tol=1e-3), f"ranging sum mismatch: got {ranging['r_net'].sum():.4f}"
    print(f"PASS: core_4h_long_ranging (n={len(ranging)}, sum={ranging['r_net'].sum():+.4f} R, mean={ranging['r_net'].mean():+.4f} R)")

    assert len(choppy) == 11, f"core_4h_long_choppy count mismatch: expected 11, got {len(choppy)}"
    assert math.isclose(float(choppy["r_net"].sum()), 6.3640, abs_tol=1e-3), f"choppy sum mismatch: got {choppy['r_net'].sum():.4f}"
    print(f"PASS: core_4h_long_choppy (n={len(choppy)}, sum={choppy['r_net'].sum():+.4f} R, mean={choppy['r_net'].mean():+.4f} R)")

    # 2. flash_short_burst
    fs = df[(df["strategy"] == "flash") & (df["label"].isin(["Sell", "Strong Sell"]))]
    assert len(fs) == 125, f"flash_short_burst count mismatch: expected 125, got {len(fs)}"
    assert math.isclose(float(fs["r_net"].sum()), 5.8203, abs_tol=0.01), f"flash_short_burst sum mismatch: got {fs['r_net'].sum():.4f}"
    assert (fs["market"] == "crypto").all(), "flash_short_burst contains non-crypto trades!"
    print(f"PASS: flash_short_burst (n={len(fs)}, sum={fs['r_net'].sum():+.4f} R, mean={fs['r_net'].mean():+.4f} R)")

    # 3. flash_long_burst
    fl = df[(df["strategy"] == "flash") & (df["label"].isin(["Buy", "Strong Buy"]))]
    assert len(fl) == 479, f"flash_long_burst count mismatch: expected 479, got {len(fl)}"
    assert math.isclose(float(fl["r_net"].sum()), -28.5277, abs_tol=0.02), f"flash_long_burst sum mismatch: got {fl['r_net'].sum():.4f}"
    assert (fl["market"] == "crypto").all(), "flash_long_burst contains non-crypto trades!"
    print(f"PASS: flash_long_burst (n={len(fl)}, sum={fl['r_net'].sum():+.4f} R, mean={fl['r_net'].mean():+.4f} R)")

    # 4. core_short_all
    cs = df[(df["strategy"] == "core") & (df["label"].isin(["Sell", "Strong Sell"]))]
    assert len(cs) == 120, f"core_short_all count mismatch: expected 120, got {len(cs)}"
    assert math.isclose(float(cs["r_net"].sum()), -65.6538, abs_tol=0.02), f"core_short_all sum mismatch: got {cs['r_net'].sum():.4f}"
    
    # Market breakdown check
    market_counts = cs["market"].value_counts().to_dict()
    n_forex = market_counts.get("forex", 0)
    n_commodities = market_counts.get("commodities", 0)
    n_crypto = market_counts.get("crypto", 0)
    n_forex_comm = n_forex + n_commodities

    assert n_forex == 69, f"Forex shorts mismatch: expected 69, got {n_forex}"
    assert n_commodities == 2, f"Commodity shorts mismatch: expected 2, got {n_commodities}"
    assert n_crypto == 45, f"Crypto shorts mismatch: expected 45, got {n_crypto}"
    assert n_forex_comm == 71, f"Forex+Commodity total mismatch: expected 71, got {n_forex_comm}"

    print(f"PASS: core_short_all (n={len(cs)}, sum={cs['r_net'].sum():+.4f} R, mean={cs['r_net'].mean():+.4f} R)")
    print(f"      Market Breakdown: Forex={n_forex}, Crypto={n_crypto}, Commodities={n_commodities}, Rates={market_counts.get('rates', 0)}, Indices={market_counts.get('indices', 0)}")
    print(f"      Forex + Commodities Subtotal: {n_forex_comm} / 120 ({n_forex_comm/120*100:.1f}%)")
    print("\nSUCCESS: All cohort invariants strictly satisfied.")


if __name__ == "__main__":
    test_cohort_invariants()
