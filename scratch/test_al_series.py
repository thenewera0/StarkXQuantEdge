import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

import json
import math
import numpy as np
import pandas as pd

from app.research.dataset import compute_btc_regimes

def load_all_cached_4h_data():
    cache_dir = Path("data_cache")
    if not cache_dir.exists():
        cache_dir = Path("backend/data_cache")
    data = {}
    for f in cache_dir.glob("*_4h.parquet"):
        sym = f.name.replace("_4h.parquet", "")
        try:
            df = pd.read_parquet(f)
            if len(df) >= 100:
                data[sym] = df
        except Exception:
            pass
    return data
from app.research.labels import simulate_hybrid_entry_barrier
from app.indicators.engine import compute_indicators
from app.signal_service import detect_regime, score_row

def main():
    frozen_path = Path("config/frozen_core_long_v1_1.json")
    with open(frozen_path, "r", encoding="utf-8") as f:
        frozen_params = json.load(f)["parameters"]

    data_4h = load_all_cached_4h_data()
    btc_4h = data_4h["BTCUSDT"]
    btc_regimes = compute_btc_regimes(btc_4h)

    conviction_floor = frozen_params["conviction_floor"]
    min_token_px = frozen_params["min_token_nominal_price"]
    allowed_regimes = {"strong_trend", "weak_trend", "range", "high_vol"}

    # We want to test different definitions of Always-Long paired comparison:
    # Option 1: Rule has partial booking (0.20R / 50%), AL has NO partial booking (pure barrier / buy & hold to exit)
    # Option 2: AL is a sequential strategy on each symbol (re-entering on every exit). Compare daily portfolio returns.
    # Option 3: Rule trade lifespan compared to Buy & Hold return over [entry, exit] normalized by risk_dist.

    rule_trades = []
    al_trades_no_pb = []
    al_trades_bnh = []

    for sym, df_raw in list(data_4h.items())[:10]: # test on 10 symbols first
        n_bars = len(df_raw)
        if n_bars < 100: continue
        ind_df = compute_indicators(df_raw)
        btc_sub = btc_regimes.reindex(ind_df.index, method="ffill")

        for i in range(50, n_bars - 48, 2):
            bar = ind_df.iloc[i]
            px = float(bar["close"])
            if px < min_token_px: continue
            reg = detect_regime(bar)
            if reg not in allowed_regimes: continue
            res = score_row(bar, interval="4h", regime=reg)

            if res.composite >= conviction_floor and res.label in ("Buy", "Strong Buy"):
                # Rule trade with partial booking
                t_rule = simulate_hybrid_entry_barrier(
                    df_raw, i, direction="long", k_up=2.0, k_dn=1.25, symbol=sym,
                    partial_book_r=frozen_params.get("partial_book_at_r", 0.20),
                    partial_book_frac=frozen_params.get("partial_book_fraction", 0.50),
                )
                # AL trade without partial booking (same exits, pure barrier)
                t_al_nopb = simulate_hybrid_entry_barrier(
                    df_raw, i, direction="long", k_up=2.0, k_dn=1.25, symbol=sym,
                    partial_book_r=999.0,
                    partial_book_frac=0.0,
                )
                if t_rule is not None and t_al_nopb is not None:
                    btc_reg = btc_sub.iloc[i].get("btc_regime", "bull")
                    t_rule["btc_regime"] = btc_reg
                    t_al_nopb["btc_regime"] = btc_reg
                    
                    # Also BnH over the holding period:
                    exit_bar = min(n_bars - 1, i + t_rule["bars_held"])
                    bnh_ret = (float(df_raw["close"].iloc[exit_bar]) - t_rule["entry_px"]) / (1.25 * float(bar.get("atr", 0.02 * px)))
                    
                    rule_trades.append(t_rule)
                    al_trades_no_pb.append(t_al_nopb)
                    al_trades_bnh.append(bnh_ret)

    df_r = pd.DataFrame(rule_trades)
    df_al_npb = pd.DataFrame(al_trades_no_pb)
    
    print(f"Sample rule trades: {len(df_r)}")
    print(f"Rule Mean R: {df_r['r_net'].mean():.4f}")
    print(f"AL (No Partial Booking) Mean R: {df_al_npb['r_net'].mean():.4f}")
    diff = df_r['r_net'] - df_al_npb['r_net']
    print(f"Mean Difference (Rule - AL_no_pb): {diff.mean():.4f} R")
    print(f"Difference std: {diff.std():.4f}")
    print(f"Number of non-zero diffs: {(diff != 0).sum()} / {len(diff)}")

if __name__ == "__main__":
    main()
