"""Pre-registration and hash-locking of Direction A Spec (Blueprint Phase 4.2)."""

import hashlib
import json
from pathlib import Path

spec_content = {
    "version": "1.0",
    "as_of": "2026-10-27T00:00:00Z",
    "strategy_name": "hedged_cross_sectional_composite_dirA",
    "parameters": {
        "signal": "composite_from_frozen_core_long_v1_1",
        "long_leg": "quintile_5_top_20pct",
        "short_leg": "quintile_1_bottom_20pct",
        "dollar_neutral": True,
        "beta_hedge": "rolling_30d_btc_beta",
        "weighting_scheme": "equal_risk_inverse_30d_realized_vol",
        "rebalance_horizons_bars": [12, 24, 48],
        "entry_timing": "next_bar_open",
        "turnover_control": "rebalance_at_horizon",
        "costs": {
            "fee_taker_bps": 5.0,
            "fee_maker_bps": 2.0,
            "slippage_bps_rank_1_30": 3.0,
            "slippage_bps_rank_31_50": 6.0,
            "slippage_bps_rank_51_100": 10.0,
            "funding_model": "actual_8h_settlements",
            "borrow_fee": 0.0
        },
        "maker_variant": {
            "offset_atr": 0.15,
            "fill_rule": "trade_through_by_1_tick",
            "unfilled_timeout_bars": 2,
            "unfilled_fallback": "taker_market_sweep"
        },
        "universes": {
            "discovery": "ranks_1_to_50_trailing_30d_usd_vol",
            "validation": "ranks_51_to_100_trailing_30d_usd_vol",
            "min_history_days": 90
        },
        "pass_criteria": {
            "taker_net_sharpe_min": 0.50,
            "maker_net_sharpe_min": 1.20,
            "ci_lower_bound_gt_zero": True,
            "dsr_min": 0.95,
            "positive_years_min": "4_of_5",
            "positive_bull_and_bear": True,
            "top_5pct_days_max_pnl_share": 0.25,
            "placebo_p_max": 0.01,
            "incremental_alpha_t_min": 2.0
        }
    }
}

content_str = json.dumps(spec_content, indent=2, sort_keys=True)
sha = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
spec_content["sha256"] = sha

for p in [Path("config/dirA_spec.json"), Path("backend/config/dirA_spec.json")]:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(spec_content, f, indent=2)
    print(f"Wrote {p} (SHA256: {sha})")
